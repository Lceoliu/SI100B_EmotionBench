from __future__ import annotations

import asyncio

from conftest import make_onnx


def test_forged_forwarded_for_does_not_bypass_rate_limit(make_api, app_module):
    api = make_api()
    statuses = [
        api.client.post(
            "/api/auth/login",
            json={"email": "nobody@shanghaitech.edu.cn", "password": "wrong-password"},
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
        ).status_code
        for index in range(app_module.AUTH_LIMIT_PER_MINUTE + 1)
    ]
    assert statuses[-1] == 429


def test_oversized_submission_is_rejected_before_parsing(app_module, student):
    with app_module.SessionLocal() as db:
        app_module.set_setting(db, "max_weight_mb", "0.001")
        db.commit()
    payload = make_onnx() + b"\x00" * (3 * 1024 * 1024)
    response = student.submit(payload)
    assert response.status_code == 413
    # Nothing was recorded or written for the rejected upload.
    assert student.get("/api/submissions/mine").json()["rows"] == []
    assert not any(app_module.SUBMISSION_ROOT.glob("*"))


def test_submission_within_limit_is_accepted(student):
    assert student.submit(make_onnx()).status_code == 200


def test_oversized_json_body_is_rejected(student):
    response = student.patch("/api/me/profile", content=b"{" + b" " * (2 * 1024 * 1024) + b"}", headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_streamed_body_without_content_length_is_cut_off(app_module):
    async def echo_app(scope, receive, send):
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": str(len(body)).encode()})

    middleware = app_module.RequestSizeLimitMiddleware(echo_app)
    chunk = b"x" * (256 * 1024)
    chunks = [chunk] * 8  # 2 MB total, above the 1 MB JSON limit
    sent: list[dict] = []

    async def receive():
        body = chunks.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(chunks)}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/api/me/profile", "headers": [], "query_string": b""}
    asyncio.run(middleware(scope, receive, send))
    assert sent[0]["status"] == 413


def test_config_has_no_placeholder_deadline(client):
    assert client.get("/api/config").json()["final_pick_deadline"] in ("", None)


def test_streamed_upload_through_app_returns_413(app_module, client):
    with app_module.SessionLocal() as db:
        app_module.set_setting(db, "max_weight_mb", "0.001")
        db.commit()
    boundary = b"bench-boundary"
    head = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="package"; filename="model.onnx"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
    )
    chunks = [head] + [b"\x00" * (512 * 1024)] * 6 + [b"\r\n--" + boundary + b"--\r\n"]
    sent: list[dict] = []

    async def receive():
        if not chunks:
            return {"type": "http.disconnect"}
        body = chunks.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(chunks)}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/submissions",
        "raw_path": b"/api/submissions",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"multipart/form-data; boundary=" + boundary)],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    asyncio.run(app_module.app(scope, receive, send))
    assert sent[0]["status"] == 413
    assert len(chunks) > 0, "the body must not be consumed past the limit"
