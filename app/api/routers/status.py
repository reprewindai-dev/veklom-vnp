"""Canonical VNP capability status endpoint.

GET /v1/status/capabilities reports the truthful implementation and
operational state of every VNP capability, derived exclusively from
database evidence. The frontend must render this response exactly and
may not override status locally.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import (
    ClaimRequest,
    Observation,
    ProbeEvent,
    RegionalTelemetry,
    UsageEvent,
)

router = APIRouter(prefix="/v1/status", tags=["VNP Status"])

APPROVED_STATUS_VOCABULARY = frozenset(
    {
        "Live",
        "Connected",
        "Partially Implemented",
        "Demo Mode",
        "Methodology Target",
        "Not Yet Wired",
        "Config Incomplete",
        "Disconnected",
        "Auth Required",
        "Insufficient Evidence",
    }
)


class CapabilityStatus(BaseModel):
    capability_id: str
    implementation_state: str
    operational_state: str
    evidence_count: int
    last_successful_event: Optional[str] = None
    freshness_seconds: Optional[int] = None
    reason: str
    required_configuration: List[str] = []


class CapabilityStatusResponse(BaseModel):
    service: str = "veklom-vnp"
    environment: str
    demo_mode: bool
    generated_at: str
    capabilities: List[CapabilityStatus]


VNP_METHODOLOGY_CAPABILITY_MAP = {
    "Physical measurements": "vnp_physical_probes",
    "Signed telemetry": "vnp_signed_telemetry",
    "Robust scoring": "vnp_regional_scoring",
    "x402 settlement evidence": "vnp_usage_metering",
    "PGL audit trails": "pgl_audit_trails",
    "Agent/runtime enforcement": "agent_runtime_enforcement",
}


def _freshness(last_event: Optional[datetime]) -> Optional[int]:
    if last_event is None:
        return None
    if last_event.tzinfo is None:
        last_event = last_event.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - last_event).total_seconds()))


def _methodology_capability(section: str, status: str) -> CapabilityStatus:
    capability_id = VNP_METHODOLOGY_CAPABILITY_MAP[section]
    operational_state = "Connected" if status == "Live" else status
    return CapabilityStatus(
        capability_id=capability_id,
        implementation_state=status,
        operational_state=operational_state,
        evidence_count=1,
        last_successful_event=None,
        freshness_seconds=None,
        reason=f"BYOS methodology reports '{section}' as {status}",
        required_configuration=[],
    )


async def _byos_methodology_capabilities(settings) -> dict[str, CapabilityStatus]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.byos_backend_url.rstrip('/')}/api/v1/vnp/methodology"
            )
        response.raise_for_status()
        payload = response.json()
        capabilities: dict[str, CapabilityStatus] = {}
        for item in payload.get("verification_stack", []):
            section = item.get("section")
            status = item.get("status")
            if (
                section in VNP_METHODOLOGY_CAPABILITY_MAP
                and status in APPROVED_STATUS_VOCABULARY
            ):
                capability = _methodology_capability(section, status)
                capabilities[capability.capability_id] = capability
        return capabilities
    except Exception:
        return {}


async def _evidence_capability(
    db: AsyncSession,
    capability_id: str,
    model,
    timestamp_column,
    required_configuration: List[str],
    no_evidence_reason: str,
) -> CapabilityStatus:
    count = (await db.execute(select(func.count()).select_from(model))).scalar_one()
    last_event = (await db.execute(select(func.max(timestamp_column)))).scalar_one()
    if count == 0:
        return CapabilityStatus(
            capability_id=capability_id,
            implementation_state="Partially Implemented",
            operational_state="Insufficient Evidence",
            evidence_count=0,
            last_successful_event=None,
            freshness_seconds=None,
            reason=no_evidence_reason,
            required_configuration=required_configuration,
        )
    return CapabilityStatus(
        capability_id=capability_id,
        implementation_state="Partially Implemented",
        operational_state="Connected",
        evidence_count=count,
        last_successful_event=last_event.isoformat() if last_event else None,
        freshness_seconds=_freshness(last_event),
        reason=f"{count} evidence records in database",
        required_configuration=[],
    )


def _not_yet_wired(capability_id: str, reason: str, required: List[str]) -> CapabilityStatus:
    return CapabilityStatus(
        capability_id=capability_id,
        implementation_state="Not Yet Wired",
        operational_state="Not Yet Wired",
        evidence_count=0,
        reason=reason,
        required_configuration=required,
    )


async def _byos_node_registry_capability(settings) -> CapabilityStatus:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.byos_backend_url.rstrip('/')}/api/v1/beacon/topology"
            )
        response.raise_for_status()
        topology = response.json().get("topology", {})
        active_nodes = int(topology.get("activeNodes") or 0)
        expected_nodes = int(topology.get("expectedNodes") or 5)
        nodes = topology.get("nodes") or []
        keyed_nodes = sum(1 for node in nodes if int(node.get("activeKeyCount") or 0) > 0)
        fresh_nodes = sum(1 for node in nodes if node.get("lastHeartbeat"))
        last_heartbeat = max(
            (node.get("lastHeartbeat") for node in nodes if node.get("lastHeartbeat")),
            default=None,
        )
        if active_nodes >= expected_nodes and keyed_nodes >= expected_nodes:
            return CapabilityStatus(
                capability_id="vnp_node_registry",
                implementation_state="Live",
                operational_state="Connected",
                evidence_count=active_nodes,
                last_successful_event=last_heartbeat,
                freshness_seconds=None,
                reason=(
                    f"BYOS topology reports {active_nodes}/{expected_nodes} connected "
                    f"nodes with active signing keys"
                ),
                required_configuration=[],
            )
        return CapabilityStatus(
            capability_id="vnp_node_registry",
            implementation_state="Partially Implemented",
            operational_state="Config Incomplete",
            evidence_count=active_nodes,
            last_successful_event=last_heartbeat,
            freshness_seconds=None,
            reason=(
                f"BYOS topology reports {active_nodes}/{expected_nodes} connected, "
                f"{keyed_nodes}/{expected_nodes} keyed, {fresh_nodes}/{expected_nodes} heartbeating"
            ),
            required_configuration=["node_keypair", "node_registration", "region_assignment"],
        )
    except Exception:
        return _not_yet_wired(
            "vnp_node_registry",
            "BYOS topology unavailable; cannot verify physical node registry or signed heartbeats",
            ["byos_backend_url"],
        )


@router.get("/capabilities", response_model=CapabilityStatusResponse)
async def get_capabilities(db: AsyncSession = Depends(get_db)) -> CapabilityStatusResponse:
    settings = get_settings()
    capabilities: List[CapabilityStatus] = []
    byos_methodology = await _byos_methodology_capabilities(settings)

    try:
        for capability_id, model, timestamp_column, required_configuration, reason in (
            (
                "vnp_physical_probes",
                Observation,
                Observation.completed_at,
                ["node_keypair", "node_registration", "region_assignment"],
                "No signed observations received",
            ),
            (
                "vnp_regional_scoring",
                RegionalTelemetry,
                RegionalTelemetry.measured_at,
                ["finalized_measurement_windows"],
                "No finalized regional telemetry windows",
            ),
            (
                "vnp_usage_metering",
                UsageEvent,
                UsageEvent.occurred_at,
                ["sdk_credentials"],
                "No signed usage events received",
            ),
        ):
            capabilities.append(
                byos_methodology.get(capability_id)
                or await _evidence_capability(
                    db,
                    capability_id,
                    model,
                    timestamp_column,
                    required_configuration,
                    reason,
                )
            )

        if "vnp_signed_telemetry" in byos_methodology:
            capabilities.append(byos_methodology["vnp_signed_telemetry"])
        if "pgl_audit_trails" in byos_methodology:
            capabilities.append(byos_methodology["pgl_audit_trails"])
        if "agent_runtime_enforcement" in byos_methodology:
            capabilities.append(byos_methodology["agent_runtime_enforcement"])

        capabilities.append(
            await _evidence_capability(
                db,
                "vnp_provider_claims",
                ClaimRequest,
                ClaimRequest.created_at,
                [],
                "No provider claims submitted",
            )
        )
        db_reachable = True
    except Exception:
        db_reachable = False
        capabilities = [
            byos_methodology.get(capability_id)
            or CapabilityStatus(
                capability_id=capability_id,
                implementation_state="Partially Implemented",
                operational_state="Disconnected",
                evidence_count=0,
                reason="Database unreachable",
                required_configuration=["database_url"],
            )
            for capability_id in (
                "vnp_physical_probes",
                "vnp_regional_scoring",
                "vnp_provider_claims",
                "vnp_usage_metering",
            )
        ]
        for capability_id in (
            "vnp_signed_telemetry",
            "pgl_audit_trails",
            "agent_runtime_enforcement",
        ):
            if capability_id in byos_methodology:
                capabilities.append(byos_methodology[capability_id])

    capabilities.append(await _byos_node_registry_capability(settings))
    capabilities.append(
        _not_yet_wired(
            "vabp_certification",
            "VABP benchmark sandbox and Trust Certificates not yet wired",
            ["vabp_sandbox", "test_corpora"],
        )
    )
    capabilities.append(
        _not_yet_wired(
            "vnp_performance_assurance",
            "Performance Bonds, challenges and CAPPO settlement not yet wired",
            ["cappo_service_identity", "pgl_signing_keys"],
        )
    )

    if db_reachable:
        capabilities.append(
            CapabilityStatus(
                capability_id="vnp_streaming",
                implementation_state="Partially Implemented",
                operational_state="Connected",
                evidence_count=0,
                reason="SSE/WebSocket streams serve database telemetry only",
                required_configuration=[],
            )
        )
    else:
        capabilities.append(
            CapabilityStatus(
                capability_id="vnp_streaming",
                implementation_state="Partially Implemented",
                operational_state="Disconnected",
                evidence_count=0,
                reason="Database unreachable",
                required_configuration=["database_url"],
            )
        )

    for capability in capabilities:
        assert capability.operational_state in APPROVED_STATUS_VOCABULARY

    return CapabilityStatusResponse(
        environment=settings.vnp_env,
        demo_mode=settings.demo_mode_active,
        generated_at=datetime.now(timezone.utc).isoformat(),
        capabilities=capabilities,
    )
