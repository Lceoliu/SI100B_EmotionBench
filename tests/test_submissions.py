from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import make_onnx


def test_valid_onnx_is_queued(student):
    response = student.submit(make_onnx())
    assert response.status_code == 200, response.text
    submission = response.json()["submission"]
    assert submission["status"] == "queued"
    assert submission["input_channels"] == 1
    assert submission["input_size"] == 48
    assert submission["param_count"] == 48 * 48 * 7 + 7


def test_non_onnx_filename_is_rejected(student):
    assert student.submit(b"not a model", filename="model.zip").status_code == 400


def test_shape_mismatch_is_rejected_and_recorded(student):
    response = student.submit(make_onnx(size=64), input_size=48)
    assert response.status_code == 400
    rows = student.get("/api/submissions/mine").json()["rows"]
    assert [row["status"] for row in rows] == ["rejected"]


def test_unknown_mode_is_rejected(student):
    assert student.submit(make_onnx(), mode="private").status_code == 400


def test_daily_quota_counts_public_submissions_only(student):
    for _ in range(4):
        assert student.submit(make_onnx()).status_code == 200
    assert student.submit(make_onnx()).status_code == 429
    # Test-mode submissions do not consume the formal quota.
    assert student.submit(make_onnx(), mode="dry-run").status_code == 200


def test_rejected_submissions_do_not_consume_quota(student):
    for _ in range(5):
        assert student.submit(make_onnx(size=64), input_size=48).status_code == 400
    assert student.submit(make_onnx()).status_code == 200


def test_admin_quota_reset_restores_submissions(admin, student):
    for _ in range(4):
        assert student.submit(make_onnx()).status_code == 200
    assert student.submit(make_onnx()).status_code == 429
    response = admin.post(f"/api/admin/students/{student.user['id']}/reset-quota")
    assert response.status_code == 200
    assert response.json()["user"]["daily_public_remaining"] == 4
    assert student.submit(make_onnx()).status_code == 200


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


def test_students_cannot_read_other_reports(make_api, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    other = make_api()
    assert other.register("bob@shanghaitech.edu.cn", display_name="Bob").status_code == 200
    assert other.get(f"/api/me/report/{submission_id}").status_code == 404
    assert student.get(f"/api/me/report/{submission_id}").status_code == 200
