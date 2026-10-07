from __future__ import annotations

import pytest

from conftest import make_onnx, mark_passed, set_status


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
        ("POST", "/api/admin/submissions/1/rejudge"),
        ("POST", "/api/admin/submissions/rejudge-errors"),
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


def test_rejudge_requeues_and_clears_old_results(app_module, admin, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    mark_passed(app_module, submission_id, 0.5)
    with app_module.SessionLocal() as db:
        db.add(app_module.Score(submission_id=submission_id, split="final", macro_f1=0.5, accuracy=0.5))
        db.commit()
    assert len(student.get("/api/leaderboard").json()["rows"]) == 1

    response = admin.post(f"/api/admin/submissions/{submission_id}/rejudge")
    assert response.status_code == 200
    assert response.json()["submission"]["status"] == "queued"
    report = student.get(f"/api/me/report/{submission_id}").json()
    assert report["scores"] == []
    assert report["submission"]["public_score"] is None
    assert student.get("/api/leaderboard").json()["rows"] == []


def test_rejudge_refuses_queued_and_rejected(app_module, admin, student):
    queued = student.submit(make_onnx()).json()["submission"]["id"]
    assert admin.post(f"/api/admin/submissions/{queued}/rejudge").status_code == 400
    student.submit(make_onnx(size=64), input_size=48)
    rejected = student.get("/api/submissions/mine").json()["rows"][0]["id"]
    assert admin.post(f"/api/admin/submissions/{rejected}/rejudge").status_code == 400
    assert admin.post("/api/admin/submissions/999/rejudge").status_code == 404


def test_rejudge_all_errors(app_module, admin, student):
    ids = [student.submit(make_onnx()).json()["submission"]["id"] for _ in range(3)]
    set_status(app_module, ids[0], "error")
    set_status(app_module, ids[1], "error")
    set_status(app_module, ids[2], "failed")
    response = admin.post("/api/admin/submissions/rejudge-errors")
    assert response.status_code == 200
    assert sorted(response.json()["ids"]) == sorted(ids[:2])
    statuses = {row["id"]: row["status"] for row in student.get("/api/submissions/mine").json()["rows"]}
    assert statuses == {ids[0]: "queued", ids[1]: "queued", ids[2]: "failed"}


def test_dashboard_counts_system_errors(app_module, admin, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    set_status(app_module, submission_id, "error")
    counts = admin.get("/api/admin/dashboard").json()["queue_counts"]
    assert counts["error"] == 1
    assert "final" not in counts
