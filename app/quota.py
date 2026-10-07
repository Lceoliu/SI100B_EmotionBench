"""Daily formal-submission quota (counted per group) and submission gating."""

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

# Submissions that never reached a verdict on the model do not use up the quota:
# rejected uploads fail static validation, and "error" marks a server-side failure.
QUOTA_EXEMPT_STATUSES = ("rejected", "error")


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
                Submission.status.not_in(QUOTA_EXEMPT_STATUSES),
            )
        )
        or 0
    )


def group_members(db: Session, group_name: str) -> list[User]:
    if not group_name:
        return []
    return list(db.scalars(select(User).where(User.group_name == group_name).order_by(User.display_name.asc())).all())


def quota_members(db: Session, user: User) -> list[User]:
    """Everyone sharing the user's quota: the whole group, or just the user while ungrouped."""
    return group_members(db, user.group_name) or [user]


def quota_status(db: Session, user: User, cfg: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    limit = configured_quota_per_day(cfg)
    used = sum(public_submission_count_today(db, member.id, now, member.quota_reset_at) for member in quota_members(db, user))
    return {
        "scope": "group" if user.group_name else "none",
        "group_name": user.group_name or "",
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
    }


def ensure_public_submission_quota(db: Session, user: User, cfg: dict[str, Any]) -> None:
    if not user.group_name:
        raise HTTPException(status_code=403, detail="正式提交按小组计分和计次：请先在右侧“我的小组”填写小组名。未分组时只能使用测试提交。")
    status = quota_status(db, user, cfg)
    if status["used"] >= status["limit"]:
        raise HTTPException(status_code=429, detail=f"小组「{user.group_name}」今日正式提交次数已达上限（{status['limit']} 次）。")


def reset_quota_for(db: Session, user: User) -> list[User]:
    now = datetime.now(timezone.utc)
    members = quota_members(db, user)
    for member in members:
        member.quota_reset_at = now
    return members


def ensure_public_submission_open(cfg: dict[str, Any]) -> None:
    if bool(cfg.get("freeze_leaderboard", False)):
        raise HTTPException(status_code=403, detail="排行榜已锁定，暂不接受正式提交。")
    deadline = parse_deadline(cfg.get("final_pick_deadline"))
    if deadline is not None and datetime.now(timezone.utc) > deadline:
        raise HTTPException(status_code=403, detail="正式提交截止时间已过。")


def admin_student_payload(user: User, db: Session, cfg: dict[str, Any]) -> dict[str, Any]:
    status = quota_status(db, user, cfg)
    payload = user_payload(user)
    payload.update(
        {
            "daily_public_used": status["used"],
            "daily_public_quota": status["limit"],
            "daily_public_remaining": status["remaining"],
            "quota_scope": status["scope"],
        }
    )
    return payload
