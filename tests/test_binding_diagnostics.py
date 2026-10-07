import logging
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.binding_diagnostics import BindingDiagnosticsMiddleware, binding_request_id


def diagnostic_app():
    app = FastAPI()
    app.add_middleware(BindingDiagnosticsMiddleware)

    @app.get("/api/v1/miniapp/session")
    def session(fail: bool = False):
        if fail:
            raise HTTPException(503, "temporarily unavailable")
        return {"request_id": binding_request_id()}

    return app


def test_request_correlation_preserved_and_credentials_absent_from_logs(caplog):
    correlation = str(uuid4())
    caplog.set_level(logging.INFO)
    response = TestClient(diagnostic_app()).get(
        "/api/v1/miniapp/session?miniapp_token=private-launch-data",
        headers={"X-Request-ID": correlation, "X-Max-WebApp-Data": "private-signed-data"},
    )
    assert response.headers["X-Request-ID"] == correlation
    assert response.json()["request_id"] == correlation
    assert correlation in caplog.text
    server_logs = "\n".join(record.message for record in caplog.records
                            if record.name == "app.core.binding_diagnostics")
    assert "private-launch-data" not in server_logs
    assert "private-signed-data" not in server_logs


def test_untrusted_request_id_is_replaced_and_server_error_is_failed(caplog):
    caplog.set_level(logging.INFO, logger="app.core.binding_diagnostics")
    response = TestClient(diagnostic_app()).get(
        "/api/v1/miniapp/session?fail=true", headers={"X-Request-ID": "untrusted-log-text"},
    )
    UUID(response.headers["X-Request-ID"])
    assert "outcome=failed" in caplog.text
    assert "untrusted-log-text" not in caplog.text
    assert binding_request_id() == "background"
