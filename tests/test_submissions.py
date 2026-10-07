from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import make_onnx, set_status


def test_valid_onnx_is_queued(student):
    response = student.submit(make_onnx())
    assert response.status_code == 200, response.text
    submission = response.json()["submission"]
    assert submission["status"] == "queued"
    assert submission["group_name"] == "A组"
    assert submission["input_channels"] == 1
    assert submission["input_size"] == 48
    assert submission["param_count"] == 48 * 48 * 7 + 7
    assert "final_pick" not in submission


def test_non_onnx_filename_is_rejected(student):
    assert student.submit(b"not a model", filename="model.zip").status_code == 400


def test_shape_mismatch_is_rejected_and_recorded(student):
    response = student.submit(make_onnx(size=64), input_size=48)
    assert response.status_code == 400
    rows = student.get("/api/submissions/mine").json()["rows"]
    assert [row["status"] for row in rows] == ["rejected"]


def test_unknown_mode_is_rejected(student):
    assert student.submit(make_onnx(), mode="private").status_code == 400


def test_ungrouped_student_can_only_use_test_mode(make_student):
    loner = make_student("Loner")
    response = loner.submit(make_onnx())
    assert response.status_code == 403
    assert "小组" in response.json()["detail"]
    assert loner.submit(make_onnx(), mode="dry-run").status_code == 200


def test_daily_quota_is_shared_by_the_group(make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    carol = make_student("Carol", "B组")
    for api in (alice, bob, alice, bob):
        assert api.submit(make_onnx()).status_code == 200
    blocked = bob.submit(make_onnx())
    assert blocked.status_code == 429
    assert "A组" in blocked.json()["detail"]
    assert alice.submit(make_onnx()).status_code == 429
    # Another group has its own quota, and test mode never consumes it.
    assert carol.submit(make_onnx()).status_code == 200
    assert alice.submit(make_onnx(), mode="dry-run").status_code == 200


def test_rejected_submissions_do_not_consume_quota(student):
    for _ in range(5):
        assert student.submit(make_onnx(size=64), input_size=48).status_code == 400
    assert student.submit(make_onnx()).status_code == 200


def test_system_errors_do_not_consume_quota(app_module, student):
    ids = [student.submit(make_onnx()).json()["submission"]["id"] for _ in range(4)]
    assert student.submit(make_onnx()).status_code == 429
    set_status(app_module, ids[0], "error")
    assert student.submit(make_onnx()).status_code == 200


def test_model_failures_still_consume_quota(app_module, student):
    ids = [student.submit(make_onnx()).json()["submission"]["id"] for _ in range(4)]
    set_status(app_module, ids[0], "failed")
    assert student.submit(make_onnx()).status_code == 429


def test_admin_quota_reset_restores_the_whole_group(admin, make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    for api in (alice, alice, bob, bob):
        assert api.submit(make_onnx()).status_code == 200
    assert alice.submit(make_onnx()).status_code == 429
    response = admin.post(f"/api/admin/students/{alice.user['id']}/reset-quota")
    assert response.status_code == 200
    assert response.json()["reset_members"] == 2
    assert response.json()["user"]["daily_public_remaining"] == 4
    assert bob.submit(make_onnx()).status_code == 200


def test_frozen_leaderboard_blocks_public_but_not_test_mode(admin, student):
    assert admin.patch("/api/admin/settings", json={"freeze_leaderboard": True}).status_code == 200
    assert student.submit(make_onnx()).status_code == 403
    assert student.submit(make_onnx(), mode="dry-run").status_code == 200


def test_past_deadline_blocks_public_submissions(admin, student):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert admin.patch("/api/admin/settings", json={"final_pick_deadline": past}).status_code == 200
    assert student.submit(make_onnx()).status_code == 403


def test_submit_disabled_user_cannot_submit(admin, student):
    assert admin.patch(f"/api/admin/students/{student.user['id']}/controls", json={"submit_disabled": True}).status_code == 200
    assert student.submit(make_onnx()).status_code == 403


def test_submissions_require_login(make_api):
    api = make_api()
    assert api.submit(make_onnx()).status_code == 401


def test_students_cannot_read_other_reports(make_student, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    other = make_student("Bob", "A组")
    assert other.get(f"/api/me/report/{submission_id}").status_code == 404
    assert student.get(f"/api/me/report/{submission_id}").status_code == 200


def test_final_pick_endpoint_is_gone(student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    assert student.post(f"/api/submissions/{submission_id}/final").status_code in (404, 405)
