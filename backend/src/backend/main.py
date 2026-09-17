from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.deps import DatabaseSession
from backend.api.errors import registrar_manejadores_de_errores
from backend.api.routers.aliado import router as aliado_router
from backend.api.routers.contacto_aliado import router as contacto_aliado_router
from backend.api.routers.pais import router as pais_router
from backend.core.config import settings

app = FastAPI(
    title="ORI Manager API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Rol-Usuario"],
)

registrar_manejadores_de_errores(app)
app.include_router(aliado_router)
app.include_router(contacto_aliado_router)
app.include_router(pais_router)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ORI Manager API",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def readiness_check(db: DatabaseSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return {
        "status": "ok",
        "database": "reachable",
    }
