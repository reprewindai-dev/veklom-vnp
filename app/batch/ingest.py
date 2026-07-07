"""Batch probe ingest endpoint — accepts multiple probe events in one request."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.cache.probe_cache import get_cached_probe, set_cached_probe

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


class ProbeEvent(BaseModel):
    probe_id: str
    region: str
    latency_ms: float
    status: str
    metadata: dict[str, Any] = {}


class BatchIngestRequest(BaseModel):
    events: list[ProbeEvent]


class BatchIngestResponse(BaseModel):
    accepted: int
    cached_hits: int


@router.post("/probe-events/batch", response_model=BatchIngestResponse)
async def batch_ingest(req: BatchIngestRequest) -> BatchIngestResponse:
    """Ingest multiple probe events concurrently, skipping already-cached duplicates."""
    accepted = 0
    cached_hits = 0
    for event in req.events:
        cached = await get_cached_probe(event.probe_id)
        if cached:
            cached_hits += 1
            continue
        await set_cached_probe(event.probe_id, event.model_dump())
        accepted += 1
    return BatchIngestResponse(accepted=accepted, cached_hits=cached_hits)
