from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import env
from app.db import get_db
from app.leaderboard import group_leaderboard
from app.public_config import public_config_payload
from app.resources import find_resource, resource_rows
from app.security import DOWNLOAD_EVENTS, check_rate_limit, client_key
from app.submissions import queue_snapshot

router = APIRouter()


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "root": str(env.ROOT), "config_exists": env.CONFIG_PATH.exists(), "frontend": env.FRONTEND_DIST.exists()}


@router.get("/api/config")
def api_config() -> dict[str, Any]:
    return public_config_payload()


@router.get("/api/resources")
def api_resources() -> dict[str, Any]:
    return {"rows": resource_rows()}


@router.api_route("/api/resources/{resource_id}/download", methods=["GET", "HEAD"])
def download_resource(resource_id: str, request: Request) -> FileResponse:
    check_rate_limit(DOWNLOAD_EVENTS, client_key(request, "download"), env.DOWNLOAD_LIMIT_PER_MINUTE)
    item = find_resource(resource_id)
    path = (env.RESOURCE_ROOT / item["filename"]).resolve()
    if not path.is_file() or env.RESOURCE_ROOT not in path.parents:
        raise HTTPException(status_code=404, detail="资源文件尚未上传。")
    return FileResponse(
        path,
        media_type=item.get("media_type", "application/pdf"),
        filename=item["filename"],
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/api/queue")
def queue_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    snapshot = queue_snapshot(db)
    return {"queued": snapshot["queued"], "running": snapshot["running"]}


@router.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"rows": group_leaderboard(db)}
