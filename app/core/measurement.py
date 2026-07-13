from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.core.topology import CANONICAL_LOCATION_CODES, LEGACY_REGION_CODE_MAP
from app.db.models import Observation, MeasurementWindow
from app.pgl.client import PGLClient, PGLConnectionError

logger = logging.getLogger(__name__)

async def finalize_measurement_window(
    db: AsyncSession, target_id: str, window_start: datetime, window_end: datetime
) -> MeasurementWindow:
    """
    Finalize a measurement window for a target over a time range.
    Gathers observations, counts nodes and regions, and creates the window record.
    """
    # 1. Fetch observations for the window
    stmt = (
        select(Observation)
        .where(Observation.target_id == target_id)
        .where(Observation.started_at >= window_start)
        .where(Observation.started_at < window_end)
    )
    result = await db.execute(stmt)
    observations = result.scalars().all()

    # 2. Aggregate metrics
    sample_count = len(observations)
    unique_nodes = {obs.node_id for obs in observations}
    unique_locations = {obs.physical_location for obs in observations}
    
    # Normalize legacy rows while counting current canonical location codes.
    unique_regions = {LEGACY_REGION_CODE_MAP.get(obs.region, obs.region) for obs in observations}
    
    # Check freshness (max time since last observation)
    now = datetime.now(timezone.utc)
    freshness = 0
    if observations:
        latest = max(obs.completed_at for obs in observations)
        freshness = int((now - latest).total_seconds())
        
    missing_regions = sorted(CANONICAL_LOCATION_CODES - unique_regions)

    # Calculate confidence band based on sample count
    confidence_band = "high" if sample_count >= 10 else "low"

    # Create the window
    window = MeasurementWindow(
        target_id=target_id,
        window_start=window_start,
        window_end=window_end,
        node_count=len(unique_nodes),
        physical_location_count=len(unique_locations),
        macro_region_count=len(unique_regions), # Approximation
        sample_count=sample_count,
        freshness=freshness,
        missing_regions=missing_regions,
        provisional_flag=False,
        confidence_band=confidence_band,
        formula_version="v1.0"
    )
    
    db.add(window)
    await db.flush()
    
    try:
        pgl_client = PGLClient()
        receipt_id = await pgl_client.mint_receipt("window_finalized", {
            "window_id": str(window.id),
            "target_id": target_id,
            "sample_count": sample_count
        })
        window.pgl_evidence_id = receipt_id
        logger.info(f"Minted PGL receipt {receipt_id} for measurement window {window.id}")
    except PGLConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    await db.commit()
    await db.refresh(window)
    
    return window
