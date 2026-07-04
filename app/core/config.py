from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_VALUES = {
    "",
    "...",
    "replace_me",
    "your_token_here",
    "replace_with_local_xlsx_path",
    "replace_with_local_json_path",
}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in PLACEHOLDER_VALUES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Algo MAX Bot"
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_secret_key: str = Field(default="replace_me", alias="APP_SECRET_KEY")
    api_v1_prefix: str = "/api/v1"

    max_bot_token: str | None = Field(default=None, alias="MAX_BOT_TOKEN")
    max_api_base: str = Field(default="https://platform-api2.max.ru", alias="MAX_API_BASE")
    max_backend_api_base: str | None = Field(default=None, alias="MAX_BACKEND_API_BASE")
    default_tenant_slug: str = Field(
        default="nizhniy-novgorod-partner-a",
        alias="DEFAULT_TENANT_SLUG",
    )
    max_miniapp_url: str | None = Field(default=None, alias="MAX_MINIAPP_URL")
    bot_mode: str = Field(default="long_polling", alias="BOT_MODE")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/algo_bot_max",
        alias="DATABASE_URL",
    )
    database_sync_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/algo_bot_max",
        alias="DATABASE_SYNC_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    rate_limit_backend: str = Field(default="memory", alias="RATE_LIMIT_BACKEND")
    rate_limit_max_attempts: int = Field(default=8, alias="RATE_LIMIT_MAX_ATTEMPTS")
    rate_limit_window_seconds: int = Field(default=15 * 60, alias="RATE_LIMIT_WINDOW_SECONDS")

    initial_superadmin_max_user_id: str | None = Field(
        default=None,
        alias="INITIAL_SUPERADMIN_MAX_USER_ID",
    )
    initial_superadmin_username: str | None = Field(
        default="ImDoubleU",
        alias="INITIAL_SUPERADMIN_USERNAME",
    )

    crm_active_export_path: str | None = Field(default=None, alias="CRM_ACTIVE_EXPORT_PATH")
    crm_departed_export_path: str | None = Field(default=None, alias="CRM_DEPARTED_EXPORT_PATH")
    lms_api_base_url: str | None = Field(default=None, alias="LMS_API_BASE_URL")
    lms_api_token: str | None = Field(default=None, alias="LMS_API_TOKEN")

    google_service_account_file: str | None = Field(
        default=None,
        alias="GOOGLE_SERVICE_ACCOUNT_FILE",
    )
    google_sheets_orders_spreadsheet_id: str | None = Field(
        default=None,
        alias="GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID",
    )

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    def bot_config_errors(self) -> list[str]:
        errors: list[str] = []
        if is_placeholder(self.max_bot_token):
            errors.append("MAX_BOT_TOKEN is not configured")
        if is_placeholder(self.default_tenant_slug):
            errors.append("DEFAULT_TENANT_SLUG is not configured")
        if self.rate_limit_max_attempts < 1:
            errors.append("RATE_LIMIT_MAX_ATTEMPTS must be greater than 0")
        if self.rate_limit_window_seconds < 1:
            errors.append("RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        return errors

    def config_warnings(self) -> list[str]:
        warnings: list[str] = []
        if is_placeholder(self.app_secret_key):
            warnings.append("APP_SECRET_KEY still uses a placeholder value")
        if is_placeholder(self.max_backend_api_base):
            warnings.append(
                "MAX_BACKEND_API_BASE is empty: bot can show help/status, but profile, "
                "catalog, orders and staff actions are unavailable"
            )
        if is_placeholder(self.max_miniapp_url):
            warnings.append("MAX_MINIAPP_URL is empty: miniapp link buttons will be disabled")
        if is_placeholder(self.initial_superadmin_max_user_id):
            warnings.append(
                "INITIAL_SUPERADMIN_MAX_USER_ID is empty: bootstrap_superadmin CLI needs a user id"
            )
        if self.rate_limit_backend.lower() not in {"memory", "redis"}:
            warnings.append("RATE_LIMIT_BACKEND should be memory or redis")
        if self.rate_limit_backend.lower() == "redis" and is_placeholder(self.redis_url):
            warnings.append("RATE_LIMIT_BACKEND=redis requires REDIS_URL")
        if (
            self.app_env.lower() not in {"local", "dev", "development", "test"}
            and self.max_miniapp_url
            and self.max_miniapp_url.startswith("http://")
        ):
            warnings.append("MAX_MINIAPP_URL should use HTTPS outside local development")
        return warnings

    def safe_config_report(self) -> dict[str, Any]:
        errors = self.bot_config_errors()
        warnings = self.config_warnings()
        return {
            "status": "ok" if not errors else "degraded",
            "environment": self.app_env,
            "service": self.app_name,
            "bot_mode": self.bot_mode,
            "default_tenant_slug": self.default_tenant_slug,
            "max_api_base": self.max_api_base,
            "max_bot_token": "configured" if not is_placeholder(self.max_bot_token) else "missing",
            "max_backend_api_base": (
                self.max_backend_api_base
                if not is_placeholder(self.max_backend_api_base)
                else "disabled"
            ),
            "max_miniapp_url": (
                self.max_miniapp_url if not is_placeholder(self.max_miniapp_url) else "disabled"
            ),
            "database_url": "configured" if not is_placeholder(self.database_url) else "missing",
            "redis_url": "configured" if not is_placeholder(self.redis_url) else "missing",
            "rate_limit_backend": self.rate_limit_backend,
            "google_sheets": (
                "configured"
                if not is_placeholder(self.google_service_account_file)
                and not is_placeholder(self.google_sheets_orders_spreadsheet_id)
                else "disabled"
            ),
            "sentry": "configured" if not is_placeholder(self.sentry_dsn) else "disabled",
            "errors": errors,
            "warnings": warnings,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
