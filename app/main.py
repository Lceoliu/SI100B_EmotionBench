"""FastAPI application entry point: wires middleware, routers and the built frontend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import env
from app.db import Base, SessionLocal, engine, ensure_schema
from app.routes import admin, auth, public, student
from app.security import RequestSizeLimitMiddleware, add_security_headers
from app.seed import seed_initial_data


def startup() -> None:
    for path in (env.STORAGE_ROOT, env.SUBMISSION_ROOT, env.INDEX_ROOT, env.RESOURCE_ROOT, env.STORAGE_ROOT / "runtime"):
        path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    ensure_schema()
    with SessionLocal() as db:
        seed_initial_data(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(title="EmotionBench", version="0.2", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=env.SECRET_KEY, same_site="lax", https_only=env.SESSION_COOKIE_SECURE)
app.add_middleware(RequestSizeLimitMiddleware)
app.middleware("http")(add_security_headers)

for module in (public, auth, student, admin):
    app.include_router(module.router)

if (env.FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=env.FRONTEND_DIST / "assets"), name="assets")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = env.FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<html><body><h1>EmotionBench</h1><p>Frontend has not been built yet.</p></body></html>")


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa_fallback(full_path: str):
    index_path = env.FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")
