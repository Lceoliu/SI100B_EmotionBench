from __future__ import annotations

from conftest import ADMIN_PASSWORD, mutation_headers


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_register_requires_valid_invite(make_api):
    api = make_api()
    response = api.register("bob@shanghaitech.edu.cn", invite_code="WRONG")
    assert response.status_code == 400


def test_register_requires_course_email_domain(make_api):
    api = make_api()
    assert api.register("bob@example.com").status_code == 400


def test_register_rejects_short_password(make_api):
    api = make_api()
    assert api.register("bob@shanghaitech.edu.cn", password="short").status_code == 400


def test_register_rejects_duplicate_email(make_api, student):
    api = make_api()
    assert api.register("alice@shanghaitech.edu.cn").status_code == 409


def test_login_logout_round_trip(make_api, student):
    api = make_api()
    assert api.login("alice@shanghaitech.edu.cn", "wrong-password").status_code == 401
    assert api.login("ALICE@shanghaitech.edu.cn", "student-password").status_code == 200
    assert api.get("/api/session").json()["user"]["email"] == "alice@shanghaitech.edu.cn"
    assert api.post("/api/auth/logout").status_code == 200
    assert api.get("/api/session").json()["user"] is None


def test_admin_login_uses_configured_initial_password(make_api):
    api = make_api()
    response = api.login("admin", ADMIN_PASSWORD)
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_mutation_requires_csrf_token(student):
    response = student.client.patch("/api/me/profile", json={"display_name": "Alice", "group_name": ""})
    assert response.status_code == 403


def test_mutation_rejects_replayed_nonce(student):
    headers = mutation_headers(student.csrf)
    payload = {"display_name": "Alice", "group_name": "A"}
    assert student.client.patch("/api/me/profile", json=payload, headers=headers).status_code == 200
    assert student.client.patch("/api/me/profile", json=payload, headers=headers).status_code == 409


def test_mutation_rejects_cross_origin(student):
    response = student.patch(
        "/api/me/profile",
        json={"display_name": "Alice", "group_name": ""},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_disabled_user_cannot_log_in(make_api, admin, student):
    user_id = student.user["id"]
    assert admin.patch(f"/api/admin/students/{user_id}/controls", json={"disabled": True}).status_code == 200
    api = make_api()
    assert api.login("alice@shanghaitech.edu.cn", "student-password").status_code == 403


def test_auth_rate_limit(make_api, app_module):
    api = make_api()
    statuses = [api.login("nobody@shanghaitech.edu.cn", "wrong-password").status_code for _ in range(app_module.AUTH_LIMIT_PER_MINUTE + 1)]
    assert statuses[-1] == 429
    assert set(statuses[:-1]) == {401}
