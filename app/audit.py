"""Append-only log of TA actions and grading-relevant student changes (group membership, passwords)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.payloads import now_iso


def record(db: Session, actor: User | None, action: str, target: str = "", **detail: Any) -> None:
    """Stage an audit entry; it is committed together with the change it describes."""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.student_id if actor else "",
            actor_role=actor.role if actor else "",
            action=action,
            target=target,
            detail_json=json.dumps(detail, ensure_ascii=False, default=str),
        )
    )


def user_target(user: User) -> str:
    return f"user {user.student_id}"


def recent_entries(db: Session, limit: int = 200, action: str = "") -> list[dict[str, Any]]:
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 1000)))
    if action:
        query = query.where(AuditLog.action == action)
    return [
        {
            "id": row.id,
            "created_at": now_iso(row.created_at),
            "actor_email": row.actor_email,
            "actor_role": row.actor_role,
            "action": row.action,
            "target": row.target,
            "detail": json.loads(row.detail_json or "{}"),
        }
        for row in db.scalars(query).all()
    ]
