from __future__ import annotations

import re

import pytest

from conftest import ADMIN_PASSWORD, INVITE_CODE


def fresh_database(app_module):
    app_module.Base.metadata.drop_all(app_module.engine)
    app_module.Base.metadata.create_all(app_module.engine)


def test_admin_gets_random_password_when_none_configured(monkeypatch, capsys, app_module, make_api):
    fresh_database(app_module)
    monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with app_module.SessionLocal() as db:
        app_module.ensure_admin_user(db)
    match = re.search(r"random password: (\S+)", capsys.readouterr().err)
    assert match, "the generated password must be reported once in the server log"
    api = make_api()
    response = api.login("admin", match.group(1))
    assert response.status_code == 200
    assert response.json()["user"]["leaderboard_hidden"] is True


def test_admin_password_is_required_in_production(monkeypatch, app_module):
    fresh_database(app_module)
    monkeypatch.setattr(app_module, "IS_PRODUCTION", True)
    monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with app_module.SessionLocal() as db, pytest.raises(RuntimeError, match="ADMIN_INITIAL_PASSWORD"):
        app_module.ensure_admin_user(db)


def test_short_admin_initial_password_is_refused(monkeypatch, app_module):
    fresh_database(app_module)
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "short")
    with app_module.SessionLocal() as db, pytest.raises(RuntimeError, match="at least"):
        app_module.ensure_admin_user(db)


def test_existing_admin_password_survives_restart(app_module, make_api):
    with app_module.SessionLocal() as db:
        app_module.seed_initial_data(db)
    assert make_api().login("admin", ADMIN_PASSWORD).status_code == 200


def test_deleted_initial_invite_stays_deleted_after_restart(app_module, admin, make_api):
    invites = admin.get("/api/admin/invites").json()["rows"]
    seeded = next(row for row in invites if row["code"] == INVITE_CODE)
    assert admin.delete(f"/api/admin/invites/{seeded['id']}").status_code == 200

    with app_module.SessionLocal() as db:
        app_module.seed_initial_data(db)

    assert [row["code"] for row in admin.get("/api/admin/invites").json()["rows"]] == []
    assert make_api().register("bob@shanghaitech.edu.cn").status_code == 400


def test_changed_invite_code_is_seeded_once(monkeypatch, app_module, admin):
    monkeypatch.setattr(app_module, "INVITE_CODE", "NEXT-TERM")
    with app_module.SessionLocal() as db:
        app_module.seed_initial_data(db)
        app_module.seed_initial_data(db)
    codes = sorted(row["code"] for row in admin.get("/api/admin/invites").json()["rows"])
    assert codes == ["NEXT-TERM", INVITE_CODE]


def test_no_invite_code_is_created_without_configuration(monkeypatch, app_module):
    fresh_database(app_module)
    monkeypatch.setattr(app_module, "INVITE_CODE", "")
    with app_module.SessionLocal() as db:
        app_module.seed_initial_data(db)
        assert db.scalar(app_module.select(app_module.func.count(app_module.InviteCode.id))) == 0


def test_change_own_password(student, make_api):
    url = "/api/me/password"
    assert student.post(url, json={"current_password": "wrong-password", "new_password": "new-password-1"}).status_code == 400
    assert student.post(url, json={"current_password": "student-password", "new_password": "short"}).status_code == 400
    assert student.post(url, json={"current_password": "student-password", "new_password": "student-password"}).status_code == 400
    assert student.post(url, json={"current_password": "student-password", "new_password": "new-password-1"}).status_code == 200
    assert make_api().login("alice@shanghaitech.edu.cn", "student-password").status_code == 401
    assert make_api().login("alice@shanghaitech.edu.cn", "new-password-1").status_code == 200


def test_admin_can_change_own_password(admin, make_api):
    response = admin.post("/api/me/password", json={"current_password": ADMIN_PASSWORD, "new_password": "rotated-admin-pw"})
    assert response.status_code == 200
    assert make_api().login("admin", "rotated-admin-pw").status_code == 200


def test_change_password_requires_csrf(student):
    response = student.client.post("/api/me/password", json={"current_password": "student-password", "new_password": "new-password-1"})
    assert response.status_code == 403
