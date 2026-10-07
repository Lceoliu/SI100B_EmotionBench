"""Leaderboard ranking, CSV export and the JSON index snapshot."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import env
from app.config import load_config
from app.models import Score, Submission, User
from app.payloads import score_payload, score_summary_payload, submission_payload


def leaderboard_rows_payload(db: Session, reveal_private: bool = False) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Submission)
        .join(User)
        .where(Submission.mode == "public", Submission.status.in_(["passed", "final"]), User.leaderboard_hidden == False)
        .order_by(Submission.public_score.desc().nullslast(), Submission.created_at.asc())
    ).all()
    best_by_user: dict[int, Submission] = {}
    for row in rows:
        if row.public_score is None:
            continue
        current = best_by_user.get(row.user_id)
        if current is None or (row.public_score or 0) > (current.public_score or 0):
            best_by_user[row.user_id] = row
    ranked = sorted(best_by_user.values(), key=lambda item: item.public_score or 0, reverse=True)
    ranked_ids = [row.id for row in ranked]
    scores_by_submission: dict[int, list[Score]] = {}
    if ranked_ids:
        scores = db.scalars(select(Score).where(Score.submission_id.in_(ranked_ids))).all()
        for score in scores:
            scores_by_submission.setdefault(score.submission_id, []).append(score)

    payload = []
    for i, row in enumerate(ranked):
        scores = scores_by_submission.get(row.id, [])
        primary_score = (
            next((score for score in scores if score.split == "final"), None)
            or next((score for score in scores if score.split == "public"), None)
            or (scores[0] if scores else None)
        )
        payload.append(
            submission_payload(row, reveal_private=reveal_private)
            | {"rank": i + 1, "leaderboard_metrics": score_summary_payload(primary_score)}
        )
    return payload


def csv_percent(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value) * 100:.2f}"
    except (TypeError, ValueError):
        return ""


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    text_value = str(value)
    if text_value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text_value
    return text_value


LEADERBOARD_CSV_FIELDS = [
    "rank",
    "submission_id",
    "email",
    "display_name",
    "group_name",
    "filename",
    "status",
    "score_percent",
    "macro_f1",
    "accuracy_percent",
    "accuracy",
    "recall_percent",
    "recall",
    "input_shape",
    "input_channels",
    "input_size",
    "param_count",
    "weight_mb",
    "created_at",
    "updated_at",
]


def leaderboard_csv(db: Session) -> str:
    rows = leaderboard_rows_payload(db, reveal_private=True)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=LEADERBOARD_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        metrics = row.get("leaderboard_metrics") or {}
        macro_f1 = metrics.get("macro_f1", row.get("public_score"))
        accuracy = metrics.get("accuracy")
        recall = metrics.get("recall")
        channels = row.get("input_channels")
        size = row.get("input_size")
        input_shape = f"NCHW: N x {channels} x {size} x {size}" if channels and size else ""
        writer.writerow(
            {
                "rank": row.get("rank", ""),
                "submission_id": row.get("id", ""),
                "email": csv_cell(row.get("email", "")),
                "display_name": csv_cell(row.get("display_name", "")),
                "group_name": csv_cell(row.get("group_name", "")),
                "filename": csv_cell(row.get("filename", "")),
                "status": csv_cell(row.get("status", "")),
                "score_percent": csv_percent(macro_f1),
                "macro_f1": "" if macro_f1 is None else macro_f1,
                "accuracy_percent": csv_percent(accuracy),
                "accuracy": "" if accuracy is None else accuracy,
                "recall_percent": csv_percent(recall),
                "recall": "" if recall is None else recall,
                "input_shape": input_shape,
                "input_channels": "" if channels is None else channels,
                "input_size": "" if size is None else size,
                "param_count": row.get("param_count", ""),
                "weight_mb": row.get("weight_mb", ""),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", ""),
            }
        )
    return "﻿" + output.getvalue()


def write_sync_index(db: Session) -> dict[str, Any]:
    env.INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    reveal_private = bool(cfg.get("reveal_private", False))
    rows = db.scalars(select(Submission).join(User).order_by(Submission.created_at.desc())).all()
    scores = db.scalars(select(Score)).all()
    scores_by_submission: dict[int, list[Score]] = {}
    for score in scores:
        scores_by_submission.setdefault(score.submission_id, []).append(score)

    submissions_payload = []
    for row in rows:
        item = submission_payload(row, reveal_private=reveal_private)
        item["scores"] = [score_payload(score) for score in scores_by_submission.get(row.id, [])]
        submissions_payload.append(item)

    leaderboard_rows = leaderboard_rows_payload(db, reveal_private=reveal_private)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "submissions": submissions_payload,
        "leaderboard": leaderboard_rows,
    }
    (env.INDEX_ROOT / "submissions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (env.INDEX_ROOT / "leaderboard.json").write_text(json.dumps({"rows": leaderboard_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(env.INDEX_ROOT), "submissions": len(submissions_payload), "leaderboard": len(leaderboard_rows)}
