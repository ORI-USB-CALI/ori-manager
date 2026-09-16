from fastapi import APIRouter

from backend.api.v1.aliados import router as aliados_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(aliados_router)

__all__ = ["api_v1_router"]
