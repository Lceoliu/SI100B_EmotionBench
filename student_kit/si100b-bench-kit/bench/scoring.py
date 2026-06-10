from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def normalize_key(value: str) -> str:
    value = str(value).replace("\\", "/").strip()
    if value.startswith("./"):
        return value[2:]
    return value


def load_labels(path: Path) -> dict[str, int]:
    rows = path.read_text(encoding="utf-8-sig").splitlines()
    reader = csv.DictReader(rows)
    labels: dict[str, int] = {}
    for row in reader:
        key = row.get("filename") or row.get("file") or row.get("path") or row.get("image")
        label = row.get("label") or row.get("class") or row.get("target")
        if key is not None and label is not None:
            labels[normalize_key(key)] = int(label)
    if not labels:
        raise ValueError("labels.csv 没有可用标签。请确认包含 filename,label 两列。")
    return labels


def compute_macro_f1(y_true: list[int], y_pred: list[int], num_classes: int) -> tuple[float, float, list[list[int]], dict[str, dict[str, float]]]:
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
    return sum(f1s) / num_classes, accuracy, confusion, per_class


def write_confusion_png(path: Path, confusion: list[list[int]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(confusion, cmap="Blues")
    ax.set_xlabel("Pred")
    ax.set_ylabel("True")
    for i, row in enumerate(confusion):
        for j, value in enumerate(row):
            ax.text(j, i, str(value), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def save_metrics(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
