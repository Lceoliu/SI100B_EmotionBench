from __future__ import annotations

import csv
import io

from conftest import make_onnx, mark_passed


def submit_scored(app_module, api, score: float) -> int:
    submission_id = api.submit(make_onnx()).json()["submission"]["id"]
    mark_passed(app_module, submission_id, score)
    return submission_id


def test_groups_are_ranked_by_their_best_member_submission(app_module, make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    carol = make_student("Carol", "B组")
    submit_scored(app_module, alice, 0.50)
    bob_best = submit_scored(app_module, bob, 0.70)
    carol_best = submit_scored(app_module, carol, 0.60)

    rows = alice.get("/api/leaderboard").json()["rows"]
    assert [(row["rank"], row["group_name"], row["submission_id"]) for row in rows] == [(1, "A组", bob_best), (2, "B组", carol_best)]
    assert rows[0]["submitted_by"] == "Bob"
    assert rows[0]["member_count"] == 2
    assert rows[0]["best_score"] == 0.70


def test_ties_go_to_the_earlier_submission(app_module, make_student):
    first = make_student("First", "G1")
    second = make_student("Second", "G2")
    submit_scored(app_module, first, 0.5)
    submit_scored(app_module, second, 0.5)
    assert [row["group_name"] for row in first.get("/api/leaderboard").json()["rows"]] == ["G1", "G2"]


def test_hidden_members_and_unscored_runs_are_excluded(app_module, admin, make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    submit_scored(app_module, alice, 0.40)
    submit_scored(app_module, bob, 0.90)
    alice.submit(make_onnx())  # still queued, no score
    assert admin.patch(f"/api/admin/students/{bob.user['id']}/controls", json={"leaderboard_hidden": True}).status_code == 200
    rows = alice.get("/api/leaderboard").json()["rows"]
    assert [(row["group_name"], row["best_score"]) for row in rows] == [("A组", 0.40)]


def test_group_score_follows_current_membership(app_module, make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    submit_scored(app_module, bob, 0.8)
    bob.set_group("B组")
    rows = alice.get("/api/leaderboard").json()["rows"]
    assert [(row["group_name"], row["best_score"]) for row in rows] == [("B组", 0.8)]


def test_standing_explains_personal_and_group_results(app_module, make_student):
    alice = make_student("Alice", "A组")
    bob = make_student("Bob", "A组")
    carol = make_student("Carol", "B组")
    alice_best = submit_scored(app_module, alice, 0.55)
    bob_best = submit_scored(app_module, bob, 0.65)
    submit_scored(app_module, carol, 0.75)

    standing = alice.get("/api/me/group").json()
    assert standing["group_name"] == "A组"
    assert standing["personal"] == {"best_score": 0.55, "best_submission_id": alice_best}
    assert standing["group"]["rank"] == 2
    assert standing["group"]["total_groups"] == 2
    assert standing["group"]["best_score"] == 0.65
    assert standing["group"]["best_submission_id"] == bob_best
    assert standing["group"]["best_by"] == "Bob"
    assert standing["group"]["best_is_mine"] is False
    assert standing["quota"] == {"scope": "group", "group_name": "A组", "used": 2, "limit": 4, "remaining": 2}
    assert {(mate["display_name"], mate["best_score"]) for mate in standing["mates"]} == {("Alice", 0.55), ("Bob", 0.65)}

    assert bob.get("/api/me/group").json()["group"]["best_is_mine"] is True


def test_standing_for_ungrouped_student(make_student):
    loner = make_student("Loner")
    standing = loner.get("/api/me/group").json()
    assert standing["group_name"] == ""
    assert standing["group"] is None
    assert standing["personal"] is None
    assert standing["quota"]["scope"] == "none"


def test_csv_export_lists_groups(app_module, admin, make_student):
    eve = make_student("Eve", "=HYPERLINK(1)")
    mallory = make_student("Mallory", "=HYPERLINK(1)")
    submit_scored(app_module, eve, 0.42)
    submit_scored(app_module, mallory, 0.30)
    response = admin.get("/api/admin/leaderboard.csv")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))
    assert len(rows) == 1
    assert rows[0]["group_name"] == "'=HYPERLINK(1)"
    assert rows[0]["member_count"] == "2"
    assert rows[0]["submitted_by"] == "Eve"
    assert rows[0]["score_percent"] == "42.00"
    assert sorted(rows[0]["member_emails"].split("; ")) == ["eve@shanghaitech.edu.cn", "mallory@shanghaitech.edu.cn"]


def test_legacy_final_status_is_migrated(app_module, student):
    submission_id = student.submit(make_onnx()).json()["submission"]["id"]
    mark_passed(app_module, submission_id, 0.5)
    with app_module.SessionLocal() as db:
        db.get(app_module.Submission, submission_id).status = "final"
        db.commit()
    from app.db import ensure_schema

    ensure_schema()
    rows = student.get("/api/leaderboard").json()["rows"]
    assert [(row["submission_id"], row["status"]) for row in rows] == [(submission_id, "passed")]
