"""Legacy in-memory demo runtime.

Everything in this module is demo-only. It is mounted exclusively when
VNP_ALLOW_DEMO_DATA=true outside production. The production entrypoint
never imports sample APIs, random measurements, mocked VDF verification,
dummy slashing or fictional topology from here.

Every response from this router carries "runtime_label": "Demo Mode" so
no consumer can mistake demo output for evidence.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demo Mode (never production)"])

RUNTIME_LABEL = "Demo Mode"


class Measurement(BaseModel):
    api_id: str
    region: str
    node_version: str = "v1.0.0"
    latency_p99: float
    latency_p95: float
    error_rate: float
    availability: float
    timestamp: datetime
    hmac_sha256: Optional[str] = None
    pad_tlv_size: Optional[int] = None
    rpn_active: bool = False
    delay_proxy_ms: float = 0.0


class Score(BaseModel):
    api_id: str
    composite_score: float
    dimensions: Dict[str, float]
    confidence: float
    updated_at: datetime
    is_mad_bounded: bool = True


measurements_store: Dict[str, List[Measurement]] = {}
scores_store: Dict[str, Score] = {}

SAMPLE_APIS = [
    "openai-api",
    "anthropic-api",
    "together-ai",
    "replicate-api",
    "huggingface-api",
]

SCORING_WEIGHTS = {
    "p99_latency": 0.40,
    "error_rate": 0.25,
    "availability": 0.15,
    "throughput": 0.08,
    "security": 0.08,
    "documentation": 0.07,
    "versioning": 0.07,
    "x402_compliance": 0.06,
    "rate_limit_transparency": 0.06,
    "developer_experience": 0.05,
}


def calculate_mad(data: List[float]) -> float:
    if not data:
        return 0.0
    median = sorted(data)[len(data) // 2]
    deviations = [abs(x - median) for x in data]
    return 1.4826 * sorted(deviations)[len(deviations) // 2]


def calculate_composite_score(measurements: List[Measurement]) -> Optional[Score]:
    if not measurements:
        return None

    adjusted_latencies = []
    legacy_count = 0
    for m in measurements:
        actual_rtt = m.latency_p99
        if m.rpn_active:
            actual_rtt = max(1.0, actual_rtt - m.delay_proxy_ms)
        adjusted_latencies.append(actual_rtt)
        if m.node_version != "v1.0.0":
            legacy_count += 1

    median_latency = sorted(adjusted_latencies)[len(adjusted_latencies) // 2]
    mad_latency = calculate_mad(adjusted_latencies)
    lower_bound = median_latency - (3 * mad_latency)

    bounded_latencies = [max(lower_bound, lat) for lat in adjusted_latencies]
    avg_latency = sum(bounded_latencies) / len(bounded_latencies)

    avg_error_rate = sum(m.error_rate for m in measurements) / len(measurements)
    avg_availability = sum(m.availability for m in measurements) / len(measurements)

    latency_score = max(0, 100 - (avg_latency / 10))
    error_score = max(0, 100 - (avg_error_rate * 100))
    availability_score = avg_availability * 100

    dimensions = {
        "p99_latency": latency_score,
        "error_rate": error_score,
        "availability": availability_score,
        "throughput": 80,
        "security": 85,
        "documentation": 75,
        "versioning": 80,
        "x402_compliance": 70,
        "rate_limit_transparency": 75,
        "developer_experience": 78,
    }

    composite = sum(dimensions[key] * SCORING_WEIGHTS[key] for key in dimensions)

    trust_weight = 1.0
    if legacy_count > 0:
        legacy_ratio = legacy_count / len(measurements)
        trust_weight = 1.0 - (0.4 * legacy_ratio)

    composite = composite * trust_weight

    return Score(
        api_id=measurements[0].api_id,
        composite_score=composite,
        dimensions=dimensions,
        confidence=min(100, (len(measurements) / 100 * 100) * trust_weight),
        updated_at=datetime.utcnow(),
        is_mad_bounded=True,
    )


def seed_demo_data() -> None:
    """Seed the in-memory stores with random sample data. Demo only."""
    for api_id in SAMPLE_APIS:
        measurements = [
            Measurement(
                api_id=api_id,
                region="us-east",
                latency_p99=random.uniform(50, 200),
                latency_p95=random.uniform(30, 150),
                error_rate=random.uniform(0.001, 0.05),
                availability=random.uniform(0.95, 0.99),
                timestamp=datetime.utcnow() - timedelta(minutes=i),
            )
            for i in range(150)
        ]
        measurements_store[api_id] = measurements
        score = calculate_composite_score(measurements[-100:])
        scores_store[api_id] = score
        logger.info("Seeded demo API %s: score %.1f", api_id, score.composite_score)


@router.post("/measurements")
async def post_measurement(measurement: Measurement):
    now = datetime.utcnow()
    diff = abs((now - measurement.timestamp).total_seconds())
    if diff > 0.5:
        raise HTTPException(
            status_code=400,
            detail=f"NTP Consensus Error: Timestamp drift {diff:.3f}s exceeds ±500ms limit",
        )

    api_id = measurement.api_id
    measurements_store.setdefault(api_id, []).append(measurement)

    if len(measurements_store[api_id]) >= 100:
        score = calculate_composite_score(measurements_store[api_id][-100:])
        scores_store[api_id] = score

    return {"status": "received", "api_id": api_id, "runtime_label": RUNTIME_LABEL}


@router.get("/measurements/{api_id}")
async def get_measurements(api_id: str, limit: int = 100):
    if api_id not in measurements_store:
        raise HTTPException(status_code=404, detail=f"No measurements for {api_id}")
    measurements = measurements_store[api_id][-limit:]
    return {
        "api_id": api_id,
        "count": len(measurements),
        "measurements": [m.dict() for m in measurements],
        "runtime_label": RUNTIME_LABEL,
    }


@router.get("/scores/{api_id}")
async def get_score(api_id: str):
    if api_id not in scores_store:
        raise HTTPException(status_code=404, detail=f"No score yet for {api_id}")
    score = scores_store[api_id]
    return {
        "api_id": api_id,
        "composite_score": score.composite_score,
        "dimensions": score.dimensions,
        "confidence": score.confidence,
        "updated_at": score.updated_at.isoformat(),
        "runtime_label": RUNTIME_LABEL,
    }


@router.get("/scores")
async def get_all_scores():
    return {
        "count": len(scores_store),
        "scores": {
            api_id: {
                "composite_score": score.composite_score,
                "updated_at": score.updated_at.isoformat(),
            }
            for api_id, score in scores_store.items()
        },
        "runtime_label": RUNTIME_LABEL,
    }


@router.get("/sdk/select")
async def sdk_select_api(candidates: str, constraint: Optional[str] = None):
    api_list = [api.strip() for api in candidates.split(",")]
    candidates_filtered = [
        {
            "api": api_id,
            "score": scores_store[api_id].composite_score,
            "dimensions": scores_store[api_id].dimensions,
        }
        for api_id in api_list
        if api_id in scores_store
    ]
    candidates_filtered.sort(key=lambda x: x["score"], reverse=True)
    if not candidates_filtered:
        raise HTTPException(status_code=404, detail="No scored APIs in candidates")
    best = candidates_filtered[0]
    return {
        "selected_api": best["api"],
        "score": best["score"],
        "all_candidates": candidates_filtered,
        "runtime_label": RUNTIME_LABEL,
    }
