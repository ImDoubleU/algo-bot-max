from fastapi.testclient import TestClient

from app.main import create_app


def test_miniapp_route_serves_html() -> None:
    client = TestClient(create_app())

    response = client.get("/miniapp")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Алгоритмика" in response.text


def test_miniapp_static_serves_assets() -> None:
    client = TestClient(create_app())

    response = client.get("/miniapp/static/app.js")

    assert response.status_code == 200
    assert "state" in response.text
