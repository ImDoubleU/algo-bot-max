from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.bot.backend_client import AccessBackendClient, BackendApiError
from app.bot.error_messages import format_backend_error
from app.services.access import AccessServiceError


@pytest.mark.parametrize("role, label", [("parent", "родитель"), ("student", "ученик")])
def test_conflict_role_survives_backend_error_response(monkeypatch, role, label):
    service_error = AccessServiceError(
        "Internal binding details", code="account_role_conflict", existing_role=role,
    )
    headers = Message()
    for name, value in service_error.response_headers.items():
        headers[name] = value

    def reject(*args, **kwargs):
        raise HTTPError(
            "https://backend.invalid/access/links", 400, "Bad Request", headers,
            BytesIO(b'{"detail": "Internal binding details"}'),
        )

    monkeypatch.setattr("app.bot.backend_client.request.urlopen", reject)
    client = AccessBackendClient("https://backend.invalid")
    with pytest.raises(BackendApiError) as captured:
        client.resolve_contact(tenant_slug="bor", contact_id="123", max_user_id=77)

    assert captured.value.existing_role == role
    assert captured.value.error_code == "account_role_conflict"
    message = format_backend_error(captured.value)
    assert message.startswith(f"Этот аккаунт MAX уже подключён как {label}.")
    assert "Internal binding details" not in message


@pytest.mark.parametrize("role", [None, "invalid"])
def test_unknown_role_is_not_exposed_or_guessed(role):
    error = AccessServiceError("failure", existing_role=role)
    assert error.response_headers == {"X-Access-Error-Code": "binding_failed"}
    message = format_backend_error(BackendApiError(
        "failure", error_code="account_role_conflict", existing_role=role,
    ))
    assert "уже подключён с другой ролью" in message
    assert "invalid" not in message
