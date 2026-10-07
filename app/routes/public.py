from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import env
from app.config import load_config, public_config_payload
from app.db import get_db
from app.leaderboard import leaderboard_rows_payload
from app.resources import RESOURCE_MANIFEST, find_resource, resource_payload
from app.security import DOWNLOAD_EVENTS, check_rate_limit, client_key

router = APIRouter()


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "root": str(env.ROOT), "config_exists": env.CONFIG_PATH.exists(), "frontend": env.FRONTEND_DIST.exists()}


@router.get("/api/config")
def api_config() -> dict[str, Any]:
    return public_config_payload()


@router.get("/api/resources")
def api_resources() -> dict[str, Any]:
    return {"rows": [resource_payload(item) for item in RESOURCE_MANIFEST]}


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


@router.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    reveal_private = bool(load_config().get("reveal_private", False))
    return {"rows": leaderboard_rows_payload(db, reveal_private=reveal_private)}
