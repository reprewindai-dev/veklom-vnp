"""Veklom VNP — canonical production entrypoint.

The application started by Docker (app.main:app) mounts only the
database-backed routers. No in-memory sample stores, random measurements,
fictional topology nodes, mocked VDF verification or dummy slashing are
reachable in production.

A legacy demo runtime remains available strictly behind
VNP_ALLOW_DEMO_DATA=true (default false) and never in production —
production startup fails closed when demo data is enabled.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import engine, get_db
from app.db.models import ProbeEvent
from app.api.routers import badges, claims, nexus, status as status_router, vnp_ingest, vnp_stream, vabp
from app.batch import ingest as batch_ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_VERSION = "1.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_production_startup()

    if settings.is_production and settings.vnp_require_db:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise RuntimeError(
                "Refusing production startup: database is unavailable. "
                f"({exc.__class__.__name__})"
            ) from exc

    if settings.demo_mode_active:
        from app import demo_runtime

        demo_runtime.seed_demo_data()
        logger.warning("VNP demo runtime seeded — Demo Mode is active (non-production only).")

    logger.info(
        "Veklom VNP starting (env=%s, demo_mode=%s)",
        settings.vnp_env,
        settings.demo_mode_active,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Veklom VNP",
        description="Cryptographic API telemetry for the machine-to-machine economy",
        version=SERVICE_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Database-backed routers only.
    app.include_router(vnp_ingest.router, prefix="/api/v1")
    app.include_router(vnp_stream.router, prefix="/api/v1")
    app.include_router(nexus.router, prefix="/api/v1")
    app.include_router(claims.router, prefix="/api/v1")
    app.include_router(badges.router, prefix="/api/v1")
    app.include_router(vabp.router, prefix="/api/v1")
    app.include_router(batch_ingest.router)
    app.include_router(status_router.router)

    if settings.demo_mode_active:
        from app import demo_runtime

        app.include_router(demo_runtime.router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "veklom-vnp",
            "version": SERVICE_VERSION,
            "environment": settings.vnp_env,
            "demo_mode": settings.demo_mode_active,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/ready")
    async def readiness_check():
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            database = "connected"
            ready = True
        except Exception:
            database = "disconnected"
            ready = False
        return {
            "ready": ready,
            "database": database,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/v1/beacon/topology")
    async def get_topology(db: AsyncSession = Depends(get_db)):
        """Truthful topology telemetry derived only from database evidence.

        The physical node registry with signed heartbeats is not yet wired;
        until it is, regions are reported from actual probe observations and
        no fictional node, stake, CPU or pool-utilization values are emitted.
        """
        rows = (
            await db.execute(
                select(
                    ProbeEvent.region,
                    func.count(ProbeEvent.id),
                    func.max(ProbeEvent.measured_at),
                ).group_by(ProbeEvent.region)
            )
        ).all()

        regions = [
            {
                "region": region,
                "observation_count": count,
                "last_observation": last.isoformat() if last else None,
                "status_str": "Connected" if count else "Insufficient Evidence",
            }
            for region, count, last in rows
        ]

        return {
            "topology": {
                "networkStatus": "ACTIVE" if regions else "INSUFFICIENT_EVIDENCE",
                "activeRegions": len(regions),
                "regions": regions,
                "node_registry": "Not Yet Wired",
                "securityLevel": "VNP Methodology v1.0",
                "features": {
                    "signed_probe_ingestion": "Connected",
                    "node_heartbeats": "Not Yet Wired",
                    "vdf_time_lock": "Methodology Target",
                    "zk_snark_ready": "Methodology Target",
                },
            }
        }

    frontend_dist = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "frontend", "dist"
    )

    if os.path.exists(frontend_dist):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(frontend_dist, "assets")),
            name="assets",
        )

        @app.get("/")
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    else:

        @app.get("/")
        async def root():
            return {
                "service": "Veklom VNP",
                "version": SERVICE_VERSION,
                "environment": settings.vnp_env,
                "status": "running",
            }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8089, reload=True)
