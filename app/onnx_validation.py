from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import onnx
from onnx import ModelProto, TensorProto


ALLOWED_INPUT_SIZES = {48, 64, 96, 112, 160, 224}
ALLOWED_CHANNELS = {1, 3}
NUM_CLASSES = 7


@dataclass(frozen=True)
class OnnxMetadata:
    input_name: str
    input_channels: int
    input_size: int
    output_name: str
    param_count: int
    opset: int
    metadata_props: dict[str, str]


def _dim_value(dim) -> int | str | None:
    if dim.HasField("dim_value"):
        return int(dim.dim_value)
    if dim.HasField("dim_param") and dim.dim_param:
        return str(dim.dim_param)
    return None


def _shape_of(value_info) -> list[int | str | None]:
    tensor_type = value_info.type.tensor_type
    if not tensor_type.HasField("shape"):
        raise ValueError(f"ONNX input {value_info.name} must declare a tensor shape.")
    return [_dim_value(dim) for dim in tensor_type.shape.dim]


def _tensor_numel(tensor) -> int:
    count = 1
    for dim in tensor.dims:
        count *= int(dim)
    return count


def _check_no_external_data(model: ModelProto) -> None:
    offenders: list[str] = []
    for tensor in list(model.graph.initializer) + list(model.graph.sparse_initializer):
        if tensor.data_location == TensorProto.EXTERNAL or tensor.external_data:
            offenders.append(tensor.name or "<unnamed>")
    if offenders:
        preview = ", ".join(offenders[:5])
        raise ValueError(f"ONNX external data is not allowed. External tensors: {preview}")


def _metadata_dict(model: ModelProto) -> dict[str, str]:
    return {item.key: item.value for item in model.metadata_props}


def validate_onnx_model(
    model_bytes: bytes,
    *,
    requested_input_size: int,
    requested_channels: int,
    max_model_mb: float,
    max_params: int,
) -> OnnxMetadata:
    if len(model_bytes) <= 0:
        raise ValueError("ONNX file is empty.")
    model_mb = len(model_bytes) / 1024 / 1024
    if model_mb > max_model_mb:
        raise ValueError(f"ONNX file is {model_mb:.1f} MB; limit is {max_model_mb:.0f} MB.")
    if requested_input_size not in ALLOWED_INPUT_SIZES:
        raise ValueError(f"Input size must be one of {sorted(ALLOWED_INPUT_SIZES)}.")
    if requested_channels not in ALLOWED_CHANNELS:
        raise ValueError("Input channels must be 1 or 3.")

    model = onnx.ModelProto()
    try:
        model.ParseFromString(model_bytes)
    except Exception as exc:
        raise ValueError("Invalid ONNX protobuf.") from exc
    _check_no_external_data(model)
    try:
        onnx.checker.check_model(model)
    except Exception as exc:
        raise ValueError(f"ONNX checker failed: {exc}") from exc

    graph_inputs = [item for item in model.graph.input if item.name not in {init.name for init in model.graph.initializer}]
    if len(graph_inputs) != 1:
        raise ValueError("ONNX model must have exactly one real input.")
    input_info = graph_inputs[0]
    input_type = input_info.type.tensor_type.elem_type
    if input_type != TensorProto.FLOAT:
        raise ValueError("ONNX input dtype must be float32.")
    input_shape = _shape_of(input_info)
    if len(input_shape) != 4:
        raise ValueError("ONNX input must be NCHW [B, C, H, W].")
    batch, channels, height, width = input_shape
    if not (batch is None or isinstance(batch, str) or batch > 0):
        raise ValueError("ONNX batch dimension must be positive or dynamic.")
    if channels != requested_channels:
        raise ValueError(f"ONNX input channels C={channels}; page selection is C={requested_channels}.")
    if height != requested_input_size or width != requested_input_size:
        raise ValueError(f"ONNX input shape H/W={height}x{width}; page selection is {requested_input_size}.")

    if not model.graph.output:
        raise ValueError("ONNX model must declare one output.")
    output_info = model.graph.output[0]
    output_shape = _shape_of(output_info)
    if len(output_shape) != 2 or output_shape[-1] != NUM_CLASSES:
        raise ValueError("ONNX output must be logits with shape [B, 7].")

    param_count = sum(_tensor_numel(tensor) for tensor in model.graph.initializer)
    if param_count > max_params:
        raise ValueError(f"Model has {param_count:,} initializer parameters; limit is {max_params:,}.")
    opset = max((item.version for item in model.opset_import if item.domain in {"", "ai.onnx"}), default=0)
    return OnnxMetadata(
        input_name=input_info.name,
        input_channels=requested_channels,
        input_size=requested_input_size,
        output_name=output_info.name,
        param_count=param_count,
        opset=opset,
        metadata_props=_metadata_dict(model),
    )


def metadata_payload(meta: OnnxMetadata, *, model_mb: float) -> dict[str, Any]:
    return {
        "model_format": "onnx",
        "input_name": meta.input_name,
        "input_channels": meta.input_channels,
        "input_size": meta.input_size,
        "output_name": meta.output_name,
        "param_count": meta.param_count,
        "weight_mb": model_mb,
        "opset": meta.opset,
        "metadata_props": meta.metadata_props,
    }
