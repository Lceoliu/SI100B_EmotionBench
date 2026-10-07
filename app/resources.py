"""Downloadable course resources served from storage/resources."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import env
from app.course import resource_manifest

def resource_payload(item: dict[str, str]) -> dict[str, Any]:
    path = (env.RESOURCE_ROOT / item["filename"]).resolve()
    available = path.is_file() and env.RESOURCE_ROOT in path.parents
    return {
        "id": item["id"],
        "title": item["title"],
        "filename": item["filename"],
        "media_type": item.get("media_type", "application/pdf"),
        "available": available,
        "size": path.stat().st_size if available else 0,
        "download_url": f"/api/resources/{item['id']}/download" if available else None,
    }


def resource_rows() -> list[dict[str, Any]]:
    return [resource_payload(item) for item in resource_manifest()]


def find_resource(resource_id: str) -> dict[str, str]:
    for item in resource_manifest():
        if item["id"] == resource_id:
            return item
    raise HTTPException(status_code=404, detail="资源不存在。")
