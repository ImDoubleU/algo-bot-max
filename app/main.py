import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.bot.runtime import APP_VERSION, configure_logging
from app.core.binding_diagnostics import BindingDiagnosticsMiddleware
from app.core.config import get_settings, is_local_environment, is_placeholder
from app.web.routes import STATIC_ROOT
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    config_errors = settings.bot_config_errors()
    if config_errors and not is_local_environment(settings.app_env):
        raise RuntimeError("Invalid production configuration: " + "; ".join(config_errors))
    if (settings.bot_mode.strip().lower() == "webhook"
            and not is_placeholder(settings.max_bot_token)):
        from app.bot.max_webhook import get_webhook_runtime

        get_webhook_runtime()
    from app.services.support import notification_loop, notifications_enabled

    support_worker = asyncio.create_task(notification_loop()) if notifications_enabled() else None
    from app.services.pending_bindings import pending_binding_loop
    pending_worker = (asyncio.create_task(pending_binding_loop())
                      if not is_local_environment(settings.app_env)
                      or not is_placeholder(settings.max_bot_token) else None)
    from app.services.activity_audit import bot_audit_loop

    audit_worker = (asyncio.create_task(bot_audit_loop())
                    if not is_local_environment(settings.app_env) else None)
    try:
        yield
    finally:
        if pending_worker:
            pending_worker.cancel()
            with suppress(asyncio.CancelledError):
                await pending_worker
        if audit_worker:
            audit_worker.cancel()
            with suppress(asyncio.CancelledError):
                await audit_worker
        if support_worker:
            support_worker.cancel()
            with suppress(asyncio.CancelledError):
                await support_worker
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
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(BindingDiagnosticsMiddleware)

    async def audited_http_exception(request, exc):
        request.state.audit_reason = "request_denied"
        request.state.audit_detail = exc.detail if isinstance(exc.detail, str) else None
        return await http_exception_handler(request, exc)

    app.add_exception_handler(StarletteHTTPException, audited_http_exception)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(web_router)
    app.mount("/miniapp/static", StaticFiles(directory=STATIC_ROOT / "miniapp"), name="miniapp")
    product_media_root = Path(settings.product_media_root).expanduser().resolve()
    product_media_root.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/media/products",
        StaticFiles(directory=product_media_root),
        name="product-media",
    )
    return app


app = create_app()
