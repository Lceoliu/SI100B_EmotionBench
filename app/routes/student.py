from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import env
from app.config import load_config
from app.db import get_db
from app.leaderboard import write_sync_index
from app.models import Score, Submission, User
from app.payloads import score_payload, submission_payload, user_payload
from app.quota import ensure_public_submission_open, ensure_public_submission_quota
from app.security import AUTH_EVENTS, check_rate_limit, client_key, current_user, pwd_context, verify_mutation_request
from app.submissions import validate_submission_file

router = APIRouter()


@router.get("/api/submissions/mine")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at.desc())).all()
    return {"rows": [submission_payload(row, reveal_private=True) for row in rows]}


@router.get("/api/me/report/{submission_id}")
def my_report(submission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    submission = db.get(Submission, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    rows = db.scalars(select(Score).where(Score.submission_id == submission_id).order_by(Score.split.asc())).all()
    return {"submission": submission_payload(submission, reveal_private=True), "scores": [score_payload(row) for row in rows]}


@router.get("/api/me/report/{submission_id}/confusion/{split}")
def my_confusion_matrix(submission_id: int, split: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    submission = db.get(Submission, submission_id)
    if not submission or (submission.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    if not db.scalar(select(Score).where(Score.submission_id == submission_id, Score.split == split)):
        raise HTTPException(status_code=404, detail="评测结果不存在。")
    path = (env.RESULTS_ROOT / f"submission-{submission_id}" / split / "confusion.png").resolve()
    if not path.is_file() or env.RESULTS_ROOT not in path.parents:
        raise HTTPException(status_code=404, detail="混淆矩阵尚未生成。")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})


@router.get("/api/me/group")
def my_group(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.group_name:
        return {"group_name": "", "mates": []}
    mates = db.scalars(
        select(User)
        .where(User.group_name == user.group_name, User.role == "student")
        .order_by(User.display_name.asc())
    ).all()
    return {"group_name": user.group_name, "mates": [user_payload(mate) for mate in mates]}


@router.patch("/api/me/profile")
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
    write_sync_index(db)
    return {"user": user_payload(user)}


@router.post("/api/me/password")
async def change_my_password(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    check_rate_limit(AUTH_EVENTS, client_key(request, "auth"), env.AUTH_LIMIT_PER_MINUTE)
    data = await request.json()
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    if not pwd_context.verify(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确。")
    if len(new_password) < env.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"新密码至少需要 {env.MIN_PASSWORD_LENGTH} 位。")
    if new_password == current_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同。")
    user.password_hash = pwd_context.hash(new_password)
    db.commit()
    return {"ok": True}


@router.post("/api/submissions")
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
    if user.submit_disabled:
        raise HTTPException(status_code=403, detail="你的提交功能已暂停，请联系 TA。")

    cfg = load_config()
    if mode == "public":
        ensure_public_submission_open(cfg)
        ensure_public_submission_quota(db, user, cfg)

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
    submit_dir = env.SUBMISSION_ROOT / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-u{user.id}-{token}"
    submit_dir.mkdir(parents=True, exist_ok=False)
    package_dir = submit_dir / "package"
    package_dir.mkdir()
    model_path = package_dir / "model.onnx"
    model_path.write_bytes(content)
    (submit_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "queued"
    message = "已加入正式评测队列。" if mode == "public" else "已加入测试沙箱兼容性检查队列。"
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


@router.post("/api/submissions/{submission_id}/final")
def mark_final(submission_id: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    ensure_public_submission_open(load_config())
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
