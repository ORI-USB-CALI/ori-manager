from fastapi import FastAPI

app = FastAPI(
    title="ORI Manager API",
    version="0.1.0",
)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ORI Manager API",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}