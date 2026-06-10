from __future__ import annotations

import ast
import io
import json
import os
import secrets
import shutil
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(os.environ.get("BENCH_ROOT", ".")).resolve()
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.yaml"))
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", ROOT / "storage")).resolve()
SUBMISSION_ROOT = STORAGE_ROOT / "submissions"
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist")).resolve()
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{STORAGE_ROOT / 'bench.db'}")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-emotion-bench-change-me")
INVITE_CODE = os.environ.get("INVITE_CODE", "SI100B-2026")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(24), default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    package_path: Mapped[str] = mapped_column(Text)
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


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

app = FastAPI(title="EmotionBench", version="0.1-dev")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)


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
    return {"id": user.id, "student_id": user.student_id, "display_name": user.display_name, "role": user.role}


def submission_payload(submission: Submission, reveal_private: bool = False) -> dict[str, Any]:
    return {
        "id": submission.id,
        "student_id": submission.user.student_id,
        "display_name": submission.user.display_name,
        "filename": submission.filename,
        "status": submission.status,
        "message": submission.message,
        "param_count": submission.param_count,
        "weight_mb": round(submission.weight_mb, 2),
        "public_score": submission.public_score,
        "private_score": submission.private_score if reveal_private else None,
        "realworld_score": submission.realworld_score if reveal_private else None,
        "final_pick": submission.final_pick,
        "created_at": now_iso(submission.created_at),
        "updated_at": now_iso(submission.updated_at),
    }


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Please sign in first.")
    user = db.get(User, int(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired.")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="TA access required.")
    return user


def parse_safetensors_header(data: bytes) -> tuple[int, dict[str, Any]]:
    if len(data) < 8:
        raise ValueError("model.safetensors is too small.")
    header_len = struct.unpack("<Q", data[:8])[0]
    if header_len <= 0 or header_len > 16 * 1024 * 1024:
        raise ValueError("Invalid safetensors header length.")
    header_end = 8 + header_len
    if len(data) < header_end:
        raise ValueError("Incomplete safetensors header.")
    header = json.loads(data[8:header_end].decode("utf-8"))
    dtype_sizes = {
        "F64": 8,
        "F32": 4,
        "F16": 2,
        "BF16": 2,
        "I64": 8,
        "I32": 4,
        "I16": 2,
        "I8": 1,
        "U8": 1,
        "BOOL": 1,
    }
    params = 0
    for name, tensor in header.items():
        if name == "__metadata__":
            continue
        shape = tensor.get("shape")
        dtype = tensor.get("dtype")
        if not isinstance(shape, list) or dtype not in dtype_sizes:
            raise ValueError(f"Invalid tensor metadata for {name}.")
        count = 1
        for dim in shape:
            if not isinstance(dim, int) or dim < 0:
                raise ValueError(f"Invalid tensor shape for {name}.")
            count *= dim
        params += count
    return params, header


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


def validate_package(file_bytes: bytes, filename: str) -> dict[str, Any]:
    cfg = load_config()
    max_weight_mb = float(cfg.get("max_weight_mb", 200))
    max_params = int(cfg.get("max_params", 50_000_000))
    if len(file_bytes) > (max_weight_mb + 20) * 1024 * 1024:
        raise ValueError(f"Archive is larger than the configured {max_weight_mb:.0f} MB limit.")

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]
        unsafe = [name for name in names if name.startswith("/") or ".." in Path(name).parts]
        if unsafe:
            raise ValueError("Archive contains unsafe paths.")
        basenames = {Path(name).name: name for name in names}
        if "model.py" not in basenames or "model.safetensors" not in basenames:
            raise ValueError("Archive must contain model.py and model.safetensors.")

        source = zf.read(basenames["model.py"]).decode("utf-8")
        validate_model_py(source)
        weights = zf.read(basenames["model.safetensors"])
        param_count, header = parse_safetensors_header(weights)
        weight_mb = len(weights) / 1024 / 1024
        if weight_mb > max_weight_mb:
            raise ValueError(f"model.safetensors is {weight_mb:.1f} MB; limit is {max_weight_mb:.0f} MB.")
        if param_count > max_params:
            raise ValueError(f"Model has {param_count:,} parameters; limit is {max_params:,}.")
    return {"param_count": param_count, "weight_mb": weight_mb, "tensor_count": len(header)}

def seed_demo_data(db: Session) -> None:
    if db.scalar(select(func.count(User.id))) > 0:
        return
    users = [
        User(student_id="TA", display_name="Teaching Assistant", role="admin", password_hash=pwd_context.hash("demo")),
        User(student_id="2026-001", display_name="Baseline CNN", role="student", password_hash=pwd_context.hash("demo")),
        User(student_id="2026-014", display_name="ResNet Lite", role="student", password_hash=pwd_context.hash("demo")),
        User(student_id="2026-027", display_name="ViT Small", role="student", password_hash=pwd_context.hash("demo")),
    ]
    db.add_all(users)
    db.flush()
    demo_rows = [
        (users[1], "baseline_cnn.zip", "passed", 0.612, 1_840_000, 18.4),
        (users[2], "resnet_lite_safetensors.zip", "passed", 0.741, 11_240_000, 84.7),
        (users[3], "vit_small_attempt3.zip", "running", None, 22_900_000, 142.5),
    ]
    for user, filename, status, score, params, mb in demo_rows:
        db.add(
            Submission(
                user_id=user.id,
                filename=filename,
                status=status,
                message="Demo record" if status == "passed" else "Evaluation container is running public split.",
                package_path="seed",
                param_count=params,
                weight_mb=mb,
                public_score=score,
            )
        )
    db.commit()


@app.on_event("startup")
def startup() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    SUBMISSION_ROOT.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
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
        "freeze_leaderboard": bool(cfg.get("freeze_leaderboard", False)),
        "reveal_private": bool(cfg.get("reveal_private", False)),
        "reveal_realworld": bool(cfg.get("reveal_realworld", False)),
        "final_pick_deadline": cfg.get("final_pick_deadline"),
    }
    return visible


@app.get("/api/session")
def session_info(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user_id = request.session.get("user_id")
    user = db.get(User, int(user_id)) if user_id else None
    return {"user": user_payload(user) if user else None}


@app.post("/api/auth/register")
async def register(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    data = await request.json()
    if data.get("invite_code") != INVITE_CODE:
        raise HTTPException(status_code=400, detail="Invalid invite code.")
    student_id = str(data.get("student_id", "")).strip()
    display_name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    if len(student_id) < 3 or len(display_name) < 2 or len(password) < 8:
        raise HTTPException(status_code=400, detail="Use a valid student id, display name, and password of at least 8 chars.")
    if db.scalar(select(User).where(User.student_id == student_id)):
        raise HTTPException(status_code=409, detail="Student id already registered.")
    user = User(student_id=student_id, display_name=display_name, password_hash=pwd_context.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return {"user": user_payload(user)}


@app.post("/api/auth/login")
async def login(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    data = await request.json()
    student_id = str(data.get("student_id", "")).strip()
    password = str(data.get("password", ""))
    user = db.scalar(select(User).where(User.student_id == student_id))
    if not user or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid student id or password.")
    request.session["user_id"] = user.id
    return {"user": user_payload(user)}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, Any]:
    request.session.clear()
    return {"ok": True}


@app.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    cfg = load_config()
    reveal_private = bool(cfg.get("reveal_private", False))
    rows = db.scalars(
        select(Submission)
        .join(User)
        .where(Submission.status.in_(["passed", "final"]))
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
    return {"rows": [submission_payload(row, reveal_private=reveal_private) | {"rank": i + 1} for i, row in enumerate(ranked)]}


@app.get("/api/submissions/mine")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at.desc())).all()
    return {"rows": [submission_payload(row, reveal_private=True) for row in rows]}


@app.post("/api/submissions")
async def create_submission(
    mode: str = Form("public"),
    package: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if mode not in {"public", "dry-run"}:
        raise HTTPException(status_code=400, detail="Unknown submission mode.")
    if not package.filename or not package.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip package.")

    cfg = load_config()
    quota = int(cfg.get("quota_per_day", 2))
    today = datetime.now(timezone.utc).date()
    today_count = db.scalar(
        select(func.count(Submission.id)).where(
            Submission.user_id == user.id,
            func.date(Submission.created_at) == today.isoformat(),
            Submission.status != "rejected",
        )
    )
    if mode == "public" and today_count >= quota:
        raise HTTPException(status_code=429, detail=f"Daily quota reached ({quota}).")

    content = await package.read()
    try:
        meta = validate_package(content, package.filename)
    except Exception as exc:
        submission = Submission(
            user_id=user.id,
            filename=Path(package.filename).name,
            status="rejected",
            message=str(exc),
            package_path="",
            param_count=0,
            weight_mb=0,
        )
        db.add(submission)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = secrets.token_hex(8)
    submit_dir = SUBMISSION_ROOT / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{user.student_id}-{token}"
    submit_dir.mkdir(parents=True, exist_ok=False)
    archive_path = submit_dir / "submission.zip"
    archive_path.write_bytes(content)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        zf.extractall(submit_dir / "package")
    (submit_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    status = "queued" if mode == "public" else "validated"
    message = "Queued for public evaluation." if mode == "public" else "Package passed static checks; not queued."
    submission = Submission(
        user_id=user.id,
        filename=Path(package.filename).name,
        status=status,
        message=message,
        package_path=str(archive_path),
        param_count=int(meta["param_count"]),
        weight_mb=float(meta["weight_mb"]),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {"submission": submission_payload(submission, reveal_private=True)}


@app.post("/api/submissions/{submission_id}/final")
def mark_final(submission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    submission = db.get(Submission, submission_id)
    if not submission or submission.user_id != user.id:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if submission.status not in {"passed", "final"}:
        raise HTTPException(status_code=400, detail="Only passed submissions can be selected as final.")
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
