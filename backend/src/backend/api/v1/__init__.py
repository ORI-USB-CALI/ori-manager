from fastapi import APIRouter

from backend.api.v1.aliados import router as aliados_router
from backend.api.v1.convenios import router as convenios_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(aliados_router)
api_v1_router.include_router(convenios_router)

__all__ = ["api_v1_router"]
