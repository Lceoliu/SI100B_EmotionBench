from __future__ import annotations

import json

from conftest import TEST_ROOT, make_onnx


def write_split(name: str, labels: dict[str, int]) -> None:
    split = TEST_ROOT / "data" / name
    (split / "images").mkdir(parents=True, exist_ok=True)
    rows = ["filename,label"]
    for filename, label in labels.items():
        (split / "images" / filename).write_bytes(b"placeholder")
        rows.append(f"{filename},{label}")
    (split / "labels.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def fake_container(predictions: dict[str, int]):
    def run(package_dir, images_dir, out_dir, timeout_sec, cfg):
        assert (package_dir / "model.onnx").is_file()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "predictions.json").write_text(json.dumps({"status": "ok", "predictions": predictions}), encoding="utf-8")
        return b"ok"

    return run


def test_public_submission_is_scored_and_ranked(monkeypatch, app_module, student):
    from worker import runner

    write_split("final", {"a.jpg": 3, "b.jpg": 3, "c.jpg": 0})
    monkeypatch.setattr(runner, "run_eval_container", fake_container({"a.jpg": 3, "b.jpg": 3, "c.jpg": 3}))
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]

    assert runner.run_once() is True
    assert runner.run_once() is False

    report = student.get(f"/api/me/report/{submission_id}").json()
    assert report["submission"]["status"] == "passed"
    assert [score["split"] for score in report["scores"]] == ["final"]
    assert report["scores"][0]["accuracy"] == 2 / 3
    rows = student.get("/api/leaderboard").json()["rows"]
    assert [row["id"] for row in rows] == [submission_id]
    assert rows[0]["public_score"] == report["scores"][0]["macro_f1"]


def test_dry_run_submission_is_validated(monkeypatch, app_module, student):
    from worker import runner

    write_split("dryrun", {"a.jpg": 3})
    monkeypatch.setattr(runner, "run_eval_container", fake_container({"a.jpg": 3}))
    submission_id = student.submit(make_onnx(), mode="dry-run").json()["submission"]["id"]
    assert runner.run_once() is True
    report = student.get(f"/api/me/report/{submission_id}").json()
    assert report["submission"]["status"] == "validated"
    assert student.get("/api/leaderboard").json()["rows"] == []


def test_container_failure_marks_submission_failed(monkeypatch, app_module, student):
    from worker import runner

    write_split("final", {"a.jpg": 3})

    def boom(*args, **kwargs):
        raise RuntimeError("sandbox exploded")

    monkeypatch.setattr(runner, "run_eval_container", boom)
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    assert runner.run_once() is True
    report = student.get(f"/api/me/report/{submission_id}").json()
    assert report["submission"]["status"] == "failed"
    assert "sandbox exploded" in report["submission"]["message"]
