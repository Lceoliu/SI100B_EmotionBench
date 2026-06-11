from __future__ import annotations

import ast
import json
import os
import secrets
import shutil
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.onnx_validation import ALLOWED_CHANNELS, ALLOWED_INPUT_SIZES, metadata_payload, validate_onnx_model

ROOT = Path(os.environ.get("BENCH_ROOT", ".")).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.yaml"))
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", ROOT / "storage")).resolve()
SUBMISSION_ROOT = STORAGE_ROOT / "submissions"
INDEX_ROOT = STORAGE_ROOT / "index"
RESOURCE_ROOT = STORAGE_ROOT / "resources"
RESULTS_ROOT = Path(os.environ.get("RESULTS_ROOT", ROOT / "results")).resolve()
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist")).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{STORAGE_ROOT / 'bench.db'}")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-emotion-bench-change-me")
INVITE_CODE = os.environ.get("INVITE_CODE", "SI100B-2026")
DOWNLOAD_LIMIT_PER_MINUTE = int(os.environ.get("DOWNLOAD_LIMIT_PER_MINUTE", "40"))
AUTH_LIMIT_PER_MINUTE = int(os.environ.get("AUTH_LIMIT_PER_MINUTE", "20"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DOWNLOAD_EVENTS: defaultdict[str, deque[float]] = defaultdict(deque)
AUTH_EVENTS: defaultdict[str, deque[float]] = defaultdict(deque)
MUTATION_NONCES: defaultdict[str, deque[tuple[str, float]]] = defaultdict(deque)

RESOURCE_MANIFEST = [
    {"id": "student-kit", "title": "代码框架与样本数据集", "filename": "si100b-bench-kit-v0.2.2.zip", "media_type": "application/zip"},
    {"id": "lab1", "title": "Lab 1：环境配置与图像基础", "filename": "lab1.pdf"},
    {"id": "lab2", "title": "Lab 2：OpenCV 基本操作", "filename": "lab2.pdf"},
    {"id": "lab3", "title": "Lab 3：模型训练", "filename": "lab3.pdf"},
    {"id": "lab4", "title": "Lab 4：模型推理", "filename": "lab4.pdf"},
    {"id": "lab5", "title": "Lab 5：端到端流程", "filename": "lab5.pdf"},
    {"id": "lab6", "title": "Lab 6：Matplotlib 可视化", "filename": "lab6.pdf"},
    {"id": "lab7", "title": "Lab 7：数据标注的重要性", "filename": "lab7.pdf"},
    {"id": "lab8", "title": "Lab 8：扩展主题", "filename": "lab8.pdf"},
    {"id": "project-rules", "title": "项目评分完整规则", "filename": "face-emotion-project-rules.pdf"},
    {"id": "example-angry", "title": "公开样例：angry", "filename": "examples/angry.jpg", "media_type": "image/jpeg"},
    {"id": "example-disgust", "title": "公开样例：disgust", "filename": "examples/disgust.jpg", "media_type": "image/jpeg"},
    {"id": "example-fear", "title": "公开样例：fear", "filename": "examples/fear.jpg", "media_type": "image/jpeg"},
    {"id": "example-happy", "title": "公开样例：happy", "filename": "examples/happy.jpg", "media_type": "image/jpeg"},
    {"id": "example-neutral", "title": "公开样例：neutral", "filename": "examples/neutral.jpg", "media_type": "image/jpeg"},
    {"id": "example-sad", "title": "公开样例：sad", "filename": "examples/sad.jpg", "media_type": "image/jpeg"},
    {"id": "example-surprise", "title": "公开样例：surprise", "filename": "examples/surprise.jpg", "media_type": "image/jpeg"},
]


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="student")
    group_name: Mapped[str] = mapped_column(String(120), default="")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(24), default="public", index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    package_path: Mapped[str] = mapped_column(Text)
    model_format: Mapped[str] = mapped_column(String(24), default="onnx")
    input_size: Mapped[int] = mapped_column(Integer, default=224)
    input_channels: Mapped[int] = mapped_column(Integer, default=3)
    onnx_input_name: Mapped[str] = mapped_column(String(255), default="")
    onnx_opset: Mapped[int] = mapped_column(Integer, default=0)
    model_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    param_count: Mapped[int] = mapped_column(Integer, default=0)
    weight_mb: Mapped[float] = mapped_column(Float, default=0.0)
    public_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    private_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    realworld_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_pick: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="submissions")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    split: Mapped[str] = mapped_column(String(24), index=True)
    macro_f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    confusion_json: Mapped[str] = mapped_column(Text, default="[]")
    per_class_json: Mapped[str] = mapped_column(Text, default="{}")
    predictions_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

app = FastAPI(title="EmotionBench", version="0.1-dev")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    }


def invite_payload(invite: InviteCode) -> dict[str, Any]:
    return {
        "id": invite.id,
        "code": invite.code,
        "label": invite.label or "",
        "created_at": now_iso(invite.created_at),
    }


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return str(token)


def client_key(request: Request, scope: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
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


def submission_payload(submission: Submission, reveal_private: bool = False) -> dict[str, Any]:
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
        "private_score": submission.private_score if reveal_private else None,
        "realworld_score": submission.realworld_score if reveal_private else None,
        "final_pick": submission.final_pick,
        "created_at": now_iso(submission.created_at),
        "updated_at": now_iso(submission.updated_at),
    }


def score_payload(score: Score) -> dict[str, Any]:
    confusion_path = RESULTS_ROOT / f"submission-{score.submission_id}" / score.split / "confusion.png"
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


def write_sync_index(db: Session) -> dict[str, Any]:
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
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
    (INDEX_ROOT / "submissions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (INDEX_ROOT / "leaderboard.json").write_text(json.dumps({"rows": leaderboard_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(INDEX_ROOT), "submissions": len(submissions_payload), "leaderboard": len(leaderboard_rows)}


def remove_submission_artifacts(submission: Submission) -> None:
    if not submission.package_path or submission.package_path == "seed":
        return
    archive_path = Path(submission.package_path).resolve()
    if archive_path.is_file() and SUBMISSION_ROOT in archive_path.parents:
        submit_dir = archive_path.parent.parent if archive_path.parent.name == "package" else archive_path.parent
        if submit_dir.exists() and SUBMISSION_ROOT in submit_dir.resolve().parents:
            shutil.rmtree(submit_dir, ignore_errors=True)


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
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要 TA 管理员权限。")
    return user


FORBIDDEN_IMPORTS = {
    "ctypes",
    "multiprocessing",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "urllib",
}
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec", "input", "open"}


def validate_model_py(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"model.py syntax error: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name in FORBIDDEN_IMPORTS:
                    raise ValueError(f"Forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root_name = (node.module or "").split(".", 1)[0]
            if root_name in FORBIDDEN_IMPORTS:
                raise ValueError(f"Forbidden import: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            raise ValueError(f"Forbidden call: {node.func.id}()")


def validate_submission_file(file_bytes: bytes, filename: str, requested_input_size: int, requested_channels: int) -> dict[str, Any]:
    cfg = load_config()
    max_weight_mb = float(cfg.get("max_weight_mb", 200))
    max_params = int(cfg.get("max_params", 50_000_000))
    if not filename.lower().endswith(".onnx"):
        raise ValueError("请直接上传单个 .onnx 文件，不再接受 zip/model.py/safetensors。")
    meta = validate_onnx_model(
        file_bytes,
        requested_input_size=requested_input_size,
        requested_channels=requested_channels,
        max_model_mb=max_weight_mb,
        max_params=max_params,
    )
    return metadata_payload(meta, model_mb=len(file_bytes) / 1024 / 1024)


def resource_payload(item: dict[str, str]) -> dict[str, Any]:
    path = (RESOURCE_ROOT / item["filename"]).resolve()
    available = path.is_file() and RESOURCE_ROOT in path.parents
    return {
        "id": item["id"],
        "title": item["title"],
        "filename": item["filename"],
        "media_type": item.get("media_type", "application/pdf"),
        "available": available,
        "size": path.stat().st_size if available else 0,
        "download_url": f"/api/resources/{item['id']}/download" if available else None,
    }


def find_resource(resource_id: str) -> dict[str, str]:
    for item in RESOURCE_MANIFEST:
        if item["id"] == resource_id:
            return item
    raise HTTPException(status_code=404, detail="资源不存在。")


def seed_demo_data(db: Session) -> None:
    ensure_admin_user(db)
    ensure_default_invite_code(db)
    normalize_demo_users(db)


def ensure_default_invite_code(db: Session) -> None:
    code = INVITE_CODE.strip()
    if not code:
        return
    existing = db.scalar(select(InviteCode).where(InviteCode.code == code))
    if existing is None:
        db.add(InviteCode(code=code, label="默认邀请码"))
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
        admin = User(
            student_id="admin",
            display_name="TA 管理员",
            role="admin",
            group_name="TA",
            password_hash=pwd_context.hash("wo598053345@"),
        )
        db.add(admin)
    else:
        admin.display_name = "TA 管理员"
        admin.role = "admin"
        admin.group_name = "TA"
        admin.disabled = False
        admin.password_hash = pwd_context.hash("wo598053345@")
    db.commit()


def normalize_demo_users(db: Session) -> None:
    mappings = {
        "2026-001": ("student01@shanghaitech.edu.cn", "A组"),
        "2026-014": ("student14@shanghaitech.edu.cn", "A组"),
        "2026-027": ("student27@shanghaitech.edu.cn", "B组"),
    }
    for old_id, (email, group_name) in mappings.items():
        user = db.scalar(select(User).where(User.student_id == old_id))
        if user is None:
            continue
        existing = db.scalar(select(User).where(User.student_id == email))
        if existing is None:
            user.student_id = email
            user.group_name = group_name
        else:
            user.group_name = group_name
    db.commit()


def ensure_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).mappings().all()
        column_names = {row["name"] for row in rows}
        if rows and "group_name" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN group_name VARCHAR(120) DEFAULT '' NOT NULL"))
        if rows and "disabled" not in column_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN disabled BOOLEAN DEFAULT 0 NOT NULL"))
        rows = conn.execute(text("PRAGMA table_info(submissions)")).mappings().all()
        submission_columns = {row["name"] for row in rows}
        if rows and "mode" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN mode VARCHAR(24) DEFAULT 'public' NOT NULL"))
        if rows and "model_format" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN model_format VARCHAR(24) DEFAULT 'onnx' NOT NULL"))
        if rows and "input_size" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN input_size INTEGER DEFAULT 224 NOT NULL"))
        if rows and "input_channels" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN input_channels INTEGER DEFAULT 3 NOT NULL"))
        if rows and "onnx_input_name" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN onnx_input_name VARCHAR(255) DEFAULT '' NOT NULL"))
        if rows and "onnx_opset" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN onnx_opset INTEGER DEFAULT 0 NOT NULL"))
        if rows and "model_metadata_json" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN model_metadata_json TEXT DEFAULT '{}' NOT NULL"))


@app.on_event("startup")
def startup() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    SUBMISSION_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    RESOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    ensure_schema()
    with SessionLocal() as db:
        seed_demo_data(db)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "root": str(ROOT), "config_exists": CONFIG_PATH.exists(), "frontend": FRONTEND_DIST.exists()}


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    cfg = load_config()
    visible = {
        "quota_per_day": cfg.get("quota_per_day", 2),
        "max_params": cfg.get("max_params", 50_000_000),
        "max_weight_mb": cfg.get("max_weight_mb", 200),
        "eval_timeout_sec": cfg.get("eval_timeout_sec", 600),
        "num_classes": cfg.get("num_classes", 7),
        "submission_format": "onnx",
        "allowed_input_sizes": sorted(ALLOWED_INPUT_SIZES),
        "allowed_input_channels": sorted(ALLOWED_CHANNELS),
        "normalize": {
            "gray": {"mean": [0.5077], "std": [0.2551]},
            "rgb": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        },
        "freeze_leaderboard": bool(cfg.get("freeze_leaderboard", False)),
        "reveal_private": bool(cfg.get("reveal_private", False)),
        "reveal_realworld": bool(cfg.get("reveal_realworld", False)),
        "final_pick_deadline": cfg.get("final_pick_deadline"),
    }
    return visible


@app.get("/api/resources")
def api_resources() -> dict[str, Any]:
    return {"rows": [resource_payload(item) for item in RESOURCE_MANIFEST]}


@app.api_route("/api/resources/{resource_id}/download", methods=["GET", "HEAD"])
def download_resource(resource_id: str, request: Request) -> FileResponse:
    check_rate_limit(DOWNLOAD_EVENTS, client_key(request, "download"), DOWNLOAD_LIMIT_PER_MINUTE)
    item = find_resource(resource_id)
    path = (RESOURCE_ROOT / item["filename"]).resolve()
    if not path.is_file() or RESOURCE_ROOT not in path.parents:
        raise HTTPException(status_code=404, detail="资源文件尚未上传。")
    return FileResponse(
        path,
        media_type=item.get("media_type", "application/pdf"),
        filename=item["filename"],
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.get("/api/session")
def session_info(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user_id = request.session.get("user_id")
    user = db.get(User, int(user_id)) if user_id else None
    return {"user": user_payload(user) if user else None, "csrf_token": ensure_csrf_token(request)}


@app.post("/api/auth/register")
async def register(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_same_origin(request)
    check_rate_limit(AUTH_EVENTS, client_key(request, "auth"), AUTH_LIMIT_PER_MINUTE)
    data = await request.json()
    invite_code = str(data.get("invite_code") or "").strip()
    if not invite_code or not db.scalar(select(InviteCode).where(InviteCode.code == invite_code)):
        raise HTTPException(status_code=400, detail="邀请码无效。")
    student_id = str(data.get("email") or data.get("student_id") or "").strip().lower()
    display_name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    if not student_id.endswith("@shanghaitech.edu.cn"):
        raise HTTPException(status_code=400, detail="请使用 @shanghaitech.edu.cn 邮箱注册。")
    if "@" not in student_id or len(display_name) < 2 or len(password) < 8:
        raise HTTPException(status_code=400, detail="请填写有效邮箱、姓名，以及至少 8 位密码。")
    if db.scalar(select(User).where(User.student_id == student_id)):
        raise HTTPException(status_code=409, detail="该邮箱已注册。")
    user = User(student_id=student_id, display_name=display_name, password_hash=pwd_context.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return {"user": user_payload(user), "csrf_token": ensure_csrf_token(request)}


@app.post("/api/auth/login")
async def login(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_same_origin(request)
    check_rate_limit(AUTH_EVENTS, client_key(request, "auth"), AUTH_LIMIT_PER_MINUTE)
    data = await request.json()
    student_id = str(data.get("email") or data.get("student_id") or "").strip().lower()
    password = str(data.get("password", ""))
    user = db.scalar(select(User).where(User.student_id == student_id))
    if not user or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误。")
    if user.disabled:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系 TA。")
    request.session["user_id"] = user.id
    return {"user": user_payload(user), "csrf_token": ensure_csrf_token(request)}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, Any]:
    verify_same_origin(request)
    request.session.clear()
    return {"ok": True}


@app.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    reveal_private = bool(load_config().get("reveal_private", False))
    return {"rows": leaderboard_rows_payload(db, reveal_private=reveal_private)}


def leaderboard_rows_payload(db: Session, reveal_private: bool = False) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Submission)
        .join(User)
        .where(Submission.mode == "public", Submission.status.in_(["passed", "final"]))
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
    return [submission_payload(row, reveal_private=reveal_private) | {"rank": i + 1} for i, row in enumerate(ranked)]


@app.get("/api/submissions/mine")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at.desc())).all()
    return {"rows": [submission_payload(row, reveal_private=True) for row in rows]}


@app.get("/api/me/report/{submission_id}")
def my_report(submission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    submission = db.get(Submission, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    rows = db.scalars(select(Score).where(Score.submission_id == submission_id).order_by(Score.split.asc())).all()
    return {"submission": submission_payload(submission, reveal_private=True), "scores": [score_payload(row) for row in rows]}


@app.get("/api/me/report/{submission_id}/confusion/{split}")
def my_confusion_matrix(submission_id: int, split: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    submission = db.get(Submission, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    if not db.scalar(select(Score).where(Score.submission_id == submission_id, Score.split == split)):
        raise HTTPException(status_code=404, detail="评测结果不存在。")
    path = (RESULTS_ROOT / f"submission-{submission_id}" / split / "confusion.png").resolve()
    if not path.is_file() or RESULTS_ROOT not in path.parents:
        raise HTTPException(status_code=404, detail="混淆矩阵尚未生成。")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})


@app.get("/api/me/group")
def my_group(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.group_name:
        return {"group_name": "", "mates": []}
    mates = db.scalars(
        select(User)
        .where(User.group_name == user.group_name, User.role == "student")
        .order_by(User.display_name.asc())
    ).all()
    return {"group_name": user.group_name, "mates": [user_payload(mate) for mate in mates]}


@app.patch("/api/me/profile")
async def update_my_profile(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    display_name = str(data.get("display_name") or "").strip()
    group_name = str(data.get("group_name") or "").strip()
    if len(display_name) < 2:
        raise HTTPException(status_code=400, detail="显示名称至少需要 2 个字符。")
    if len(display_name) > 120 or len(group_name) > 120:
        raise HTTPException(status_code=400, detail="显示名称或小组名过长。")
    user.display_name = display_name
    user.group_name = group_name
    db.commit()
    db.refresh(user)
    return {"user": user_payload(user)}


@app.post("/api/submissions")
async def create_submission(
    request: Request,
    mode: str = Form("public"),
    input_size: int = Form(224),
    input_channels: int = Form(3),
    package: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    verify_mutation_request(request)
    if mode not in {"public", "dry-run"}:
        raise HTTPException(status_code=400, detail="未知提交模式。")
    if not package.filename or not package.filename.lower().endswith(".onnx"):
        raise HTTPException(status_code=400, detail="请直接上传单个 .onnx 文件。")

    cfg = load_config()
    quota = int(cfg.get("quota_per_day", 2))
    today = datetime.now(timezone.utc).date()
    today_count = db.scalar(
        select(func.count(Submission.id)).where(
            Submission.user_id == user.id,
            Submission.mode == "public",
            func.date(Submission.created_at) == today.isoformat(),
            Submission.status != "rejected",
        )
    )
    if mode == "public" and today_count >= quota:
        raise HTTPException(status_code=429, detail=f"今日提交次数已达上限（{quota} 次）。")

    content = await package.read()
    try:
        meta = validate_submission_file(content, package.filename, input_size, input_channels)
    except Exception as exc:
        submission = Submission(
            user_id=user.id,
            filename=Path(package.filename).name,
            mode=mode,
            status="rejected",
            message=str(exc),
            package_path="",
            model_format="onnx",
            input_size=input_size,
            input_channels=input_channels,
            param_count=0,
            weight_mb=0,
        )
        db.add(submission)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = secrets.token_hex(8)
    submit_dir = SUBMISSION_ROOT / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{user.student_id}-{token}"
    submit_dir.mkdir(parents=True, exist_ok=False)
    package_dir = submit_dir / "package"
    package_dir.mkdir()
    model_path = package_dir / "model.onnx"
    model_path.write_bytes(content)
    (submit_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "queued"
    message = "Queued for public evaluation." if mode == "public" else "已加入测试沙箱兼容性检查队列。"
    submission = Submission(
        user_id=user.id,
        filename=Path(package.filename).name,
        mode=mode,
        status=status,
        message=message,
        package_path=str(model_path),
        model_format="onnx",
        input_size=int(meta["input_size"]),
        input_channels=int(meta["input_channels"]),
        onnx_input_name=str(meta["input_name"]),
        onnx_opset=int(meta["opset"]),
        model_metadata_json=json.dumps(meta.get("metadata_props", {}), ensure_ascii=False),
        param_count=int(meta["param_count"]),
        weight_mb=float(meta["weight_mb"]),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {"submission": submission_payload(submission, reveal_private=True)}


@app.post("/api/submissions/{submission_id}/final")
def mark_final(submission_id: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    submission = db.get(Submission, submission_id)
    if not submission or submission.user_id != user.id:
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    if submission.status not in {"passed", "final"}:
        raise HTTPException(status_code=400, detail="只有已通过的提交可以设为最终提交。")
    db.query(Submission).filter(Submission.user_id == user.id).update({Submission.final_pick: False})
    submission.final_pick = True
    submission.status = "final"
    db.commit()
    db.refresh(submission)
    return {"submission": submission_payload(submission, reveal_private=True)}


@app.get("/api/admin/queue")
def admin_queue(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Submission).join(User).order_by(Submission.created_at.desc()).limit(100)).all()
    return {"rows": [submission_payload(row, reveal_private=True) for row in rows]}


@app.delete("/api/admin/submissions/{submission_id}")
def admin_delete_submission(submission_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    remove_submission_artifacts(submission)
    db.query(Score).filter(Score.submission_id == submission_id).delete()
    db.delete(submission)
    db.commit()
    write_sync_index(db)
    return {"ok": True}


@app.post("/api/admin/sync")
def admin_sync(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    return write_sync_index(db)


@app.get("/api/admin/students")
def admin_students(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    users = db.scalars(select(User).order_by(User.role.asc(), User.group_name.asc(), User.display_name.asc())).all()
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in users:
        if item.role != "student":
            continue
        groups.setdefault(item.group_name or "未分组", []).append(user_payload(item))
    return {"rows": [user_payload(item) for item in users], "groups": groups}


@app.patch("/api/admin/students/{user_id}/disabled")
async def admin_update_disabled(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员账号不能被禁用。")
    user.disabled = bool(data.get("disabled", False))
    db.commit()
    db.refresh(user)
    return {"user": user_payload(user)}


@app.post("/api/admin/students/{user_id}/reset-password")
async def admin_reset_password(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    password = str(data.get("password", ""))
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少需要 8 位。")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员密码不在学生管理中重置。")
    user.password_hash = pwd_context.hash(password)
    db.commit()
    return {"ok": True, "user": user_payload(user)}


@app.patch("/api/admin/students/{user_id}/group")
async def admin_update_group(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    group_name = str(data.get("group_name", "")).strip()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员账号不参与学生分组。")
    user.group_name = group_name
    db.commit()
    db.refresh(user)
    return {"user": user_payload(user)}


@app.post("/api/admin/groups/bulk")
async def admin_bulk_groups(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    assignments = data.get("assignments", [])
    if not isinstance(assignments, list):
        raise HTTPException(status_code=400, detail="assignments 必须是数组。")
    updated = 0
    for item in assignments:
        if not isinstance(item, dict):
            continue
        user = db.get(User, int(item.get("user_id", 0)))
        if user and user.role == "student":
            user.group_name = str(item.get("group_name", "")).strip()
            updated += 1
    db.commit()
    return {"updated": updated}


@app.get("/api/admin/invites")
def admin_invites(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(InviteCode).order_by(InviteCode.created_at.desc())).all()
    return {"rows": [invite_payload(row) for row in rows]}


@app.post("/api/admin/invites")
async def admin_create_invite(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    code = str(data.get("code") or "").strip()
    label = str(data.get("label") or "").strip()
    if len(code) < 4 or len(code) > 120:
        raise HTTPException(status_code=400, detail="邀请码长度需为 4 到 120 个字符。")
    if db.scalar(select(InviteCode).where(InviteCode.code == code)):
        raise HTTPException(status_code=409, detail="邀请码已存在。")
    invite = InviteCode(code=code, label=label)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"invite": invite_payload(invite)}


@app.delete("/api/admin/invites/{invite_id}")
def admin_delete_invite(invite_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    invite = db.get(InviteCode, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在。")
    db.delete(invite)
    db.commit()
    return {"ok": True}


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<html><body><h1>EmotionBench</h1><p>Frontend has not been built yet.</p></body></html>")


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa_fallback(full_path: str):
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")
