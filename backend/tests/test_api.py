"""API smoke tests."""

from fastapi.testclient import TestClient

from oldschool.api.app import create_app


def test_health(tmp_path):
    client = TestClient(create_app(tmp_path / "t.sqlite"))
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == 4
    assert body["app"].startswith("Oldschool")
