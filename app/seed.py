"""Initial admin account and invite code created at startup."""

from __future__ import annotations

import os
import secrets
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import env
from app.config import set_setting
from app.models import InviteCode, Setting, Submission, User
from app.security import pwd_context, revoke_other_sessions


def seed_initial_data(db: Session) -> None:
    ensure_admin_user(db)
    ensure_initial_invite_code(db)


def ensure_initial_invite_code(db: Session) -> None:
    """Create the INVITE_CODE invite once; deleting it in the admin console must stick across restarts."""
    if not env.INVITE_CODE:
        return
    marker = db.get(Setting, env.SEEDED_INVITE_SETTING)
    if marker is not None and marker.value == env.INVITE_CODE:
        return
    if db.scalar(select(InviteCode).where(InviteCode.code == env.INVITE_CODE)) is None:
        db.add(InviteCode(code=env.INVITE_CODE, label="初始邀请码"))
    set_setting(db, env.SEEDED_INVITE_SETTING, env.INVITE_CODE)
    db.commit()


def ensure_admin_user(db: Session) -> None:
    legacy_ta = db.scalar(select(User).where(User.student_id == "TA"))
    if legacy_ta is not None:
        submission_count = db.scalar(select(func.count(Submission.id)).where(Submission.user_id == legacy_ta.id))
        if submission_count:
            legacy_ta.student_id = "legacy-ta"
            legacy_ta.password_hash = pwd_context.hash(secrets.token_urlsafe(24))
        else:
            db.delete(legacy_ta)
        db.flush()
    admin = db.scalar(select(User).where(User.student_id == "admin"))
    if admin is None:
        initial_password = os.environ.get("ADMIN_INITIAL_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
        if not initial_password:
            if env.IS_PRODUCTION:
                raise RuntimeError("ADMIN_INITIAL_PASSWORD must be set when creating the admin user in production.")
            initial_password = secrets.token_urlsafe(12)
            print(
                f"[emotion-bench] Created admin account 'admin' with a random password: {initial_password}\n"
                "[emotion-bench] Set ADMIN_INITIAL_PASSWORD to choose it, and change it after the first login.",
                file=sys.stderr,
                flush=True,
            )
        elif len(initial_password) < env.MIN_PASSWORD_LENGTH:
            raise RuntimeError(f"ADMIN_INITIAL_PASSWORD must be at least {env.MIN_PASSWORD_LENGTH} characters.")
        admin = User(
            student_id="admin",
            display_name="TA 管理员",
            role="admin",
            group_name="TA",
            leaderboard_hidden=True,
            password_hash=pwd_context.hash(initial_password),
        )
        db.add(admin)
    else:
        admin.display_name = "TA 管理员"
        admin.role = "admin"
        admin.group_name = "TA"
        admin.disabled = False
        admin.submit_disabled = False
        admin.leaderboard_hidden = True
        if os.environ.get("ADMIN_RESET_PASSWORD_ON_STARTUP") == "1":
            reset_password = os.environ.get("ADMIN_INITIAL_PASSWORD") or os.environ.get("ADMIN_PASSWORD")
            if not reset_password:
                raise RuntimeError("ADMIN_RESET_PASSWORD_ON_STARTUP=1 requires ADMIN_INITIAL_PASSWORD.")
            if len(reset_password) < env.MIN_PASSWORD_LENGTH:
                raise RuntimeError(f"ADMIN_INITIAL_PASSWORD must be at least {env.MIN_PASSWORD_LENGTH} characters.")
            admin.password_hash = pwd_context.hash(reset_password)
            revoke_other_sessions(None, admin)
    db.commit()
