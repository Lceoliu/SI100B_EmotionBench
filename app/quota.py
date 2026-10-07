"""Daily formal-submission quota and submission gating."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import configured_quota_per_day, parse_deadline
from app.env import COURSE_TZ
from app.models import Submission, User
from app.payloads import user_payload


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def public_submission_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the current Asia/Shanghai day as naive UTC datetimes for SQLite."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    local_now = now_utc.astimezone(COURSE_TZ)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    return (
        local_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def public_submission_count_today(
    db: Session,
    user_id: int,
    now: datetime | None = None,
    reset_at: datetime | None = None,
) -> int:
    day_start_utc, day_end_utc = public_submission_day_window(now)
    effective_start = day_start_utc
    if reset_at is not None:
        reset_at_utc = utc_naive(reset_at)
        if day_start_utc <= reset_at_utc < day_end_utc:
            effective_start = max(effective_start, reset_at_utc)
    return int(
        db.scalar(
            select(func.count(Submission.id)).where(
                Submission.user_id == user_id,
                Submission.mode == "public",
                Submission.created_at >= effective_start,
                Submission.created_at < day_end_utc,
                Submission.status != "rejected",
            )
        )
        or 0
    )


def ensure_public_submission_quota(db: Session, user: User, cfg: dict[str, Any]) -> None:
    quota = configured_quota_per_day(cfg)
    today_count = public_submission_count_today(db, user.id, reset_at=user.quota_reset_at)
    if today_count >= quota:
        raise HTTPException(status_code=429, detail=f"今日正式提交次数已达上限（{quota} 次）。")


def ensure_public_submission_open(cfg: dict[str, Any]) -> None:
    if bool(cfg.get("freeze_leaderboard", False)):
        raise HTTPException(status_code=403, detail="排行榜已锁定，暂不接受正式提交。")
    deadline = parse_deadline(cfg.get("final_pick_deadline"))
    if deadline is not None and datetime.now(timezone.utc) > deadline:
        raise HTTPException(status_code=403, detail="正式提交截止时间已过。")


def admin_student_payload(user: User, db: Session, cfg: dict[str, Any]) -> dict[str, Any]:
    quota = configured_quota_per_day(cfg)
    used = public_submission_count_today(db, user.id, reset_at=user.quota_reset_at)
    payload = user_payload(user)
    payload.update(
        {
            "daily_public_used": used,
            "daily_public_quota": quota,
            "daily_public_remaining": max(0, quota - used),
        }
    )
    return payload
