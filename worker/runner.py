from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docker
from docker.errors import NotFound
import yaml
from docker.types import DeviceRequest
from sqlalchemy import select

from app.main import Base, Score, SessionLocal, Submission, engine, validate_model_py, write_sync_index
from worker.scoring import score_predictions


ROOT = Path(os.environ.get("BENCH_ROOT", "/workspace")).resolve()
HOST_ROOT = Path(os.environ.get("HOST_BENCH_ROOT", str(ROOT))).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.yaml"))
DATA_ROOT = Path(os.environ.get("DATA_ROOT", ROOT / "data")).resolve()
RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT", ROOT / "results")).resolve()
LOG_ROOT = Path(os.environ.get("LOG_ROOT", ROOT / "logs" / "submissions")).resolve()
EVAL_IMAGE = os.environ.get("EVAL_IMAGE", "emotion-bench-eval:dev")
POLL_INTERVAL = float(os.environ.get("WORKER_POLL_INTERVAL", "5"))


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def host_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(HOST_ROOT / path.relative_to(ROOT))
    except ValueError:
        return str(path)


def reset_stuck_jobs() -> None:
    with SessionLocal() as db:
        rows = db.scalars(select(Submission).where(Submission.status == "running", Submission.package_path != "seed")).all()
        for row in rows:
            row.status = "queued"
            row.message = "Worker restarted; task returned to queue."
        if rows:
            db.commit()
            log(f"reset {len(rows)} stuck running submission(s)")


def claim_next_submission() -> int | None:
    with SessionLocal() as db:
        submission = db.scalars(
            select(Submission)
            .where(Submission.status == "queued", Submission.package_path != "seed", Submission.package_path != "")
            .order_by(Submission.created_at.asc())
            .limit(1)
        ).first()
        if submission is None:
            return None
        submission.status = "running"
        submission.message = "Worker claimed task; preparing sandbox."
        db.commit()
        return submission.id


def package_dir_for(submission: Submission) -> Path:
    archive = Path(submission.package_path)
    package_dir = archive.parent / "package"
    if not package_dir.exists():
        raise FileNotFoundError(f"submission package directory not found: {package_dir}")
    return package_dir


def run_static_check(package_dir: Path) -> None:
    model_files = list(package_dir.rglob("model.py"))
    weight_files = list(package_dir.rglob("model.safetensors"))
    if len(model_files) != 1 or len(weight_files) != 1:
        raise ValueError("submission package must contain exactly one model.py and one model.safetensors")
    validate_model_py(model_files[0].read_text(encoding="utf-8"))


def available_splits() -> list[tuple[str, Path, Path]]:
    splits = []
    for split in ("public", "private", "realworld"):
        split_dir = DATA_ROOT / split
        images_dir = split_dir / "images"
        labels_path = split_dir / "labels.csv"
        if images_dir.exists() and labels_path.exists():
            splits.append((split, images_dir, labels_path))
    return splits


def run_eval_container(package_dir: Path, images_dir: Path, out_dir: Path, timeout_sec: int, cfg: dict[str, Any]) -> bytes:
    out_dir.mkdir(parents=True, exist_ok=True)
    client = docker.from_env()
    environment = {
        "NUM_CLASSES": str(cfg.get("num_classes", 7)),
        "INPUT_SIZE": str(cfg.get("input_size", 224)),
        "NORMALIZE_MEAN": json.dumps(cfg.get("normalize", {}).get("mean", [0.485, 0.456, 0.406])),
        "NORMALIZE_STD": json.dumps(cfg.get("normalize", {}).get("std", [0.229, 0.224, 0.225])),
        "RESULT_DIR": "/out",
    }
    volumes = {
        host_path(package_dir): {"bind": "/sub", "mode": "ro"},
        host_path(images_dir): {"bind": "/data", "mode": "ro"},
        host_path(out_dir): {"bind": "/out", "mode": "rw"},
    }
    device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])] if os.environ.get("WORKER_USE_GPU", "1") == "1" else None
    container = client.containers.run(
        EVAL_IMAGE,
        detach=True,
        remove=False,
        network_disabled=True,
        user="1000:1000",
        mem_limit=os.environ.get("WORKER_MEMORY_LIMIT", "8g"),
        pids_limit=int(os.environ.get("WORKER_PIDS_LIMIT", "256")),
        read_only=True,
        tmpfs={"/tmp": "size=512m"},
        volumes=volumes,
        environment=environment,
        device_requests=device_requests,
    )
    try:
        result = container.wait(timeout=timeout_sec)
        logs = container.logs(stdout=True, stderr=True)
        status_code = result.get("StatusCode", 1)
        if status_code != 0:
            raise RuntimeError(logs.decode("utf-8", errors="replace")[-4000:])
        return logs
    except Exception:
        try:
            container.stop(timeout=10)
        except Exception:
            pass
        raise
    finally:
        try:
            container.remove(force=True)
        except NotFound:
            pass


def upsert_score(db, submission_id: int, split: str, metrics: dict[str, Any], predictions_path: Path) -> None:
    score = db.scalars(select(Score).where(Score.submission_id == submission_id, Score.split == split)).first()
    if score is None:
        score = Score(submission_id=submission_id, split=split)
        db.add(score)
    score.macro_f1 = float(metrics["macro_f1"])
    score.accuracy = float(metrics["accuracy"])
    score.ci_low = float(metrics["ci_low"])
    score.ci_high = float(metrics["ci_high"])
    score.confusion_json = json.dumps(metrics["confusion"], ensure_ascii=False)
    score.per_class_json = json.dumps(metrics["per_class"], ensure_ascii=False)
    score.predictions_path = str(predictions_path)


def evaluate_submission(submission_id: int) -> None:
    cfg = load_config()
    timeout_sec = int(cfg.get("eval_timeout_sec", 600))
    num_classes = int(cfg.get("num_classes", 7))
    splits = available_splits()
    if not splits:
        raise RuntimeError("没有找到可评测数据：需要 data/<split>/images 和 data/<split>/labels.csv")

    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if submission is None:
            raise RuntimeError(f"submission not found: {submission_id}")
        package_dir = package_dir_for(submission)
        submission.message = "Running static safety checks."
        db.commit()

    run_static_check(package_dir)

    split_metrics: dict[str, dict[str, Any]] = {}
    logs_dir = LOG_ROOT / str(submission_id)
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir = RESULTS_ROOT / f"submission-{submission_id}"

    for split, images_dir, labels_path in splits:
        out_dir = results_dir / split
        with SessionLocal() as db:
            submission = db.get(Submission, submission_id)
            submission.message = f"Evaluating {split} split in sandbox."
            db.commit()

        output = run_eval_container(package_dir, images_dir, out_dir, timeout_sec, cfg)
        (logs_dir / f"{split}.log").write_bytes(output)
        predictions_path = out_dir / "predictions.json"
        metrics = score_predictions(labels_path, predictions_path, num_classes)
        (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        split_metrics[split] = metrics

        with SessionLocal() as db:
            upsert_score(db, submission_id, split, metrics, predictions_path)
            db.commit()

    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        public = split_metrics.get("public")
        private = split_metrics.get("private")
        realworld = split_metrics.get("realworld")
        if public:
            submission.public_score = float(public["macro_f1"])
        if private:
            submission.private_score = float(private["macro_f1"])
        if realworld:
            submission.realworld_score = float(realworld["macro_f1"])
        submission.status = "passed"
        submission.message = "Evaluation finished."
        db.commit()
        write_sync_index(db)


def mark_failed(submission_id: int, message: str) -> None:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if submission:
            submission.status = "failed"
            submission.message = message[:2000]
            db.commit()
            write_sync_index(db)


def run_once() -> bool:
    submission_id = claim_next_submission()
    if submission_id is None:
        return False
    log(f"claimed submission {submission_id}")
    try:
        evaluate_submission(submission_id)
        log(f"finished submission {submission_id}")
    except Exception as exc:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        error_text = "".join(traceback.format_exception(exc))
        (LOG_ROOT / f"{submission_id}.error.log").write_text(error_text, encoding="utf-8")
        mark_failed(submission_id, str(exc))
        log(f"failed submission {submission_id}: {exc}")
    return True


def main() -> None:
    Base.metadata.create_all(engine)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    reset_stuck_jobs()
    log(f"worker started root={ROOT} eval_image={EVAL_IMAGE}")
    once = os.environ.get("WORKER_ONCE", "0") == "1"
    while True:
        had_job = run_once()
        if once:
            return
        if not had_job:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
