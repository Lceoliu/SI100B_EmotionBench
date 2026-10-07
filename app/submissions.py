"""Submission file handling shared by the API routes."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import env
from app.config import load_config
from app.models import Submission
from app.onnx_validation import metadata_payload, validate_onnx_model


def validate_submission_file(file_bytes: bytes, filename: str, requested_input_size: int, requested_channels: int) -> dict[str, Any]:
    cfg = load_config()
    max_weight_mb = float(cfg.get("max_weight_mb", 200))
    max_params = int(cfg.get("max_params", 50_000_000))
    if not filename.lower().endswith(".onnx"):
        raise ValueError("请直接上传单个 .onnx 文件，不再接受 zip/model.py/safetensors。")
    meta = validate_onnx_model(
        file_bytes,
        requested_input_size=requested_input_size,
        requested_channels=requested_channels,
        max_model_mb=max_weight_mb,
        max_params=max_params,
    )
    return metadata_payload(meta, model_mb=len(file_bytes) / 1024 / 1024)


def remove_submission_artifacts(submission: Submission) -> None:
    if not submission.package_path or submission.package_path == "seed":
        return
    archive_path = Path(submission.package_path).resolve()
    if archive_path.is_file() and env.SUBMISSION_ROOT in archive_path.parents:
        submit_dir = archive_path.parent.parent if archive_path.parent.name == "package" else archive_path.parent
        if submit_dir.exists() and env.SUBMISSION_ROOT in submit_dir.resolve().parents:
            shutil.rmtree(submit_dir, ignore_errors=True)


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def bytes_mb(value: int) -> float:
    return round(value / 1024 / 1024, 2)


def queue_snapshot(db: Session) -> dict[str, Any]:
    """Queued submission ids in the order the worker claims them, plus the running count."""
    queued_ids = db.scalars(
        select(Submission.id)
        .where(Submission.status == "queued", Submission.package_path != "", Submission.package_path != "seed")
        .order_by(Submission.created_at.asc(), Submission.id.asc())
    ).all()
    running = db.scalar(select(func.count(Submission.id)).where(Submission.status == "running")) or 0
    return {"positions": {submission_id: index + 1 for index, submission_id in enumerate(queued_ids)}, "queued": len(queued_ids), "running": int(running)}


def with_queue_position(payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    payload["queue_position"] = snapshot["positions"].get(payload["id"])
    payload["queue_length"] = snapshot["queued"]
    return payload
