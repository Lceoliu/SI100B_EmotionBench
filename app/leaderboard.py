"""Group leaderboard, personal standing, CSV export and the JSON index snapshot.

Grading is per group: a group's score is the best Macro-F1 among the formal
submissions of its current members. There is a single leaderboard.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from app import env
from app.config import load_config
from app.models import Score, Submission, User
from app.payloads import score_payload, score_summary_payload, submission_payload
from app.quota import group_members, quota_status

SCORED_STATUSES = ("passed",)


def scored_submissions_query():
    return (
        select(Submission)
        .join(User)
        .options(contains_eager(Submission.user))
        .where(
            Submission.mode == "public",
            Submission.status.in_(SCORED_STATUSES),
            Submission.public_score.is_not(None),
        )
        .order_by(Submission.public_score.desc(), Submission.created_at.asc())
    )


def primary_scores(db: Session, submission_ids: list[int]) -> dict[int, Score]:
    if not submission_ids:
        return {}
    by_submission: dict[int, list[Score]] = defaultdict(list)
    for score in db.scalars(select(Score).where(Score.submission_id.in_(submission_ids))).all():
        by_submission[score.submission_id].append(score)
    result = {}
    for submission_id, scores in by_submission.items():
        result[submission_id] = (
            next((score for score in scores if score.split == "final"), None)
            or next((score for score in scores if score.split == "public"), None)
            or scores[0]
        )
    return result


def group_leaderboard(db: Session) -> list[dict[str, Any]]:
    """One row per group, ranked by the group's best formal submission."""
    rows = db.scalars(
        scored_submissions_query().where(User.leaderboard_hidden == False, User.group_name != "")  # noqa: E712
    ).all()
    best_by_group: dict[str, Submission] = {}
    for row in rows:
        best_by_group.setdefault(row.user.group_name, row)
    ranked = list(best_by_group.values())
    member_counts = dict(
        db.execute(
            select(User.group_name, func.count(User.id)).where(User.group_name.in_(list(best_by_group))).group_by(User.group_name)
        ).all()
    )
    scores = primary_scores(db, [row.id for row in ranked])
    payload = []
    for index, row in enumerate(ranked):
        payload.append(
            submission_payload(row)
            | {
                "rank": index + 1,
                "submission_id": row.id,
                "best_score": row.public_score,
                "submitted_by": row.user.display_name,
                "member_count": int(member_counts.get(row.user.group_name, 0)),
                "leaderboard_metrics": score_summary_payload(scores.get(row.id)),
            }
        )
    return payload


def best_submission_for(db: Session, user_ids: list[int]) -> Submission | None:
    if not user_ids:
        return None
    return db.scalars(scored_submissions_query().where(Submission.user_id.in_(user_ids)).limit(1)).first()


def standing_payload(db: Session, user: User) -> dict[str, Any]:
    """What a student needs to understand their grade: own best, group best, group rank and quota."""
    cfg = load_config()
    personal = best_submission_for(db, [user.id])
    members = group_members(db, user.group_name)
    member_rows = []
    for member in members:
        best = best_submission_for(db, [member.id])
        member_rows.append(
            {
                "id": member.id,
                "display_name": member.display_name,
                "email": member.student_id,
                "best_score": best.public_score if best else None,
                "best_submission_id": best.id if best else None,
            }
        )

    group = None
    if user.group_name:
        board = group_leaderboard(db)
        entry = next((row for row in board if row["group_name"] == user.group_name), None)
        group = {
            "rank": entry["rank"] if entry else None,
            "total_groups": len(board),
            "best_score": entry["best_score"] if entry else None,
            "best_submission_id": entry["submission_id"] if entry else None,
            "best_by": entry["submitted_by"] if entry else None,
            "best_is_mine": bool(entry and personal and entry["submission_id"] == personal.id),
        }
    return {
        "group_name": user.group_name or "",
        "mates": member_rows,
        "personal": {"best_score": personal.public_score, "best_submission_id": personal.id} if personal else None,
        "group": group,
        "quota": quota_status(db, user, cfg),
    }


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
    "group_name",
    "member_count",
    "members",
    "member_emails",
    "best_submission_id",
    "submitted_by",
    "submitted_by_email",
    "filename",
    "score_percent",
    "macro_f1",
    "accuracy_percent",
    "accuracy",
    "recall_percent",
    "recall",
    "input_shape",
    "param_count",
    "weight_mb",
    "submitted_at",
]


def leaderboard_csv(db: Session) -> str:
    rows = group_leaderboard(db)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=LEADERBOARD_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        members = group_members(db, row["group_name"])
        metrics = row.get("leaderboard_metrics") or {}
        macro_f1 = metrics.get("macro_f1", row.get("best_score"))
        accuracy = metrics.get("accuracy")
        recall = metrics.get("recall")
        channels = row.get("input_channels")
        size = row.get("input_size")
        writer.writerow(
            {
                "rank": row["rank"],
                "group_name": csv_cell(row["group_name"]),
                "member_count": row["member_count"],
                "members": csv_cell("; ".join(member.display_name for member in members)),
                "member_emails": csv_cell("; ".join(member.student_id for member in members)),
                "best_submission_id": row["submission_id"],
                "submitted_by": csv_cell(row["submitted_by"]),
                "submitted_by_email": csv_cell(row["email"]),
                "filename": csv_cell(row["filename"]),
                "score_percent": csv_percent(macro_f1),
                "macro_f1": "" if macro_f1 is None else macro_f1,
                "accuracy_percent": csv_percent(accuracy),
                "accuracy": "" if accuracy is None else accuracy,
                "recall_percent": csv_percent(recall),
                "recall": "" if recall is None else recall,
                "input_shape": f"NCHW: N x {channels} x {size} x {size}" if channels and size else "",
                "param_count": row.get("param_count", ""),
                "weight_mb": row.get("weight_mb", ""),
                "submitted_at": row.get("created_at", ""),
            }
        )
    return "﻿" + output.getvalue()


def write_sync_index(db: Session) -> dict[str, Any]:
    env.INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    rows = db.scalars(select(Submission).join(User).order_by(Submission.created_at.desc())).all()
    scores_by_submission: dict[int, list[Score]] = defaultdict(list)
    for score in db.scalars(select(Score)).all():
        scores_by_submission[score.submission_id].append(score)

    submissions_payload = []
    for row in rows:
        item = submission_payload(row)
        item["scores"] = [score_payload(score) for score in scores_by_submission.get(row.id, [])]
        submissions_payload.append(item)

    leaderboard_rows = group_leaderboard(db)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "submissions": submissions_payload,
        "leaderboard": leaderboard_rows,
    }
    (env.INDEX_ROOT / "submissions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (env.INDEX_ROOT / "leaderboard.json").write_text(json.dumps({"rows": leaderboard_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(env.INDEX_ROOT), "submissions": len(submissions_payload), "leaderboard": len(leaderboard_rows)}
