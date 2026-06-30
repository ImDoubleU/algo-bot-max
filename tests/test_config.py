from app.core.config import Settings


def test_settings_defaults_are_local_safe() -> None:
    settings = Settings()

    assert settings.app_env == "local"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.max_api_base.startswith("https://")


def test_safe_config_report_does_not_expose_secret_values() -> None:
    settings = Settings(
        APP_SECRET_KEY="secret-value",
        MAX_BOT_TOKEN="real-token",
        DEFAULT_TENANT_SLUG="tenant-a",
        MAX_BACKEND_API_BASE="http://127.0.0.1:8000/api/v1",
        MAX_MINIAPP_URL="http://127.0.0.1:8000/miniapp",
    )

    report = settings.safe_config_report()

    assert report["status"] == "ok"
    assert report["max_bot_token"] == "configured"
    assert "real-token" not in str(report)
    assert "secret-value" not in str(report)


def test_safe_config_report_flags_missing_bot_token() -> None:
    settings = Settings(MAX_BOT_TOKEN="replace_me")

    report = settings.safe_config_report()

    assert report["status"] == "degraded"
    assert "MAX_BOT_TOKEN is not configured" in report["errors"]


def test_config_warnings_include_missing_initial_superadmin() -> None:
    settings = Settings(
        APP_SECRET_KEY="secret-value",
        MAX_BOT_TOKEN="real-token",
        INITIAL_SUPERADMIN_MAX_USER_ID="replace_me",
    )

    assert any("INITIAL_SUPERADMIN_MAX_USER_ID" in item for item in settings.config_warnings())
