"""Authentication, CSRF/replay protection, rate limiting and request hardening."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import load_config
from app.db import get_db
from app.models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DOWNLOAD_EVENTS: defaultdict[str, deque[float]] = defaultdict(deque)
AUTH_EVENTS: defaultdict[str, deque[float]] = defaultdict(deque)
MUTATION_NONCES: defaultdict[str, deque[tuple[str, float]]] = defaultdict(deque)

MAX_JSON_BODY_BYTES = 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return str(token)


def client_key(request: Request, scope: str) -> str:
    # Never read X-Forwarded-For here: clients can forge it. uvicorn already replaces
    # request.client with the forwarded address when the peer is in FORWARDED_ALLOW_IPS.
    ip = request.client.host if request.client else "unknown"
    return f"{scope}:{ip}"


def check_rate_limit(events: defaultdict[str, deque[float]], key: str, limit: int, window_seconds: int = 60) -> None:
    now = time.time()
    bucket = events[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
    bucket.append(now)


def verify_same_origin(request: Request) -> None:
    host = request.headers.get("host")
    if not host:
        return
    for header_name in ("origin", "referer"):
        value = request.headers.get(header_name)
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.netloc and parsed.netloc != host:
            raise HTTPException(status_code=403, detail="请求来源不合法。")


def verify_mutation_request(request: Request) -> None:
    verify_same_origin(request)
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token")
    if not expected or not supplied or not secrets.compare_digest(str(expected), str(supplied)):
        raise HTTPException(status_code=403, detail="安全令牌无效，请刷新页面后重试。")

    nonce = request.headers.get("x-request-nonce", "")
    if len(nonce) < 12 or len(nonce) > 128:
        raise HTTPException(status_code=403, detail="请求 nonce 无效。")
    try:
        request_time = int(request.headers.get("x-request-time", "0")) / 1000
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="请求时间戳无效。") from exc
    now = time.time()
    if abs(now - request_time) > 300:
        raise HTTPException(status_code=403, detail="请求已过期，请刷新页面后重试。")

    key = f"{request.session.get('user_id', 'anon')}:{str(expected)[:16]}"
    seen = MUTATION_NONCES[key]
    while seen and seen[0][1] <= now - 300:
        seen.popleft()
    if any(item == nonce for item, _ in seen):
        raise HTTPException(status_code=409, detail="检测到重复请求，请刷新页面后重试。")
    seen.append((nonce, now))


def start_session(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    request.session["session_version"] = user.session_version or 0


def revoke_other_sessions(request: Request | None, user: User) -> None:
    """Invalidate every existing login of `user`; keep `request` signed in if given."""
    user.session_version = (user.session_version or 0) + 1
    if request is not None:
        request.session["session_version"] = user.session_version


def session_is_current(request: Request, user: User) -> bool:
    return int(request.session.get("session_version", 0)) == (user.session_version or 0)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录。")
    user = db.get(User, int(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="登录状态已失效。")
    if user.disabled:
        request.session.clear()
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系 TA。")
    if not session_is_current(request, user):
        request.session.clear()
        raise HTTPException(status_code=401, detail="密码已修改，请重新登录。")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要 TA 管理员权限。")
    return user


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


class RequestBodyTooLarge(HTTPException):
    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=f"请求体过大（上限 {limit / 1024 / 1024:.0f} MB）。")


def max_request_body_bytes(path: str) -> int:
    if path == "/api/submissions":
        try:
            max_weight_mb = float(load_config().get("max_weight_mb", 200))
        except (TypeError, ValueError):
            max_weight_mb = 200.0
        return int(max_weight_mb * 1024 * 1024) + MULTIPART_OVERHEAD_BYTES
    return MAX_JSON_BODY_BYTES


class RequestSizeLimitMiddleware:
    """Reject oversized bodies before they are spooled to disk or read into memory."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        limit = max_request_body_bytes(scope["path"])
        content_length = dict(scope["headers"]).get(b"content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > limit:
            await self._reject(scope, receive, send, limit)
            return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestBodyTooLarge(limit)
            return message

        async def tracking_send(message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, send, limit)

    @staticmethod
    async def _reject(scope, receive, send, limit: int) -> None:
        error = RequestBodyTooLarge(limit)
        response = JSONResponse({"detail": error.detail}, status_code=error.status_code, headers={"Connection": "close"})
        await response(scope, receive, send)
