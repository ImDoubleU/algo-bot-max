from fastapi import APIRouter

from app.api.routes import access, health, miniapp

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(access.router, prefix="/access", tags=["access"])
api_router.include_router(miniapp.router, prefix="/miniapp", tags=["miniapp"])
