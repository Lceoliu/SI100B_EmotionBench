"""JSON shapes returned by the API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app import env
from app.models import InviteCode, Score, Submission, User


def now_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.student_id,
        "student_id": user.student_id,
        "display_name": user.display_name,
        "role": user.role,
        "group_name": user.group_name or "",
        "disabled": bool(user.disabled),
        "submit_disabled": bool(user.submit_disabled),
        "leaderboard_hidden": bool(user.leaderboard_hidden),
        "quota_reset_at": now_iso(user.quota_reset_at),
    }


def invite_payload(invite: InviteCode) -> dict[str, Any]:
    return {
        "id": invite.id,
        "code": invite.code,
        "label": invite.label or "",
        "created_at": now_iso(invite.created_at),
    }


def submission_payload(submission: Submission) -> dict[str, Any]:
    return {
        "id": submission.id,
        "email": submission.user.student_id,
        "student_id": submission.user.student_id,
        "display_name": submission.user.display_name,
        "group_name": submission.user.group_name or "",
        "filename": submission.filename,
        "mode": submission.mode,
        "status": submission.status,
        "message": submission.message,
        "model_format": submission.model_format,
        "input_size": submission.input_size,
        "input_channels": submission.input_channels,
        "onnx_input_name": submission.onnx_input_name,
        "onnx_opset": submission.onnx_opset,
        "param_count": submission.param_count,
        "weight_mb": round(submission.weight_mb, 2),
        "public_score": submission.public_score,
        "created_at": now_iso(submission.created_at),
        "updated_at": now_iso(submission.updated_at),
    }


def score_payload(score: Score) -> dict[str, Any]:
    confusion_path = env.RESULTS_ROOT / f"submission-{score.submission_id}" / score.split / "confusion.png"
    return {
        "split": score.split,
        "macro_f1": score.macro_f1,
        "accuracy": score.accuracy,
        "ci_low": score.ci_low,
        "ci_high": score.ci_high,
        "confusion": json.loads(score.confusion_json or "[]"),
        "per_class": json.loads(score.per_class_json or "{}"),
        "confusion_url": f"/api/me/report/{score.submission_id}/confusion/{score.split}" if confusion_path.is_file() else None,
        "predictions_path": score.predictions_path,
        "updated_at": now_iso(score.updated_at),
    }


def score_summary_payload(score: Score | None) -> dict[str, Any] | None:
    if score is None:
        return None
    per_class = json.loads(score.per_class_json or "{}")
    recalls = []
    for item in per_class.values():
        if not isinstance(item, dict):
            continue
        try:
            value = float(item.get("recall"))
        except (TypeError, ValueError):
            continue
        recalls.append(value)
    return {
        "split": score.split,
        "macro_f1": score.macro_f1,
        "accuracy": score.accuracy,
        "recall": sum(recalls) / len(recalls) if recalls else None,
    }
