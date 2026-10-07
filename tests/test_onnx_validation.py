from __future__ import annotations

import pytest
from onnx import TensorProto

from app.onnx_validation import validate_onnx_model
from conftest import make_onnx


def validate(model_bytes: bytes, *, size: int = 48, channels: int = 1, max_params: int = 50_000_000, max_mb: float = 200):
    return validate_onnx_model(
        model_bytes,
        requested_input_size=size,
        requested_channels=channels,
        max_model_mb=max_mb,
        max_params=max_params,
    )


@pytest.mark.parametrize("channels,size", [(1, 48), (3, 64), (3, 112)])
def test_accepts_supported_shapes(channels, size):
    meta = validate(make_onnx(channels=channels, size=size), size=size, channels=channels)
    assert (meta.input_channels, meta.input_size, meta.opset) == (channels, size, 13)


def test_accepts_fixed_batch():
    assert validate(make_onnx(batch=1)).input_name == "input"


def test_rejects_garbage():
    with pytest.raises(ValueError, match="Invalid ONNX"):
        validate(b"\x00not-onnx" * 10)


def test_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate(b"")


def test_rejects_unsupported_size():
    with pytest.raises(ValueError, match="Input size"):
        validate(make_onnx(size=50), size=50)


def test_rejects_channel_mismatch():
    with pytest.raises(ValueError, match="channels"):
        validate(make_onnx(channels=3), channels=1)


def test_rejects_non_float_input():
    with pytest.raises(ValueError, match="float32"):
        validate(make_onnx(input_dtype=TensorProto.FLOAT16))


def test_rejects_wrong_output_shape():
    with pytest.raises(ValueError, match=r"\[B, 7\]"):
        validate(make_onnx(num_classes=5))


def test_rejects_too_many_params():
    with pytest.raises(ValueError, match="parameters"):
        validate(make_onnx(), max_params=100)


def test_rejects_oversized_file():
    with pytest.raises(ValueError, match="limit"):
        validate(make_onnx(), max_mb=0.01)


def test_rejects_external_data():
    import onnx

    model = onnx.load_from_string(make_onnx())
    tensor = model.graph.initializer[0]
    tensor.data_location = TensorProto.EXTERNAL
    entry = tensor.external_data.add()
    entry.key, entry.value = "location", "weights.bin"
    with pytest.raises(ValueError, match="external data"):
        validate(model.SerializeToString())
