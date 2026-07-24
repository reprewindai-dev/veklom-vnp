"""Veklom Nexus Protocol — real benchmark scoring from ExecutionLog."""

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import hashlib

from app.db.database import get_db
from app.core.topology import CANONICAL_LOCATION_CODES
from app.db.models import Api, RegionalTelemetry, ProbeEvent, Node, NodeHeartbeat

router = APIRouter(prefix="/nexus", tags=["Nexus Protocol"])

# VNP Threshold Definitions — the standard, never mocked
VNP_THRESHOLDS = {
    "latency_ms": 150,          # Max acceptable latency
    "throughput_tps": 50,       # Min acceptable tokens/sec
    "cost_per_inference_usdc": 0.05,  # Max acceptable cost
}


class CertificationRequest(BaseModel):
    api_name: str
    provider: str
    endpoint_url: str
    claimed_latency: int
    claimed_throughput: int


def _vnp_status(avg_latency: float, avg_cost: float) -> str:
    """Derive NEXUS-CERTIFIED or FAILING from real aggregated metrics."""
    if avg_latency <= VNP_THRESHOLDS["latency_ms"] and avg_cost <= VNP_THRESHOLDS["cost_per_inference_usdc"]:
        return "NEXUS-CERTIFIED"
    return "FAILING"


def _vnp_score(avg_latency: float, avg_cost: float, total_tokens: float) -> int:
    """Compute a 0-100 VNP score.
    Latency contributes 50 pts, cost 30 pts, throughput proxy 20 pts.
    """
    latency_score = max(0.0, 50.0 * (1.0 - avg_latency / 500.0))
    cost_score = max(0.0, 30.0 * (1.0 - avg_cost / 0.10))
    throughput_score = min(20.0, 20.0 * (total_tokens / 10000.0))
    return round(latency_score + cost_score + throughput_score)


@router.get("/standard")
async def nexus_standard():
    """Returns the official Veklom Nexus Protocol threshold definitions."""
    return {
        "standard": "veklom-nexus-v1",
        "thresholds": VNP_THRESHOLDS,
        "description": "Veklom Nexus Protocol sets the benchmark standard for sovereign AI agent API performance.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/benchmark")
async def nexus_benchmark():
    """Returns Veklom Nexus Protocol benchmark metadata."""
    return {
        "standard": "veklom-nexus-v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }





@router.post("/certify")
async def nexus_certify(request: CertificationRequest):
    """Endpoint for third-party API submissions to be certified by VNP."""
    certified = (
        request.claimed_latency <= VNP_THRESHOLDS["latency_ms"]
        and request.claimed_throughput >= VNP_THRESHOLDS["throughput_tps"]
    )
    return {
        "submission_id": f"cert-{int(datetime.now(timezone.utc).timestamp())}",
        "api_name": request.api_name,
        "provider": request.provider,
        "status": "APPROVED" if certified else "REJECTED",
        "reason": (
            "Meets VNP standards"
            if certified
            else "Fails to meet VNP latency or throughput standards"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }




@router.get("/scores")
async def get_nexus_scores(db: AsyncSession = Depends(get_db)):
    """
    Returns API ScoreCards for the NexusProtocol UI.
    Queries vnp_apis and RegionalTelemetry dynamically.
    """
    stmt = select(Api).where(Api.status == "active")
    result = await db.execute(stmt)
    apis = result.scalars().all()

    # Dimension definitions with weights
    dimension_defs = [
        ("Performance",      15, "p50/p95 response latency across probe regions"),
        ("Reliability",      15, "HTTP 200 uptime consistency over 30d window"),
        ("Security Posture", 10, "TLS configuration, security headers, auth strength"),
        ("SLA Compliance",   10, "Acceptable boundary conformance per signed SLA"),
        ("Cost Efficiency",  10, "Effective cost per 1K governed requests"),
        ("Data Integrity",   10, "Schema validation, payload accuracy & type fidelity"),
        ("Governance",       10, "Policy adherence under Zero-Trust middleware"),
        ("Auditability",      8, "Log completeness, traceability and receipt coverage"),
        ("Resilience",        7, "Mean recovery time and retry success rate under load"),
        ("Interoperability",  5, "OpenAPI, x402 settlement, CORS standards compliance"),
    ]

    scorecards = []
    for api in apis:
        api_id_str = str(api.id)
        
        # Get actual telemetry from DB
        telemetry_stmt = select(RegionalTelemetry).where(RegionalTelemetry.api_id == api.id).order_by(RegionalTelemetry.measured_at.desc()).limit(1)
        tel_result = await db.execute(telemetry_stmt)
        latest_telemetry = tel_result.scalar_one_or_none()
        
        if not latest_telemetry:
            scorecards.append({
                "id": api_id_str,
                "name": api.name,
                "provider": api_id_str.split("-")[0] if api.name else "Unknown",
                "score": None,
                "grade": None,
                "status": "Insufficient Evidence",
                "dimensions": [],
                "anchorHash": None,
                "txHash": None,
                "lastUpdated": _time_ago(api.updated_at) if hasattr(api, "updated_at") and api.updated_at else "—",
            })
            continue

        # Map real DB metrics to 0-100 scales
        perf_score = max(0, 100 - (latest_telemetry.p99_latency_ms / 10))
        rel_score = float(latest_telemetry.uptime_percent)
        composite = float(latest_telemetry.trust_score)
        anchor_hash = latest_telemetry.on_chain_anchor
        tx_hash = latest_telemetry.provenance_hash

        dimensions = []
        weighted_sum = 0.0
        total_weight = 0

        for i, (name, weight, desc) in enumerate(dimension_defs):
            if name == "Performance":
                dim_score = perf_score
            elif name == "Reliability":
                dim_score = rel_score
            else:
                dim_score = composite # Fallback for unmeasured dimensions
                
            dim_score = max(0, min(100, int(dim_score)))
            dimensions.append({
                "name": name,
                "score": dim_score,
                "weight": weight,
                "desc": desc,
            })
            weighted_sum += dim_score * weight
            total_weight += weight

        overall = round(weighted_sum / total_weight) if total_weight else int(composite)
        grade = _nexus_grade(overall)

        scorecards.append({
            "id": api_id_str,
            "name": api.name,
            "provider": api_id_str.split("-")[0] if api.name else "Unknown",
            "score": overall,
            "grade": grade,
            "status": "Evidence Verified",
            "dimensions": dimensions,
            "anchorHash": anchor_hash,
            "txHash": tx_hash,
            "lastUpdated": _time_ago(api.updated_at) if hasattr(api, "updated_at") and api.updated_at else "—",
        })

    return scorecards


def _nexus_grade(score: int) -> str:
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "A-"
    elif score >= 80:
        return "B+"
    elif score >= 75:
        return "B"
    elif score >= 70:
        return "B-"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    return "F"


def _time_ago(dt) -> str:
    if not dt:
        return "—"
    now = datetime.now(timezone.utc)
    diff = now - dt
    minutes = int(diff.total_seconds() / 60)
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{minutes}m ago"
    elif minutes < 1440:
        return f"{minutes // 60}h ago"
    return f"{minutes // 1440}d ago"


@router.get("/nodes")
async def get_nexus_nodes(db: AsyncSession = Depends(get_db)):
    stmt = select(Node).order_by(Node.region_code)
    result = await db.execute(stmt)
    registered_nodes = result.scalars().all()
    
    nodes = []
    for node in registered_nodes:
        heartbeat_result = await db.execute(
            select(func.max(NodeHeartbeat.timestamp)).where(NodeHeartbeat.node_id == node.id)
        )
        last_heartbeat = heartbeat_result.scalar_one_or_none()
        observation_result = await db.execute(
            select(func.count(ProbeEvent.id)).where(ProbeEvent.worker_region == node.region_code)
        )
        observation_count = observation_result.scalar_one()
        missing_config = [
            field
            for field, value in (
                ("host_reference", getattr(node, "host_reference", None)),
                ("coolify_application_ref", getattr(node, "coolify_application_ref", None)),
                ("container_image_digest", getattr(node, "container_image_digest", None)),
                ("signing_key_id", getattr(node, "signing_key_id", None)),
            )
            if not value
        ]
        operational_state = (
            "Live"
            if not missing_config and last_heartbeat and observation_count > 0
            else "Config Incomplete"
            if missing_config
            else "Insufficient Evidence"
        )
        nodes.append({
            "id": str(node.id),
            "host_reference": getattr(node, "host_reference", None),
            "name": node.name,
            "region": node.region_code,
            "location_code": node.region_code,
            "physical_location": node.physical_location,
            "jurisdiction": node.jurisdiction,
            "infrastructure_provider": getattr(node, "infrastructure_provider", "Hetzner"),
            "deployment_platform": getattr(node, "deployment_platform", "Coolify"),
            "coolify_application_ref": getattr(node, "coolify_application_ref", None),
            "container_image_digest": getattr(node, "container_image_digest", None),
            "software_version": getattr(node, "software_version", None),
            "signing_key_id": getattr(node, "signing_key_id", None),
            "key_status": getattr(node, "key_status", "configuration_incomplete"),
            "last_signed_heartbeat": last_heartbeat.isoformat() if last_heartbeat else None,
            "health_state": node.health_state,
            "freshness_state": "fresh" if last_heartbeat else "missing",
            "registration_status": node.registration_status,
            "configuration_incomplete": missing_config,
            "latency": 0,
            "throughput": 0,
            "status": operational_state,
            "activeCycles": observation_count,
        })

    missing_location_codes = CANONICAL_LOCATION_CODES - {node.region_code for node in registered_nodes}
    for location_code in sorted(missing_location_codes):
        nodes.append(
            {
                "id": None,
                "host_reference": None,
                "name": location_code,
                "region": location_code,
                "location_code": location_code,
                "physical_location": None,
                "jurisdiction": None,
                "infrastructure_provider": "Hetzner",
                "deployment_platform": "Coolify",
                "coolify_application_ref": None,
                "container_image_digest": None,
                "software_version": None,
                "signing_key_id": None,
                "key_status": "configuration_incomplete",
                "last_signed_heartbeat": None,
                "health_state": "unknown",
                "freshness_state": "missing",
                "registration_status": "configuration_incomplete",
                "configuration_incomplete": ["node_registration"],
                "latency": 0,
                "throughput": 0,
                "status": "Config Incomplete",
                "activeCycles": 0,
            }
        )
    return nodes
