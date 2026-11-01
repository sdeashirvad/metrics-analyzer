import pytest

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_portfolio_and_dq020(client):
    overview = client.get("/api/v1/dq/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["controls"] == 36
    assert body["latest"] == {"red": 5, "amber": 2, "green": 29}
    assert body["openExceptions"] == 722
    reds = sorted(item["id"] for item in body["atRisk"] if item["status"] == "red")
    assert reds == ["DQ-001", "DQ-007", "DQ-010", "DQ-020", "DQ-025"]
    assert len([item for item in body["atRisk"] if item["status"] in {"red", "amber"}]) == 7

    detail = client.get("/api/v1/dq/controls/DQ-020")
    assert detail.status_code == 200
    control = detail.json()
    assert control["reading"]["status"] == "red"
    assert control["reading"]["asOf"] == "2026-10-28"
    assert abs(control["reading"]["value"] - 98.178) < 0.0001
    assert control["workbook"]["failed"] == 3161
    assert control["workbook"]["total"] == 173463

    exceptions = client.get("/api/v1/dq/controls/DQ-020/exceptions?status=Open&pageSize=1")
    assert exceptions.status_code == 200
    assert exceptions.json()["total"] == 130
    desks = client.get("/api/v1/dq/controls/DQ-020/desks")
    assert desks.status_code == 200
    assert desks.json()["available"] is True
    missing = client.get("/api/v1/dq/controls/DQ-999")
    assert missing.status_code == 404
    assert missing.json()["code"] == "CONTROL_NOT_FOUND"


def test_ready(client):
    ready = client.get("/api/v1/dq/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    assert "password" not in ready.text.lower()
