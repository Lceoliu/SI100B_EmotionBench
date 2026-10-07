from __future__ import annotations

import csv
import io

import pytest

from conftest import make_onnx


def mark_passed(app_module, submission_id: int, score: float) -> None:
    with app_module.SessionLocal() as db:
        submission = db.get(app_module.Submission, submission_id)
        submission.status = "passed"
        submission.public_score = score
        db.commit()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/queue"),
        ("GET", "/api/admin/students"),
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/invites"),
        ("GET", "/api/admin/leaderboard.csv"),
        ("PATCH", "/api/admin/settings"),
        ("POST", "/api/admin/sync"),
    ],
)
def test_admin_endpoints_reject_students(student, method, path):
    response = student.send(method, path, json={}) if method != "GET" else student.get(path)
    assert response.status_code == 403


def test_settings_validation(admin):
    assert admin.patch("/api/admin/settings", json={"quota_per_day": 101}).status_code == 400
    assert admin.patch("/api/admin/settings", json={"quota_per_day": "many"}).status_code == 400
    assert admin.patch("/api/admin/settings", json={"final_pick_deadline": "tomorrow"}).status_code == 400
    assert admin.patch("/api/admin/settings", json={"unknown": 1}).status_code == 400
    response = admin.patch("/api/admin/settings", json={"quota_per_day": 2})
    assert response.status_code == 200
    assert response.json()["config"]["quota_per_day"] == 2


def test_leaderboard_keeps_best_submission_per_user(app_module, make_api, admin, student):
    first = student.submit(make_onnx()).json()["submission"]["id"]
    second = student.submit(make_onnx()).json()["submission"]["id"]
    bob = make_api()
    bob.register("bob@shanghaitech.edu.cn", display_name="Bob")
    third = bob.submit(make_onnx()).json()["submission"]["id"]
    mark_passed(app_module, first, 0.5)
    mark_passed(app_module, second, 0.7)
    mark_passed(app_module, third, 0.6)

    rows = student.get("/api/leaderboard").json()["rows"]
    assert [(row["id"], row["rank"]) for row in rows] == [(second, 1), (third, 2)]

    assert admin.patch(f"/api/admin/students/{student.user['id']}/controls", json={"leaderboard_hidden": True}).status_code == 200
    rows = student.get("/api/leaderboard").json()["rows"]
    assert [row["id"] for row in rows] == [third]


def test_mark_final_requires_passed_submission(app_module, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    assert student.post(f"/api/submissions/{submission_id}/final").status_code == 400
    mark_passed(app_module, submission_id, 0.5)
    response = student.post(f"/api/submissions/{submission_id}/final")
    assert response.status_code == 200
    assert response.json()["submission"]["final_pick"] is True


def test_csv_export_neutralizes_formulas(app_module, admin, make_api):
    api = make_api()
    api.register("eve@shanghaitech.edu.cn", display_name="=HYPERLINK(1)")
    submission_id = api.submit(make_onnx()).json()["submission"]["id"]
    mark_passed(app_module, submission_id, 0.42)
    response = admin.get("/api/admin/leaderboard.csv")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))
    assert rows[0]["display_name"] == "'=HYPERLINK(1)"
    assert rows[0]["score_percent"] == "42.00"


def test_admin_delete_submission_removes_files(app_module, admin, student):
    submission = student.submit(make_onnx()).json()["submission"]
    with app_module.SessionLocal() as db:
        package_path = db.get(app_module.Submission, submission["id"]).package_path
    assert admin.delete(f"/api/admin/submissions/{submission['id']}").status_code == 200
    assert student.get("/api/submissions/mine").json()["rows"] == []
    from pathlib import Path

    assert not Path(package_path).exists()


def test_invite_management(admin, make_api):
    response = admin.post("/api/admin/invites", json={"code": "NEW-CODE", "label": "lab"})
    assert response.status_code == 200
    invite_id = response.json()["invite"]["id"]
    assert admin.post("/api/admin/invites", json={"code": "NEW-CODE"}).status_code == 409
    assert make_api().register("carol@shanghaitech.edu.cn", invite_code="NEW-CODE").status_code == 200
    assert admin.delete(f"/api/admin/invites/{invite_id}").status_code == 200
    assert make_api().register("dave@shanghaitech.edu.cn", invite_code="NEW-CODE").status_code == 400


def test_admin_cannot_be_disabled_via_student_controls(admin):
    admin_id = admin.user["id"]
    assert admin.patch(f"/api/admin/students/{admin_id}/controls", json={"disabled": True}).status_code == 400


def test_admin_password_reset_for_student(admin, student, make_api):
    user_id = student.user["id"]
    assert admin.post(f"/api/admin/students/{user_id}/reset-password", json={"password": "short"}).status_code == 400
    assert admin.post(f"/api/admin/students/{user_id}/reset-password", json={"password": "new-password-1"}).status_code == 200
    assert make_api().login("alice@shanghaitech.edu.cn", "new-password-1").status_code == 200


def test_bulk_group_assignment(admin, student):
    response = admin.post("/api/admin/groups/bulk", json={"assignments": [{"user_id": student.user["id"], "group_name": "G1"}]})
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    assert student.get("/api/me/group").json()["group_name"] == "G1"
