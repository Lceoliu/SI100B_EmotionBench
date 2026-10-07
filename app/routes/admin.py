from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import env
from app.config import load_config, normalize_deadline, public_config_payload, set_setting
from app.db import get_db
from app.leaderboard import leaderboard_csv, write_sync_index
from app.models import InviteCode, Score, Submission, User
from app.payloads import invite_payload, score_payload, submission_payload, user_payload
from app.quota import admin_student_payload, reset_quota_for
from app.security import admin_user, pwd_context, revoke_other_sessions, verify_mutation_request
from app.submissions import bytes_mb, folder_size, remove_submission_artifacts

router = APIRouter(prefix="/api/admin")


@router.get("/leaderboard.csv")
def admin_leaderboard_csv(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> Response:
    stamp = datetime.now(env.COURSE_TZ).strftime("%Y%m%d-%H%M%S")
    filename = f"emotion-bench-leaderboard-{stamp}.csv"
    return Response(
        leaderboard_csv(db),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submissions/{submission_id}/report")
def admin_submission_report(submission_id: int, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    rows = db.scalars(select(Score).where(Score.submission_id == submission_id).order_by(Score.split.asc())).all()
    return {"submission": submission_payload(submission), "scores": [score_payload(row) for row in rows]}


@router.get("/queue")
def admin_queue(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(Submission).join(User).order_by(Submission.created_at.desc()).limit(100)).all()
    return {"rows": [submission_payload(row) for row in rows]}


@router.delete("/submissions/{submission_id}")
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


REJUDGE_STATUSES = {"passed", "failed", "error", "validated"}


def requeue_submission(db: Session, submission: Submission) -> None:
    db.query(Score).filter(Score.submission_id == submission.id).delete()
    submission.public_score = None
    submission.status = "queued"
    submission.message = "TA 已重新加入评测队列。"


def submission_package_exists(submission: Submission) -> bool:
    return bool(submission.package_path) and Path(submission.package_path).is_file()


@router.post("/submissions/{submission_id}/rejudge")
def admin_rejudge_submission(submission_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在。")
    if submission.status not in REJUDGE_STATUSES:
        raise HTTPException(status_code=400, detail="只有已完成、失败或系统错误的提交可以重新评测。")
    if not submission_package_exists(submission):
        raise HTTPException(status_code=400, detail="模型文件已不存在，无法重新评测。")
    requeue_submission(db, submission)
    db.commit()
    write_sync_index(db)
    return {"submission": submission_payload(submission)}


@router.post("/submissions/rejudge-errors")
def admin_rejudge_errors(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    rows = [row for row in db.scalars(select(Submission).where(Submission.status == "error")).all() if submission_package_exists(row)]
    for row in rows:
        requeue_submission(db, row)
    db.commit()
    if rows:
        write_sync_index(db)
    return {"requeued": len(rows), "ids": [row.id for row in rows]}


@router.post("/sync")
def admin_sync(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    return write_sync_index(db)


@router.patch("/settings")
async def admin_update_settings(request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    allowed = {"final_pick_deadline", "freeze_leaderboard", "quota_per_day"}
    for key in data:
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"未知设置项：{key}")
    if "final_pick_deadline" in data:
        set_setting(db, "final_pick_deadline", normalize_deadline(data.get("final_pick_deadline")))
    if "freeze_leaderboard" in data:
        set_setting(db, "freeze_leaderboard", "true" if bool(data.get("freeze_leaderboard")) else "false")
    if "quota_per_day" in data:
        try:
            quota_per_day = int(data.get("quota_per_day"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="每日正式评测次数必须是整数。") from exc
        if quota_per_day < 0 or quota_per_day > 100:
            raise HTTPException(status_code=400, detail="每日正式评测次数必须在 0 到 100 之间。")
        set_setting(db, "quota_per_day", str(quota_per_day))
    db.commit()
    return {"config": public_config_payload()}


@router.get("/dashboard")
def admin_dashboard(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    statuses = ["queued", "running", "passed", "failed", "error", "rejected", "validated"]
    queue_counts = {
        status: int(db.scalar(select(func.count(Submission.id)).where(Submission.status == status)) or 0)
        for status in statuses
    }
    recent = db.scalars(select(Submission).join(User).order_by(Submission.updated_at.desc()).limit(8)).all()
    recent_failed = db.scalars(
        select(Submission)
        .join(User)
        .where(Submission.status.in_(["failed", "error", "rejected"]))
        .order_by(Submission.updated_at.desc())
        .limit(5)
    ).all()
    gpu_path = env.STORAGE_ROOT / "runtime" / "gpu.json"
    if gpu_path.is_file():
        try:
            gpu = json.loads(gpu_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            gpu = {"available": False, "error": "GPU 状态文件无法解析。"}
    else:
        gpu = {"available": False, "error": "GPU 状态尚未上报。"}
    db_path = Path(env.DATABASE_URL.replace("sqlite:///", "")) if env.DATABASE_URL.startswith("sqlite:///") else env.STORAGE_ROOT / "bench.db"
    storage = {
        "submissions_mb": bytes_mb(folder_size(env.SUBMISSION_ROOT)),
        "results_mb": bytes_mb(folder_size(env.RESULTS_ROOT)),
        "database_mb": bytes_mb(db_path.stat().st_size) if db_path.is_file() else 0,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gpu": gpu,
        "queue_counts": queue_counts,
        "recent": [submission_payload(row) for row in recent],
        "recent_failed": [submission_payload(row) for row in recent_failed],
        "storage": storage,
    }


@router.get("/students")
def admin_students(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    cfg = load_config()
    users = db.scalars(select(User).order_by(User.role.asc(), User.group_name.asc(), User.display_name.asc())).all()
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in users:
        if item.role != "student":
            continue
        groups.setdefault(item.group_name or "未分组", []).append(admin_student_payload(item, db, cfg))
    return {
        "rows": [admin_student_payload(item, db, cfg) if item.role == "student" else user_payload(item) for item in users],
        "groups": groups,
    }


@router.patch("/students/{user_id}/disabled")
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
    write_sync_index(db)
    return {"user": user_payload(user)}


@router.patch("/students/{user_id}/controls")
async def admin_update_student_controls(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    allowed = {"disabled", "submit_disabled", "leaderboard_hidden"}
    for key in data:
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"未知控制项：{key}")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员账号不能在学生控制中修改。")
    if "disabled" in data:
        user.disabled = bool(data.get("disabled"))
    if "submit_disabled" in data:
        user.submit_disabled = bool(data.get("submit_disabled"))
    if "leaderboard_hidden" in data:
        user.leaderboard_hidden = bool(data.get("leaderboard_hidden"))
    db.commit()
    db.refresh(user)
    write_sync_index(db)
    return {"user": user_payload(user)}


@router.post("/students/{user_id}/reset-password")
async def admin_reset_password(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    data = await request.json()
    password = str(data.get("password", ""))
    if len(password) < env.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"新密码至少需要 {env.MIN_PASSWORD_LENGTH} 位。")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员密码不在学生管理中重置。")
    user.password_hash = pwd_context.hash(password)
    revoke_other_sessions(None, user)
    db.commit()
    return {"ok": True, "user": user_payload(user)}


@router.post("/students/{user_id}/reset-quota")
def admin_reset_student_quota(user_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="管理员账号没有学生提交次数。")
    members = reset_quota_for(db, user)
    db.commit()
    db.refresh(user)
    return {"user": admin_student_payload(user, db, load_config()), "reset_members": len(members)}


@router.patch("/students/{user_id}/group")
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
    write_sync_index(db)
    return {"user": user_payload(user)}


@router.post("/groups/bulk")
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
    write_sync_index(db)
    return {"updated": updated}


@router.get("/invites")
def admin_invites(_: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(InviteCode).order_by(InviteCode.created_at.desc())).all()
    return {"rows": [invite_payload(row) for row in rows]}


@router.post("/invites")
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


@router.delete("/invites/{invite_id}")
def admin_delete_invite(invite_id: int, request: Request, _: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    verify_mutation_request(request)
    invite = db.get(InviteCode, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在。")
    db.delete(invite)
    db.commit()
    return {"ok": True}
