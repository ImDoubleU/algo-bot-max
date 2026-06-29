from app.core.config import Settings


def test_settings_defaults_are_local_safe() -> None:
    settings = Settings()

    assert settings.app_env == "local"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.max_api_base.startswith("https://")
