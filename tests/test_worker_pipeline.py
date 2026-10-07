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


def run_with_container_error(monkeypatch, student, exc: Exception) -> dict:
    from worker import runner

    write_split("final", {"a.jpg": 3})

    def boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(runner, "run_eval_container", boom)
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    assert runner.run_once() is True
    return student.get(f"/api/me/report/{submission_id}").json()["submission"]


def test_model_failure_marks_submission_failed(monkeypatch, app_module, student):
    from worker.runner import ModelFailure

    submission = run_with_container_error(monkeypatch, student, ModelFailure("ONNX output must be [B, 7]"))
    assert submission["status"] == "failed"
    assert "ONNX output" in submission["message"]


def test_infrastructure_failure_is_a_system_error(monkeypatch, app_module, student):
    submission = run_with_container_error(monkeypatch, student, RuntimeError("docker daemon unreachable"))
    assert submission["status"] == "error"
    assert "不计入" in submission["message"]
    assert student.get("/api/me/group").json()["quota"]["used"] == 0


def test_missing_evaluation_data_is_a_system_error(app_module, student):
    from worker import runner

    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    assert runner.run_once() is True
    assert student.get(f"/api/me/report/{submission_id}").json()["submission"]["status"] == "error"


class FakeContainer:
    def __init__(self, *, exit_code: int = 0, wait_error: Exception | None = None, logs: bytes = b"") -> None:
        self.exit_code = exit_code
        self.wait_error = wait_error
        self._logs = logs
        self.removed = False

    def wait(self, timeout):
        if self.wait_error:
            raise self.wait_error
        return {"StatusCode": self.exit_code}

    def logs(self, stdout, stderr):
        return self._logs

    def stop(self, timeout):
        pass

    def remove(self, force):
        self.removed = True


def run_fake_container(monkeypatch, tmp_path, container: FakeContainer):
    from types import SimpleNamespace

    from worker import runner

    client = SimpleNamespace(containers=SimpleNamespace(run=lambda *args, **kwargs: container))
    monkeypatch.setattr(runner.docker, "from_env", lambda: client)
    return runner.run_eval_container(tmp_path / "sub", tmp_path / "data", tmp_path / "out", 5, {})


def test_nonzero_sandbox_exit_is_a_model_failure(monkeypatch, tmp_path):
    import pytest

    from worker.runner import ModelFailure

    container = FakeContainer(exit_code=1, logs=b"RuntimeError: ONNX output must be [B, 7]")
    with pytest.raises(ModelFailure, match="ONNX output"):
        run_fake_container(monkeypatch, tmp_path, container)
    assert container.removed


def test_sandbox_data_error_exit_is_not_a_model_failure(monkeypatch, tmp_path):
    import pytest

    from worker.runner import SANDBOX_DATA_ERROR_EXIT, ModelFailure

    container = FakeContainer(exit_code=SANDBOX_DATA_ERROR_EXIT, logs=b"data error: no images")
    with pytest.raises(RuntimeError) as excinfo:
        run_fake_container(monkeypatch, tmp_path, container)
    assert not isinstance(excinfo.value, ModelFailure)


def test_sandbox_timeout_is_a_model_failure(monkeypatch, tmp_path):
    import pytest
    import requests

    from worker.runner import ModelFailure

    container = FakeContainer(wait_error=requests.exceptions.ReadTimeout("Read timed out"))
    with pytest.raises(ModelFailure, match="超时"):
        run_fake_container(monkeypatch, tmp_path, container)
