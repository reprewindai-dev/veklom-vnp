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
from app.db.models import Node, NodeKey, NodeHeartbeat, Observation
from app.api.routers import badges, claims, nexus, status as status_router, vnp_ingest, vnp_stream, vabp, staking
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
    app.include_router(staking.router, prefix="/api/v1")
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
        """Compile topology only from the canonical physical node registry."""
        now = datetime.now(timezone.utc)
        freshness_limit = settings.vnp_node_heartbeat_freshness_seconds
        nodes = (await db.execute(select(Node).order_by(Node.site_code))).scalars().all()
        entries = []
        for node in nodes:
            key = (
                await db.execute(
                    select(NodeKey)
                    .where(NodeKey.node_id == node.id)
                    .where(NodeKey.active.is_(True))
                    .where(NodeKey.revoked_at.is_(None))
                    .order_by(NodeKey.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            heartbeat = (
                await db.execute(
                    select(NodeHeartbeat)
                    .where(NodeHeartbeat.node_id == node.id)
                    .order_by(NodeHeartbeat.timestamp.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            observation_count = (
                await db.execute(
                    select(func.count(Observation.id)).where(Observation.node_id == node.id)
                )
            ).scalar_one()
            freshness = (
                max(0, int((now - heartbeat.timestamp).total_seconds()))
                if heartbeat
                else None
            )
            heartbeat_fresh = freshness is not None and freshness <= freshness_limit
            deployed = bool(node.probe_deployed_at and node.image_digest)
            if not key or not node.registration_status:
                state, reason = "Config Incomplete", "node registration incomplete"
            elif not deployed:
                state, reason = "Config Incomplete", "probe deployment evidence missing"
            elif not heartbeat_fresh:
                state, reason = "Disconnected", "fresh signed heartbeat missing"
            elif not observation_count:
                state, reason = "Insufficient Evidence", "no accepted observations"
            else:
                state, reason = "Live", "all operational evidence requirements satisfied"
            entries.append(
                {
                    "nodeId": str(node.id),
                    "name": node.name,
                    "siteCode": node.site_code,
                    "locationCode": node.region_code,
                    "physicalLocation": node.physical_location,
                    "provider": node.provider,
                    "platform": node.platform,
                    "coolifyServerUuid": node.coolify_server_uuid,
                    "coolifyApplicationUuid": node.coolify_application_uuid,
                    "softwareVersion": node.software_version,
                    "heartbeatFreshnessSeconds": freshness,
                    "observationCount": int(observation_count or 0),
                    "state": state,
                    "reason": reason,
                }
            )
        live = sum(entry["state"] == "Live" for entry in entries)
        return {
            "topology": {
                "node_registry": "canonical_vnp_nodes",
                "nodes": entries,
                "networkStatus": "LIVE" if live == len(entries) and entries else "PARTIAL",
                "activeRegions": live,
                "regions": entries,
                "expectedNodes": 5,
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
