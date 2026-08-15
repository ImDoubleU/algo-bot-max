from fastapi import APIRouter

from app.api.routes import access, amocrm, health, max_webhook, miniapp

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(max_webhook.router, prefix="/max", tags=["MAX webhook"])
api_router.include_router(amocrm.router, prefix="/amocrm", tags=["amoCRM webhook"])
api_router.include_router(access.router, prefix="/access", tags=["access"])
api_router.include_router(miniapp.router, prefix="/miniapp", tags=["miniapp"])
