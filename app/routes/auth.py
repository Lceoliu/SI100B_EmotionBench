from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import env
from app.db import get_db
from app.models import InviteCode, User
from app.payloads import user_payload
from app.security import (
    AUTH_EVENTS,
    check_rate_limit,
    client_key,
    ensure_csrf_token,
    pwd_context,
    session_is_current,
    start_session,
    verify_same_origin,
)

router = APIRouter()

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@shanghaitech\.edu\.cn$")


@router.get("/api/session")
def session_info(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user_id = request.session.get("user_id")
    user = db.get(User, int(user_id)) if user_id else None
    if user_id and (user is None or user.disabled or not session_is_current(request, user)):
        request.session.clear()
        user = None
    return {"user": user_payload(user) if user else None, "csrf_token": ensure_csrf_token(request)}


@router.post("/api/auth/register")
async def register(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_same_origin(request)
    check_rate_limit(AUTH_EVENTS, client_key(request, "auth"), env.AUTH_LIMIT_PER_MINUTE)
    data = await request.json()
    invite_code = str(data.get("invite_code") or "").strip()
    if not invite_code or not db.scalar(select(InviteCode).where(InviteCode.code == invite_code)):
        raise HTTPException(status_code=400, detail="邀请码无效。")
    student_id = str(data.get("email") or data.get("student_id") or "").strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    if not EMAIL_RE.fullmatch(student_id) or len(student_id) > 64:
        raise HTTPException(status_code=400, detail="请使用 @shanghaitech.edu.cn 邮箱注册。")
    if "@" not in student_id or len(display_name) < 2 or len(password) < env.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail="请填写有效邮箱、姓名，以及至少 8 位密码。")
    if db.scalar(select(User).where(User.student_id == student_id)):
        raise HTTPException(status_code=409, detail="该邮箱已注册。")
    user = User(student_id=student_id, display_name=display_name, password_hash=pwd_context.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    start_session(request, user)
    return {"user": user_payload(user), "csrf_token": ensure_csrf_token(request)}


@router.post("/api/auth/login")
async def login(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_same_origin(request)
    check_rate_limit(AUTH_EVENTS, client_key(request, "auth"), env.AUTH_LIMIT_PER_MINUTE)
    data = await request.json()
    student_id = str(data.get("email") or data.get("student_id") or "").strip().lower()
    password = str(data.get("password", ""))
    user = db.scalar(select(User).where(User.student_id == student_id))
    if not user or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误。")
    if user.disabled:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系 TA。")
    start_session(request, user)
    return {"user": user_payload(user), "csrf_token": ensure_csrf_token(request)}


@router.post("/api/auth/logout")
def logout(request: Request) -> dict[str, Any]:
    verify_same_origin(request)
    request.session.clear()
    return {"ok": True}
