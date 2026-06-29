from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
