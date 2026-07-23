from fastapi import APIRouter

from app.api.routes import access, health, max_webhook, miniapp, teaching

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(max_webhook.router, prefix="/max", tags=["MAX webhook"])
api_router.include_router(access.router, prefix="/access", tags=["access"])
api_router.include_router(miniapp.router, prefix="/miniapp", tags=["miniapp"])
api_router.include_router(teaching.router, prefix="/teaching", tags=["teaching"])
