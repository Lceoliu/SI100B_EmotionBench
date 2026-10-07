from __future__ import annotations

import json

import pytest

from worker.scoring import compute_macro_f1, compute_metrics, load_labels, load_predictions, match_predictions, score_predictions


def test_perfect_predictions():
    y = [0, 1, 2, 3, 4, 5, 6]
    metrics = compute_metrics(y, y, 7, bootstrap_n=20)
    assert metrics["macro_f1"] == pytest.approx(1.0)
    assert metrics["accuracy"] == pytest.approx(1.0)


def test_macro_f1_matches_confusion_based_metric():
    y_true = [0, 0, 1, 1, 2, 2, 3]
    y_pred = [0, 1, 1, 1, 2, 0, 3]
    metrics = compute_metrics(y_true, y_pred, 7, bootstrap_n=20)
    assert metrics["macro_f1"] == pytest.approx(compute_macro_f1(y_true, y_pred, 7))
    assert metrics["confusion"][0] == [1, 1, 0, 0, 0, 0, 0]
    assert metrics["ci_low"] <= metrics["macro_f1"] <= metrics["ci_high"] or metrics["ci_low"] <= metrics["ci_high"]


def test_labels_with_and_without_header(tmp_path):
    with_header = tmp_path / "a.csv"
    with_header.write_text("filename,label\nx/1.jpg,3\n2.jpg,4\n", encoding="utf-8")
    without_header = tmp_path / "b.csv"
    without_header.write_text("1.jpg,3\n", encoding="utf-8")
    assert load_labels(with_header) == {"x/1.jpg": 3, "2.jpg": 4}
    assert load_labels(without_header) == {"1.jpg": 3}


def test_predictions_match_by_basename(tmp_path):
    predictions = tmp_path / "p.json"
    predictions.write_text(json.dumps({"predictions": {"sub/1.jpg": 3, "2.jpg": {"label": 1}}}), encoding="utf-8")
    labels = {"1.jpg": 3, "2.jpg": 4, "3.jpg": 0}
    y_true, y_pred, missing = match_predictions(labels, load_predictions(predictions))
    assert (y_true, y_pred, missing) == ([3, 4], [3, 1], ["3.jpg"])


def test_score_predictions_reports_missing(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text("filename,label\n1.jpg,0\n2.jpg,1\n", encoding="utf-8")
    predictions = tmp_path / "predictions.json"
    predictions.write_text(json.dumps({"predictions": {"1.jpg": 0}}), encoding="utf-8")
    metrics = score_predictions(labels, predictions, 7)
    assert metrics["matched"] == 1
    assert metrics["missing_count"] == 1
