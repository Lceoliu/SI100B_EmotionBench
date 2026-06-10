from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_labels(path: Path) -> dict[str, int]:
    if not path.exists():
        raise FileNotFoundError(f"labels.csv not found: {path}")
    rows = path.read_text(encoding="utf-8-sig").splitlines()
    if not rows:
        raise ValueError(f"labels.csv is empty: {path}")

    sample = rows[0].lower()
    has_header = "label" in sample and ("file" in sample or "path" in sample or "image" in sample)
    labels: dict[str, int] = {}
    if has_header:
        reader = csv.DictReader(rows)
        for row in reader:
            key = row.get("filename") or row.get("file") or row.get("path") or row.get("image") or row.get("name")
            label = row.get("label") or row.get("class") or row.get("target")
            if key is None or label is None:
                continue
            labels[normalize_key(key)] = int(label)
    else:
        reader = csv.reader(rows)
        for row in reader:
            if len(row) < 2:
                continue
            labels[normalize_key(row[0])] = int(row[1])
    if not labels:
        raise ValueError(f"labels.csv has no usable rows: {path}")
    return labels


def load_predictions(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("predictions", payload) if isinstance(payload, dict) else {}
    predictions: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            value = value.get("label", value.get("pred", value.get("class_id")))
        predictions[normalize_key(key)] = int(value)
    if not predictions:
        raise ValueError(f"predictions.json has no predictions: {path}")
    return predictions


def normalize_key(value: str) -> str:
    value = str(value).replace("\\", "/").strip()
    if value.startswith("./"):
        value = value[2:]
    return value


def match_predictions(labels: dict[str, int], predictions: dict[str, int]) -> tuple[list[int], list[int], list[str]]:
    y_true: list[int] = []
    y_pred: list[int] = []
    missing: list[str] = []
    basename_predictions = {Path(key).name: val for key, val in predictions.items()}
    for key, label in labels.items():
        pred = predictions.get(key)
        if pred is None:
            pred = basename_predictions.get(Path(key).name)
        if pred is None:
            missing.append(key)
            continue
        y_true.append(label)
        y_pred.append(pred)
    if not y_true:
        raise ValueError("no predictions matched labels")
    return y_true, y_pred, missing


def compute_metrics(y_true: list[int], y_pred: list[int], num_classes: int, bootstrap_n: int = 200) -> dict[str, Any]:
    labels = list(range(num_classes))
    confusion = [[0 for _ in labels] for _ in labels]
    for truth, pred in zip(y_true, y_pred):
        if 0 <= truth < num_classes and 0 <= pred < num_classes:
            confusion[truth][pred] += 1

    per_class: dict[str, dict[str, float]] = {}
    f1s: list[float] = []
    for cls in labels:
        tp = confusion[cls][cls]
        fp = sum(confusion[row][cls] for row in labels if row != cls)
        fn = sum(confusion[cls][col] for col in labels if col != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_class[str(cls)] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(confusion[cls])}
        f1s.append(f1)

    accuracy = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred) / len(y_true)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    ci_low, ci_high = bootstrap_ci(y_true, y_pred, num_classes, bootstrap_n)
    return {
        "macro_f1": macro_f1,
        "accuracy": accuracy,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "confusion": confusion,
        "per_class": per_class,
    }


def bootstrap_ci(y_true: list[int], y_pred: list[int], num_classes: int, bootstrap_n: int) -> tuple[float, float]:
    if len(y_true) < 2:
        metric = compute_macro_f1(y_true, y_pred, num_classes)
        return metric, metric
    rng = random.Random(20260610)
    values = []
    indices = list(range(len(y_true)))
    for _ in range(bootstrap_n):
        sample = [rng.choice(indices) for _ in indices]
        values.append(compute_macro_f1([y_true[i] for i in sample], [y_pred[i] for i in sample], num_classes))
    values.sort()
    low_idx = int(0.025 * (len(values) - 1))
    high_idx = int(0.975 * (len(values) - 1))
    return values[low_idx], values[high_idx]


def compute_macro_f1(y_true: list[int], y_pred: list[int], num_classes: int) -> float:
    buckets: dict[int, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for truth, pred in zip(y_true, y_pred):
        if truth == pred:
            buckets[truth]["tp"] += 1
        else:
            buckets[pred]["fp"] += 1
            buckets[truth]["fn"] += 1
    f1s = []
    for cls in range(num_classes):
        item = buckets[cls]
        precision = item["tp"] / (item["tp"] + item["fp"]) if item["tp"] + item["fp"] else 0.0
        recall = item["tp"] / (item["tp"] + item["fn"]) if item["tp"] + item["fn"] else 0.0
        f1s.append((2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    return sum(f1s) / num_classes


def score_predictions(labels_path: Path, predictions_path: Path, num_classes: int) -> dict[str, Any]:
    labels = load_labels(labels_path)
    predictions = load_predictions(predictions_path)
    y_true, y_pred, missing = match_predictions(labels, predictions)
    metrics = compute_metrics(y_true, y_pred, num_classes)
    metrics["matched"] = len(y_true)
    metrics["missing"] = missing[:50]
    metrics["missing_count"] = len(missing)
    return metrics


def write_confusion_matrix_png(confusion: list[list[int]], output_path: Path, class_names: list[str] | None = None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    labels = class_names or [str(index) for index in range(len(confusion))]
    matrix = np.array(confusion, dtype=float)
    row_sums = matrix.sum(axis=1, keepdims=True)
    normalized = np.divide(matrix, row_sums, out=np.zeros_like(matrix), where=row_sums != 0)

    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=160)
    image = ax.imshow(normalized, cmap="Blues", vmin=0, vmax=max(0.01, float(normalized.max())))
    ax.set_xticks(range(len(labels)), labels=labels, rotation=35, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title("Confusion Matrix")

    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = int(matrix[row, col])
            ratio = normalized[row, col]
            color = "white" if ratio > 0.45 else "#202020"
            ax.text(col, row, f"{value}\n{ratio:.0%}", ha="center", va="center", color=color, fontsize=8)

    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
