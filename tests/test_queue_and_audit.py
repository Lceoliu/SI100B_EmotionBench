from __future__ import annotations

from conftest import make_onnx, set_status


def test_queue_positions_follow_worker_order(app_module, make_student, client):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "B组")
    first = alice.submit(make_onnx()).json()["submission"]["id"]
    second = bob.submit(make_onnx()).json()["submission"]["id"]
    third = alice.submit(make_onnx(), mode="dry-run").json()["submission"]["id"]

    positions = {row["id"]: row["queue_position"] for row in alice.get("/api/submissions/mine").json()["rows"]}
    assert positions == {first: 1, third: 3}
    assert bob.get(f"/api/me/report/{second}").json()["submission"]["queue_position"] == 2
    assert client.get("/api/queue").json() == {"queued": 3, "running": 0}

    set_status(app_module, first, "running")
    positions = {row["id"]: row["queue_position"] for row in alice.get("/api/submissions/mine").json()["rows"]}
    assert positions == {first: None, third: 2}
    assert client.get("/api/queue").json() == {"queued": 2, "running": 1}


def actions(admin, **params) -> list[dict]:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return admin.get(f"/api/admin/audit?{query}").json()["rows"]


def test_admin_actions_are_audited(app_module, admin, student):
    user_id = student.user["id"]
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    set_status(app_module, submission_id, "error")
    admin.patch("/api/admin/settings", json={"quota_per_day": 3})
    admin.patch(f"/api/admin/students/{user_id}/controls", json={"submit_disabled": True})
    admin.post(f"/api/admin/students/{user_id}/reset-password", json={"password": "reset-by-ta-1"})
    admin.post(f"/api/admin/students/{user_id}/reset-quota")
    admin.patch(f"/api/admin/students/{user_id}/group", json={"group_name": "B组"})
    admin.post(f"/api/admin/submissions/{submission_id}/rejudge")
    admin.post("/api/admin/invites", json={"code": "LAB-CODE", "label": "lab"})

    rows = actions(admin)
    assert [row["action"] for row in rows[:7]] == [
        "invite.create",
        "submission.rejudge",
        "group.assign",
        "student.reset_quota",
        "student.reset_password",
        "student.controls",
        "settings.update",
    ]
    assert all(row["actor_email"] == "admin" and row["actor_role"] == "admin" for row in rows[:7])
    group_change = rows[2]
    assert group_change["target"] == "user alice@shanghaitech.edu.cn"
    assert group_change["detail"] == {"previous": "A组", "current": "B组"}
    assert rows[1]["detail"]["previous_status"] == "error"
    assert rows[6]["detail"] == {"quota_per_day": 3}
    assert "reset-by-ta-1" not in str(rows)


def test_student_group_and_password_changes_are_audited(admin, student):
    student.set_group("C组")
    student.post("/api/me/password", json={"current_password": "student-password", "new_password": "new-password-1"})
    rows = actions(admin)
    assert rows[0]["action"] == "password.change"
    assert rows[0]["actor_email"] == "alice@shanghaitech.edu.cn"
    assert rows[1]["action"] == "group.self_change"
    assert rows[1]["target"] == "user alice@shanghaitech.edu.cn"
    assert rows[1]["detail"] == {"previous": "A组", "current": "C组"}
    assert "new-password-1" not in str(rows)
    registered = actions(admin, action="user.register")
    assert [row["target"] for row in registered] == ["user alice@shanghaitech.edu.cn"]


def test_unchanged_group_is_not_audited(admin, student):
    before = len(actions(admin, action="group.self_change"))
    student.set_group("A组")
    assert len(actions(admin, action="group.self_change")) == before


def test_deleting_a_submission_is_audited(admin, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    admin.delete(f"/api/admin/submissions/{submission_id}")
    entry = actions(admin, action="submission.delete")[0]
    assert entry["target"] == f"submission #{submission_id}"
    assert entry["detail"]["owner"] == "alice@shanghaitech.edu.cn"


def test_bulk_group_assignment_skips_bad_ids_and_is_audited(admin, student):
    response = admin.post(
        "/api/admin/groups/bulk",
        json={"assignments": [{"user_id": "not-a-number", "group_name": "X"}, {"user_id": student.user["id"], "group_name": "D组"}]},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    entry = actions(admin, action="group.bulk_assign")[0]
    assert entry["detail"]["changes"] == [{"user": "alice@shanghaitech.edu.cn", "previous": "A组", "current": "D组"}]


def test_audit_log_is_admin_only(student):
    assert student.get("/api/admin/audit").status_code == 403
