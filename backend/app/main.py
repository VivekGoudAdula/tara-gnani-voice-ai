"""FastAPI application entrypoint for TARA backend service."""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import close_db, get_db, init_db
from app.routers.auth import router as auth_router
from app.routers.customers import router as customers_router
from app.routers.leads import router as leads_router
from app.routers.products import router as products_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.app_env != "development" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Silence verbose PyMongo / Motor heartbeat debug output
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)

logger = logging.getLogger("tara.app")



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context managing database initialization, recovery, and cleanup."""
    logger.info("Starting TARA application service...")
    await init_db()
    try:
        from app.services.campaign_scheduler import recover_interrupted_campaigns, start_campaign_scheduler
        db = get_db()
        await recover_interrupted_campaigns(db)
        start_campaign_scheduler(poll_interval_seconds=15.0)
    except Exception as exc:
        logger.warning("Campaign scheduler initialization deferred or failed: %s", exc)

    yield
    logger.info("Shutting down TARA application service...")
    try:
        from app.services.campaign_scheduler import stop_campaign_scheduler
        stop_campaign_scheduler()
    except Exception:
        pass
    await close_db()


app = FastAPI(
    title="TARA API",
    description="Targeted Acquisition & Reach Agent - Voice-First Outreach Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Vite development and frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint reporting application and MongoDB connectivity status.
    """
    try:
        db = get_db()
        await db.command("ping")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.error("Health check database ping failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure",
        )


from app.routers.audit import router as audit_router
from app.routers.campaigns import router as campaigns_router
from app.routers.communication import router as communication_router
from app.routers.data_import import router as data_import_router
from app.routers.media_streams import router as media_streams_router
from app.routers.outcomes import router as outcomes_router
from app.routers.scoring import router as scoring_router
from app.routers.webhooks import router as webhooks_router
from app.routers.workspace import router as workspace_router

# Register tenant-scoped and public webhook API routers
app.include_router(auth_router, prefix="/api")
app.include_router(leads_router, prefix="/api")
app.include_router(customers_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(scoring_router, prefix="/api")
app.include_router(campaigns_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(communication_router, prefix="/api")
app.include_router(media_streams_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(outcomes_router, prefix="/api")
app.include_router(data_import_router, prefix="/api")
app.include_router(audit_router, prefix="/api")




if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
