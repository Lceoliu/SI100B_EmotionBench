"""Semester-specific content (course info, registration domains, labs, downloads) read from config.yaml."""

from __future__ import annotations

import re
from typing import Any

from app.config import load_file_config

GENERIC_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def _people(value: Any) -> list[dict[str, str]]:
    people = []
    for item in value or []:
        if isinstance(item, str):
            item = {"name": item}
        if isinstance(item, dict) and str(item.get("name") or "").strip():
            people.append({"name": str(item["name"]).strip(), "url": str(item.get("url") or "").strip()})
    return people


def _links(value: Any) -> list[dict[str, str]]:
    return [
        {"label": str(item["label"]).strip(), "url": str(item["url"]).strip()}
        for item in value or []
        if isinstance(item, dict) and item.get("label") and item.get("url")
    ]


def course_info(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = load_file_config() if cfg is None else cfg
    course = cfg.get("course") or {}
    domains = [str(domain).strip().lower().lstrip("@") for domain in course.get("email_domains") or [] if str(domain).strip()]
    return {
        "name": str(course.get("name") or "").strip(),
        "term": str(course.get("term") or "").strip(),
        "project_title": str(course.get("project_title") or "").strip(),
        "description": str(course.get("description") or "").strip(),
        "email_domains": domains,
        "instructors": _people(course.get("instructors")),
        "tas": _people(course.get("tas")),
        "links": _links(course.get("links")),
    }


def lectures(cfg: dict[str, Any] | None = None) -> list[dict[str, str]]:
    cfg = load_file_config() if cfg is None else cfg
    return [
        {"title": str(item["title"]), "detail": str(item.get("detail") or ""), "resource_id": str(item.get("resource") or "")}
        for item in cfg.get("lectures") or []
        if isinstance(item, dict) and item.get("title")
    ]


def resource_manifest(cfg: dict[str, Any] | None = None) -> list[dict[str, str]]:
    cfg = load_file_config() if cfg is None else cfg
    manifest = []
    for item in cfg.get("resources") or []:
        if not isinstance(item, dict) or not item.get("id") or not item.get("filename"):
            continue
        manifest.append(
            {
                "id": str(item["id"]),
                "title": str(item.get("title") or item["id"]),
                "filename": str(item["filename"]),
                "media_type": str(item.get("media_type") or "application/pdf"),
            }
        )
    return manifest


def email_allowed(email: str, domains: list[str]) -> bool:
    if not GENERIC_EMAIL_RE.fullmatch(email):
        return False
    if not domains:
        return True
    return email.rsplit("@", 1)[1] in domains


def email_requirement_text(domains: list[str]) -> str:
    if not domains:
        return "请使用有效邮箱注册。"
    return "请使用 " + " 或 ".join(f"@{domain}" for domain in domains) + " 邮箱注册。"
