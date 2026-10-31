from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # Register all six tables before create_all.
from app.api import audit, debug, findings, quick_check, scans, sites
from app.config import settings
from app.db import Base, engine
from app.replay import router as replay_router
from app.schemas import ErrorResponse, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # shortcut: create missing tables only; add migrations before changing persisted schemas.
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="GuardBit", version="0.1.0", debug=settings.DEBUG, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGIN.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

for router in (quick_check.router, sites.router, scans.router, findings.router, audit.router):
    app.include_router(
        router,
        responses={
            code: {"model": ErrorResponse}
            for code in (400, 401, 403, 404, 429, 501)
        },
    )


app.include_router(debug.router)
app.include_router(replay_router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health():
    return {"status": "ok", "version": "0.1.0"}
