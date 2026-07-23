from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.bot.runtime import APP_VERSION, configure_logging
from app.core.config import get_settings, is_local_environment, is_placeholder
from app.web.routes import STATIC_ROOT
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    config_errors = settings.bot_config_errors()
    if config_errors and not is_local_environment(settings.app_env):
        raise RuntimeError("Invalid production configuration: " + "; ".join(config_errors))
    yield
    from app.bot.max_webhook import close_webhook_runtime

    close_webhook_runtime()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not is_placeholder(settings.sentry_dsn):
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            release=APP_VERSION,
            send_default_pii=False,
        )
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(web_router)
    app.mount("/miniapp/static", StaticFiles(directory=STATIC_ROOT / "miniapp"), name="miniapp")
    return app


app = create_app()
