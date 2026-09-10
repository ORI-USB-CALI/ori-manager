from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.db.session import get_db

app = FastAPI(
    title="ORI Manager API",
    version="0.1.0",
)

DatabaseSession = Annotated[Session, Depends(get_db)]


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
