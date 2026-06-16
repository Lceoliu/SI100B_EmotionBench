from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("BENCH_ROOT", ".")).resolve()
OUT_PATH = Path(os.environ.get("GPU_STATUS_PATH", ROOT / "storage" / "runtime" / "gpu.json")).resolve()
INTERVAL_SECONDS = int(os.environ.get("GPU_MONITOR_INTERVAL_SECONDS", "5"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_gpu_status() -> dict[str, Any]:
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        try:
            gpus = []
            for index in range(pynvml.nvmlDeviceGetCount()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except pynvml.NVMLError:
                    temperature = None
                try:
                    power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
                    power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000
                except pynvml.NVMLError:
                    power_draw = None
                    power_limit = None
                try:
                    raw_name = pynvml.nvmlDeviceGetName(handle)
                    name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)
                except pynvml.NVMLError:
                    name = f"GPU {index}"
                gpus.append(
                    {
                        "index": index,
                        "name": name,
                        "utilization_gpu": utilization.gpu,
                        "utilization_memory": utilization.memory,
                        "memory_used_mb": round(memory.used / 1024 / 1024),
                        "memory_total_mb": round(memory.total / 1024 / 1024),
                        "temperature_gpu": temperature,
                        "power_draw_w": round(power_draw, 1) if power_draw is not None else None,
                        "power_limit_w": round(power_limit, 1) if power_limit is not None else None,
                    }
                )
            return {"available": True, "updated_at": now_iso(), "gpus": gpus}
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:
        return {"available": False, "updated_at": now_iso(), "error": str(exc)}


def write_status(payload: dict[str, Any]) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = OUT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(OUT_PATH)


def main() -> None:
    while True:
        write_status(read_gpu_status())
        time.sleep(max(1, INTERVAL_SECONDS))


if __name__ == "__main__":
    main()
