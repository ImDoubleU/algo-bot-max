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
PLACEHOLDER_FRAGMENTS = {
    "change_db_password",
    "change_to_",
    "bot.example.ru",
}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_VALUES or any(
        fragment in normalized for fragment in PLACEHOLDER_FRAGMENTS
    )


def is_local_environment(value: str | None) -> bool:
    return (value or "").strip().lower() in {"local", "dev", "development", "test"}


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
    max_bot_username: str | None = Field(default=None, alias="MAX_BOT_USERNAME")
    max_api_base: str = Field(default="https://platform-api2.max.ru", alias="MAX_API_BASE")
    max_api_timeout_seconds: int = Field(default=15, alias="MAX_API_TIMEOUT_SECONDS")
    max_poll_timeout_seconds: int = Field(default=30, alias="MAX_POLL_TIMEOUT_SECONDS")
    max_backend_api_base: str | None = Field(default=None, alias="MAX_BACKEND_API_BASE")
    max_backend_timeout_seconds: int = Field(
        default=15,
        alias="MAX_BACKEND_TIMEOUT_SECONDS",
    )
    default_tenant_slug: str = Field(
        default="nizhniy-novgorod-partner-a",
        alias="DEFAULT_TENANT_SLUG",
    )
    max_miniapp_url: str | None = Field(default=None, alias="MAX_MINIAPP_URL")
    miniapp_token_ttl_seconds: int = Field(
        default=30 * 24 * 60 * 60,
        alias="MINIAPP_TOKEN_TTL_SECONDS",
        ge=300,
        le=90 * 24 * 60 * 60,
    )
    max_webapp_auth_max_age_seconds: int = Field(
        default=3600,
        alias="MAX_WEBAPP_AUTH_MAX_AGE_SECONDS",
        ge=60,
        le=24 * 60 * 60,
    )
    bot_mode: str = Field(default="long_polling", alias="BOT_MODE")
    max_webhook_url: str | None = Field(default=None, alias="MAX_WEBHOOK_URL")
    max_webhook_secret: str | None = Field(default=None, alias="MAX_WEBHOOK_SECRET")
    max_webhook_queue_size: int = Field(
        default=500,
        alias="MAX_WEBHOOK_QUEUE_SIZE",
        ge=10,
        le=10000,
    )
    max_drop_webhooks_on_start: bool = Field(
        default=False,
        alias="MAX_DROP_WEBHOOKS_ON_START",
    )
    max_order_notifications_enabled: bool = Field(
        default=True,
        alias="MAX_ORDER_NOTIFICATIONS_ENABLED",
    )
    feedback_worker_enabled: bool = Field(default=True, alias="FEEDBACK_WORKER_ENABLED")
    feedback_worker_interval_seconds: int = Field(
        default=60,
        alias="FEEDBACK_WORKER_INTERVAL_SECONDS",
        ge=15,
        le=3600,
    )

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
    courses_json_path: str = Field(default="data/courses.json", alias="COURSES_JSON_PATH")

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
        production_like = not is_local_environment(self.app_env)
        bot_mode = self.bot_mode.strip().lower()
        if is_placeholder(self.max_bot_token):
            errors.append("MAX_BOT_TOKEN is not configured")
        if production_like and is_placeholder(self.app_secret_key):
            errors.append("APP_SECRET_KEY must be configured outside local development")
        elif production_like and len(self.app_secret_key.strip()) < 32:
            errors.append("APP_SECRET_KEY must contain at least 32 characters in production")
        if is_placeholder(self.default_tenant_slug):
            errors.append("DEFAULT_TENANT_SLUG is not configured")
        if self.max_api_timeout_seconds < 1:
            errors.append("MAX_API_TIMEOUT_SECONDS must be greater than 0")
        if self.max_poll_timeout_seconds < 1:
            errors.append("MAX_POLL_TIMEOUT_SECONDS must be greater than 0")
        if self.max_backend_timeout_seconds < 1:
            errors.append("MAX_BACKEND_TIMEOUT_SECONDS must be greater than 0")
        if self.rate_limit_max_attempts < 1:
            errors.append("RATE_LIMIT_MAX_ATTEMPTS must be greater than 0")
        if self.rate_limit_window_seconds < 1:
            errors.append("RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.rate_limit_backend.lower() not in {"memory", "redis"}:
            errors.append("RATE_LIMIT_BACKEND must be memory or redis")
        if bot_mode not in {"long_polling", "webhook"}:
            errors.append("BOT_MODE must be long_polling or webhook")
        if production_like and bot_mode != "webhook":
            errors.append("BOT_MODE must be webhook outside local development")
        if production_like and self.app_debug:
            errors.append("APP_DEBUG must be false outside local development")
        if production_like:
            if is_placeholder(self.max_backend_api_base):
                errors.append("MAX_BACKEND_API_BASE is required outside local development")
            if is_placeholder(self.max_miniapp_url):
                errors.append("MAX_MINIAPP_URL is required outside local development")
            elif not str(self.max_miniapp_url).startswith("https://"):
                errors.append("MAX_MINIAPP_URL must use HTTPS outside local development")
            if is_placeholder(self.database_url):
                errors.append("DATABASE_URL is not configured")
            elif not self.database_url.startswith("postgresql+asyncpg://"):
                errors.append("DATABASE_URL must use postgresql+asyncpg in production")
            if is_placeholder(self.database_sync_url):
                errors.append("DATABASE_SYNC_URL is not configured")
            elif not self.database_sync_url.startswith("postgresql+psycopg://"):
                errors.append("DATABASE_SYNC_URL must use postgresql+psycopg in production")
            if self.rate_limit_backend.lower() != "redis":
                errors.append("RATE_LIMIT_BACKEND must be redis in production")
            elif is_placeholder(self.redis_url):
                errors.append("REDIS_URL is required in production")
            if is_placeholder(self.initial_superadmin_max_user_id):
                errors.append("INITIAL_SUPERADMIN_MAX_USER_ID is required in production")
            elif (
                not str(self.initial_superadmin_max_user_id).isdigit()
                or int(str(self.initial_superadmin_max_user_id)) < 1
            ):
                errors.append("INITIAL_SUPERADMIN_MAX_USER_ID must be a positive integer")
        if bot_mode == "webhook":
            if is_placeholder(self.max_webhook_url):
                errors.append("MAX_WEBHOOK_URL is required in webhook mode")
            elif not str(self.max_webhook_url).startswith("https://"):
                errors.append("MAX_WEBHOOK_URL must use HTTPS")
            if is_placeholder(self.max_webhook_secret):
                errors.append("MAX_WEBHOOK_SECRET is required in webhook mode")
            else:
                secret = str(self.max_webhook_secret)
                if not 5 <= len(secret) <= 256 or not all(
                    char.isascii() and (char.isalnum() or char in "_-") for char in secret
                ):
                    errors.append(
                        "MAX_WEBHOOK_SECRET must contain 5-256 ASCII letters, digits, _ or -"
                    )
        return errors

    def config_warnings(self) -> list[str]:
        warnings: list[str] = []
        if is_local_environment(self.app_env) and is_placeholder(self.app_secret_key):
            warnings.append("APP_SECRET_KEY still uses a placeholder value")
        if is_placeholder(self.max_backend_api_base):
            warnings.append(
                "MAX_BACKEND_API_BASE is empty: bot can show help/status, but profile, "
                "catalog, orders and staff actions are unavailable"
            )
        if is_placeholder(self.max_miniapp_url):
            warnings.append("MAX_MINIAPP_URL is empty: miniapp link buttons will be disabled")
        if is_placeholder(self.max_bot_username):
            warnings.append(
                "MAX_BOT_USERNAME is empty: miniapp buttons will use an external HTTPS link"
            )
        if is_local_environment(self.app_env) and is_placeholder(
            self.initial_superadmin_max_user_id
        ):
            warnings.append(
                "INITIAL_SUPERADMIN_MAX_USER_ID is empty: bootstrap_superadmin CLI needs a user id"
            )
        if self.max_drop_webhooks_on_start:
            warnings.append(
                "MAX_DROP_WEBHOOKS_ON_START=true: bot will delete MAX webhooks on start"
            )
        if self.rate_limit_backend.lower() == "redis" and is_placeholder(self.redis_url):
            warnings.append("RATE_LIMIT_BACKEND=redis requires REDIS_URL")
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
            "max_api_timeout_seconds": self.max_api_timeout_seconds,
            "max_poll_timeout_seconds": self.max_poll_timeout_seconds,
            "max_bot_token": "configured" if not is_placeholder(self.max_bot_token) else "missing",
            "max_bot_username": (
                self.max_bot_username
                if not is_placeholder(self.max_bot_username)
                else "disabled"
            ),
            "max_backend_api_base": (
                self.max_backend_api_base
                if not is_placeholder(self.max_backend_api_base)
                else "disabled"
            ),
            "max_backend_timeout_seconds": self.max_backend_timeout_seconds,
            "max_miniapp_url": (
                self.max_miniapp_url if not is_placeholder(self.max_miniapp_url) else "disabled"
            ),
            "miniapp_token_ttl_seconds": self.miniapp_token_ttl_seconds,
            "max_webapp_auth_max_age_seconds": self.max_webapp_auth_max_age_seconds,
            "max_webhook_url": (
                self.max_webhook_url if not is_placeholder(self.max_webhook_url) else "disabled"
            ),
            "max_webhook_secret": (
                "configured" if not is_placeholder(self.max_webhook_secret) else "missing"
            ),
            "max_webhook_queue_size": self.max_webhook_queue_size,
            "max_drop_webhooks_on_start": self.max_drop_webhooks_on_start,
            "max_order_notifications_enabled": self.max_order_notifications_enabled,
            "feedback_worker_enabled": self.feedback_worker_enabled,
            "feedback_worker_interval_seconds": self.feedback_worker_interval_seconds,
            "database_url": "configured" if not is_placeholder(self.database_url) else "missing",
            "redis_url": "configured" if not is_placeholder(self.redis_url) else "missing",
            "rate_limit_backend": self.rate_limit_backend,
            "courses_json_path": self.courses_json_path,
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
