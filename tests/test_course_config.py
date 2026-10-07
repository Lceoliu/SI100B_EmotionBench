from __future__ import annotations

from conftest import TEST_ROOT


def test_config_exposes_course_and_lectures(client):
    payload = client.get("/api/config").json()
    assert payload["course"]["name"] == "SI100B"
    assert payload["course"]["term"] == "Test Term"
    assert payload["course"]["email_domains"] == ["shanghaitech.edu.cn"]
    assert payload["course"]["tas"] == [{"name": "TA One", "url": "https://example.com/ta"}, {"name": "TA Two", "url": ""}]
    assert payload["lectures"] == [{"title": "Lab 1", "detail": "Basics", "resource_id": "lab1"}]
    assert "reveal_private" not in payload


def test_registration_domains_come_from_config(make_api, extra_config):
    extra_config("course: {email_domains: [example.edu, '@other.org']}\n")
    assert make_api().register("bob@example.edu").status_code == 200
    assert make_api().register("carol@other.org").status_code == 200
    response = make_api().register("dave@shanghaitech.edu.cn")
    assert response.status_code == 400
    assert "@example.edu" in response.json()["detail"]


def test_empty_domain_list_accepts_any_valid_email(make_api, extra_config):
    extra_config("course: {email_domains: []}\n")
    assert make_api().register("someone@anywhere.io").status_code == 200
    assert make_api().register("not-an-email").status_code == 400


def test_resources_come_from_config(client):
    resource_dir = TEST_ROOT / "storage" / "resources"
    resource_dir.mkdir(parents=True, exist_ok=True)
    (resource_dir / "lab1.pdf").write_bytes(b"%PDF-1.4 test")
    rows = {row["id"]: row for row in client.get("/api/resources").json()["rows"]}
    assert set(rows) == {"lab1", "student-kit", "escape"}
    assert rows["lab1"]["available"] is True
    assert rows["student-kit"]["available"] is False
    assert rows["escape"]["available"] is False

    assert client.get("/api/resources/lab1/download").content == b"%PDF-1.4 test"
    assert client.get("/api/resources/escape/download").status_code == 404
    assert client.get("/api/resources/unknown/download").status_code == 404
