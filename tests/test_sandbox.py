from __future__ import annotations

import json
import sys

import pytest

from conftest import REPO_ROOT, make_onnx

ort = pytest.importorskip("onnxruntime")
Image = pytest.importorskip("PIL.Image")


@pytest.fixture
def sandbox(monkeypatch):
    # The eval image copies sandbox/*.py to / and imports `transforms` as a top-level module.
    monkeypatch.syspath_prepend(str(REPO_ROOT / "sandbox"))
    for name in ("evaluate", "transforms"):
        sys.modules.pop(name, None)
    import evaluate

    return evaluate


@pytest.mark.parametrize("channels,size", [(1, 48), (3, 64)])
def test_evaluate_writes_predictions(tmp_path, monkeypatch, sandbox, channels, size):
    sub_dir, data_dir, out_dir = tmp_path / "sub", tmp_path / "data", tmp_path / "out"
    sub_dir.mkdir()
    data_dir.mkdir()
    (sub_dir / "model.onnx").write_bytes(make_onnx(channels=channels, size=size, bias_class=4))
    for index in range(5):
        Image.new("RGB", (100, 80), color=(index * 40, 10, 200)).save(data_dir / f"{index}.jpg")

    monkeypatch.setenv("SUBMISSION_DIR", str(sub_dir))
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("RESULT_DIR", str(out_dir))
    monkeypatch.setenv("BATCH_SIZE", "2")
    sandbox.main()

    payload = json.loads((out_dir / "predictions.json").read_text(encoding="utf-8"))
    assert payload["count"] == 5
    assert payload["input_channels"] == channels
    assert set(payload["predictions"].values()) == {4}
