import logging
from typing import List, Dict, Any, Optional
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.core.security import VNPEventVerifier, VNPSecurityError
from app.core.targets import TARGET_PROFILES
from app.db.models import (
    ProbeEvent, UsageEvent, ProbeResultState,
    Node, NodeKey, NodeHeartbeat, Observation, ObservationRejection
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ingest",
    tags=["VNP Data Plane"],
    responses={404: {"description": "Not found"}},
)

# Pydantic Schemas for Ingest
class ProbeMeasurement(BaseModel):
    dns_ms: Optional[int] = None
    connect_ms: Optional[int] = None
    tls_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    total_ms: int
    status_code: Optional[int] = None
    success: bool
    timeout: bool = False
    error_class: Optional[str] = None

class SignatureBlock(BaseModel):
    alg: str
    key_id: str
    sig: str

class ProbeEventItem(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    producer: Dict[str, Any]
    target: Dict[str, Any]
    measurement: ProbeMeasurement
    signature: SignatureBlock

class ProbeBatch(BaseModel):
    batch_id: str
    events: List[ProbeEventItem]

class CanonicalObservation(BaseModel):
    schema_version: str = Field(alias="schema", default="veklom.vnp.observation.v1")
    observation_id: str
    node_id: str
    region: str
    site_code: str
    physical_location: str
    target_id: str
    endpoint_url: str
    measurement_profile: str
    measurement_version: str
    started_at: datetime
    completed_at: datetime
    dns_ms: Optional[int] = None
    tcp_ms: Optional[int] = None
    tls_ms: Optional[int] = None
    write_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    body_ms: Optional[int] = None
    total_ms: Optional[int] = None
    http_status: Optional[int] = None
    http_version: Optional[str] = None
    tls_version: Optional[str] = None
    tls_cipher: Optional[str] = None
    transport_reachable: bool = False
    semantic_assertion: Optional[bool] = None
    response_fingerprint: Optional[str] = None
    error_code: Optional[str] = None
    error_category: Optional[str] = None
    sequence: int
    previous_observation_hash: Optional[str] = None
    payload_digest: str
    signature_key_id: str
    signature: str

class ObservationBatch(BaseModel):
    observations: List[CanonicalObservation]


class Heartbeat(BaseModel):
    heartbeat_id: str
    node_id: str
    site_code: str
    timestamp: datetime
    sequence: int
    software_version: str
    payload_digest: str
    signature_key_id: str
    signature: str


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False

class UsageMeasurement(BaseModel):
    billable_units: int
    unit_type: str
    success: bool
    response_ms: Optional[int] = None
    http_status: Optional[int] = None
    retry_count: int = 0
    failover_count: int = 0

class UsageCommercial(BaseModel):
    pricing_tier_id: Optional[str] = None
    preauth_amount_minor: Optional[int] = None
    final_amount_minor: Optional[int] = None
    currency: str = "USD"

class UsageEventItem(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    customer_id: str
    project_id: str
    credential_id: str
    policy_id: Optional[str] = None
    request: Dict[str, Any]
    usage: UsageMeasurement
    commercial: UsageCommercial
    signature: SignatureBlock

class UsageBatch(BaseModel):
    batch_id: str
    events: List[UsageEventItem]


def _map_error_class_to_state(success: bool, timeout: bool, error_class: Optional[str]) -> ProbeResultState:
    if success:
        return ProbeResultState.success
    if timeout:
        return ProbeResultState.timeout
    if error_class == "dns_error":
        return ProbeResultState.dns_error
    if error_class == "tls_error":
        return ProbeResultState.tls_error
    if error_class == "transport_error":
        return ProbeResultState.transport_error
    return ProbeResultState.http_error


@router.post("/heartbeats")
async def ingest_heartbeat(
    heartbeat: Heartbeat = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Accept a signed heartbeat from a registered physical VNP node."""
    now = datetime.now(timezone.utc)
    if not _is_uuid(heartbeat.node_id):
        raise HTTPException(status_code=400, detail="invalid_node_id")
    if heartbeat.timestamp > now + timedelta(minutes=2):
        raise HTTPException(status_code=400, detail="future_timestamp")
    if heartbeat.timestamp < now - timedelta(minutes=15):
        raise HTTPException(status_code=400, detail="stale_heartbeat")

    node_result = await db.execute(select(Node).where(Node.id == uuid.UUID(heartbeat.node_id)))
    node = node_result.scalar_one_or_none()
    key_result = await db.execute(
        select(NodeKey).where(NodeKey.key_id == heartbeat.signature_key_id)
    )
    node_key = key_result.scalar_one_or_none()
    if (
        not node
        or not node_key
        or not node_key.active
        or node_key.revoked_at
        or node_key.node_id != node.id
        or heartbeat.site_code != node.site_code
    ):
        raise HTTPException(status_code=403, detail="node_key_or_site_not_registered")

    payload = heartbeat.model_dump(mode="json")
    if heartbeat.payload_digest != VNPEventVerifier.payload_digest(payload):
        raise HTTPException(status_code=400, detail="payload_digest_mismatch")
    payload["signature"] = {
        "alg": "Ed25519",
        "key_id": heartbeat.signature_key_id,
        "sig": heartbeat.signature,
    }
    try:
        VNPEventVerifier.verify_event_signature(payload, node_key.public_key)
    except VNPSecurityError as exc:
        raise HTTPException(status_code=401, detail="invalid_signature") from exc

    duplicate = await db.execute(
        select(NodeHeartbeat.id).where(NodeHeartbeat.heartbeat_id == heartbeat.heartbeat_id)
    )
    if duplicate.first():
        raise HTTPException(status_code=409, detail="duplicate_heartbeat")
    latest = await db.execute(
        select(NodeHeartbeat)
        .where(NodeHeartbeat.node_id == node.id)
        .order_by(NodeHeartbeat.sequence.desc())
        .limit(1)
    )
    previous = latest.scalar_one_or_none()
    if previous and heartbeat.sequence <= previous.sequence:
        raise HTTPException(status_code=409, detail="non_monotonic_sequence")

    db.add(
        NodeHeartbeat(
            heartbeat_id=heartbeat.heartbeat_id,
            node_id=node.id,
            sequence=heartbeat.sequence,
            timestamp=heartbeat.timestamp,
            software_version=heartbeat.software_version,
            signature_key_id=heartbeat.signature_key_id,
            signature=heartbeat.signature,
            payload_digest=heartbeat.payload_digest,
            created_at=now,
        )
    )
    node.last_seen_at = heartbeat.timestamp
    node.software_version = heartbeat.software_version
    node.health_state = "standby"
    await db.commit()
    logger.info("Accepted signed heartbeat node=%s sequence=%s", node.id, heartbeat.sequence)
    return {"accepted": True, "node_id": heartbeat.node_id, "sequence": heartbeat.sequence}


@router.post("/probe-events")
async def ingest_probe_events(
    batch: ProbeBatch = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Accept one or more signed probe events from Cloudflare global workers.
    """
    accepted = 0
    rejected = 0
    deduplicated = 0

    now = datetime.now(timezone.utc)

    for event in batch.events:
        latency = float(event.measurement.total_ms)
        
        # 0. Anti-Gaming: 3σ Outlier Detection & Speed of Light check
        if latency < 2.0:
            raise HTTPException(status_code=403, detail="Anti-Gaming Reject: Latency violates speed of light.")
        if latency > 10000.0:
            raise HTTPException(status_code=403, detail="Anti-Gaming Reject: Latency exceeds 3σ outlier threshold.")

        # 1. Reject events > 10 mins in future
        if event.occurred_at > now + timedelta(minutes=10):
            rejected += 1
            continue

        # 2. Check for duplicate event_id
        stmt = select(ProbeEvent.id).where(ProbeEvent.event_id == event.event_id)
        existing = await db.execute(stmt)
        if existing.first():
            deduplicated += 1
            continue

        # 3. Verify Signature
        try:
            # Reconstruct the raw dict for signature verification
            # The producer's public key is stored in the event signature block
            public_key_b64 = event.signature.key_id
            
            # Use exact pydantic dump for canonicalization
            raw_event = event.model_dump(mode="json")
            VNPEventVerifier.verify_event_signature(raw_event, public_key_b64)
            
        except VNPSecurityError as e:
            logger.warning(f"Signature verification failed for {event.event_id}: {e}")
            rejected += 1
            continue

        # 4. Insert into DB
        try:
            new_probe = ProbeEvent(
                event_id=event.event_id,
                worker_id=event.producer.get("worker_id", "unknown"),
                worker_region=event.producer.get("region_code", "unknown"),
                runtime=event.producer.get("runtime", "unknown"),
                api_id=event.target.get("api_id"),
                api_region_code=event.target.get("region_code"),
                endpoint_url=event.target.get("endpoint_url", ""),
                occurred_at=event.occurred_at,
                dns_ms=getattr(event.measurement, "dns_ms", None),
                connect_ms=getattr(event.measurement, "connect_ms", None),
                tls_ms=getattr(event.measurement, "tls_ms", None),
                ttfb_ms=getattr(event.measurement, "ttfb_ms", None),
                total_ms=int(event.measurement.total_ms),
                status_code=event.measurement.status_code,
                result_state="success" if event.measurement.status_code and event.measurement.status_code < 400 else "http_error",
                success=True if event.measurement.status_code and event.measurement.status_code < 400 else False,
                timeout=False,
                error_class=event.measurement.error_class,
                signature_alg=getattr(event.signature, "alg", "ed25519"),
                signature_key_id=getattr(event.signature, "key_id", "unknown"),
                signature_value=getattr(event.signature, "sig", ""),
                received_at=now
            )
            db.add(new_probe)
            accepted += 1
        except Exception as e:
            logger.error(f"Failed to insert probe event {event.event_id}: {e}")
            rejected += 1

    await db.commit()
    
    return {
        "accepted": accepted,
        "rejected": rejected,
        "deduplicated": deduplicated
    }


@router.post("/observations/batches")
async def ingest_observations_batches(
    batch: ObservationBatch = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Accept canonical physical observations from registered VNP nodes.
    """
    accepted = 0
    rejected = 0
    deduplicated = 0
    now = datetime.now(timezone.utc)

    async def reject(obs: CanonicalObservation, reason: str, details: Optional[Dict[str, Any]] = None):
        nonlocal rejected
        unsigned = obs.model_dump(mode="json", by_alias=True)
        db.add(
            ObservationRejection(
                observation_id=obs.observation_id,
                node_id=uuid.UUID(obs.node_id) if _is_uuid(obs.node_id) else None,
                signature_key_id=obs.signature_key_id,
                reason=reason,
                payload_digest=VNPEventVerifier.payload_digest(unsigned),
                received_at=now,
                details=details or {},
            )
        )
        rejected += 1

    for obs in batch.observations:
        if obs.schema_version != "veklom.vnp.observation.v1":
            await reject(obs, "invalid_schema")
            continue
        if obs.started_at > now + timedelta(minutes=2) or obs.completed_at > now + timedelta(minutes=2):
            await reject(obs, "future_timestamp")
            continue
        if obs.completed_at < obs.started_at:
            await reject(obs, "invalid_timestamp_order")
            continue
        target = TARGET_PROFILES.get(obs.target_id)
        if (
            not target
            or obs.endpoint_url != target["endpoint_url"]
            or obs.measurement_profile != target["measurement_profile"]
        ):
            await reject(obs, "invalid_target_assignment")
            continue

        existing = await db.execute(
            select(Observation.id).where(Observation.observation_id == obs.observation_id)
        )
        if existing.first():
            await reject(obs, "duplicate_observation")
            deduplicated += 1
            continue

        key_result = await db.execute(
            select(NodeKey).where(NodeKey.key_id == obs.signature_key_id)
        )
        node_key = key_result.scalar_one_or_none()
        if not node_key or not node_key.active or node_key.revoked_at:
            await reject(obs, "unknown_or_inactive_key")
            continue

        node_result = await db.execute(select(Node).where(Node.id == node_key.node_id))
        node = node_result.scalar_one_or_none()
        if (
            not node
            or str(node.id) != obs.node_id
            or node.site_code != obs.region
            or node.site_code != getattr(obs, "site_code", obs.region)
            or obs.physical_location != node.physical_location
        ):
            await reject(obs, "node_site_assignment")
            continue

        last_result = await db.execute(
            select(Observation)
            .where(Observation.node_id == node.id)
            .where(Observation.target_id == obs.target_id)
            .order_by(Observation.sequence.desc())
            .limit(1)
        )
        last_obs = last_result.scalar_one_or_none()
        if last_obs:
            expected_previous = hashlib.sha256(
                VNPEventVerifier.canonicalize_payload(
                    {
                        "observation_id": last_obs.observation_id,
                        "payload_digest": last_obs.payload_digest,
                    }
                )
            ).hexdigest()
            if obs.sequence <= last_obs.sequence:
                await reject(obs, "non_monotonic_sequence")
                continue
            if obs.previous_observation_hash != expected_previous:
                await reject(obs, "previous_hash_mismatch")
                continue
        elif obs.sequence != 1 or obs.previous_observation_hash not in (None, "bootstrap"):
            await reject(obs, "invalid_initial_chain")
            continue

        raw_obs = obs.model_dump(mode="json", by_alias=True)
        actual_digest = VNPEventVerifier.payload_digest(raw_obs)
        if obs.payload_digest != actual_digest:
            await reject(obs, "payload_digest_mismatch")
            continue
        raw_obs["signature"] = {"alg": "Ed25519", "key_id": obs.signature_key_id, "sig": obs.signature}
        try:
            VNPEventVerifier.verify_event_signature(raw_obs, node_key.public_key)
        except VNPSecurityError:
            await reject(obs, "invalid_signature")
            continue

        db.add(
            Observation(
                observation_id=obs.observation_id,
                node_id=node.id,
                site_code=node.site_code,
                region=obs.region,
                physical_location=obs.physical_location,
                target_id=obs.target_id,
                measurement_profile=obs.measurement_profile,
                measurement_version=obs.measurement_version,
                started_at=obs.started_at,
                completed_at=obs.completed_at,
                dns_ms=obs.dns_ms,
                tcp_ms=obs.tcp_ms,
                tls_ms=obs.tls_ms,
                write_ms=obs.write_ms,
                ttfb_ms=obs.ttfb_ms,
                body_ms=obs.body_ms,
                total_ms=obs.total_ms,
                http_status=obs.http_status,
                http_version=obs.http_version,
                tls_version=obs.tls_version,
                tls_cipher=obs.tls_cipher,
                transport_reachable=obs.transport_reachable,
                semantic_assertion=obs.semantic_assertion,
                response_fingerprint=obs.response_fingerprint,
                error_code=obs.error_code,
                error_category=obs.error_category,
                sequence=obs.sequence,
                previous_observation_hash=obs.previous_observation_hash,
                signature_key_id=obs.signature_key_id,
                signature=obs.signature,
                payload_digest=obs.payload_digest,
                created_at=now,
            )
        )
        accepted += 1
        node.last_seen_at = now
        node.health_state = "live"

    await db.commit()
    logger.info(
        "VNP observation batch processed: accepted=%s rejected=%s deduplicated=%s",
        accepted,
        rejected,
        deduplicated,
    )
    return {"accepted": accepted, "rejected": rejected, "deduplicated": deduplicated}


@router.post("/usage-events")
async def ingest_usage_events(
    batch: UsageBatch = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Accept billable usage events from the SDK or Gateway.
    """
    accepted = 0
    rejected = 0
    deduplicated = 0

    now = datetime.now(timezone.utc)

    for event in batch.events:
        if event.occurred_at > now + timedelta(minutes=10):
            rejected += 1
            continue

        stmt = select(UsageEvent.id).where(UsageEvent.event_id == event.event_id)
        existing = await db.execute(stmt)
        if existing.first():
            deduplicated += 1
            continue

        try:
            partition_key = event.occurred_at.strftime("%Y-%m")
            new_usage = UsageEvent(
                event_id=event.event_id,
                partition_key=partition_key,
                customer_id=event.customer_id,
                project_id=event.project_id,
                credential_id=event.credential_id,
                policy_id=event.policy_id,
                request_id=event.request.get("request_id"),
                api_id=event.request.get("api_id"),
                provider_id=event.request.get("provider_id"),
                provider_region=event.request.get("provider_region"),
                sdk_region=event.request.get("sdk_region"),
                route_snapshot_id=event.request.get("route_snapshot_id"),
                billable_units=event.usage.billable_units,
                unit_type=event.usage.unit_type,
                success=event.usage.success,
                response_ms=event.usage.response_ms,
                http_status=event.usage.http_status,
                retry_count=event.usage.retry_count,
                failover_count=event.usage.failover_count,
                preauth_amount_minor=event.commercial.preauth_amount_minor,
                final_amount_minor=event.commercial.final_amount_minor,
                currency=event.commercial.currency,
                occurred_at=event.occurred_at,
                signature_alg=event.signature.alg,
                signature_key_id=event.signature.key_id,
                signature_value=event.signature.sig,
                received_at=now
            )
            db.add(new_usage)
            accepted += 1
        except Exception as e:
            logger.error(f"Failed to insert usage event {event.event_id}: {e}")
            rejected += 1

    await db.commit()
    
    return {
        "accepted": accepted,
        "rejected": rejected,
        "deduplicated": deduplicated
    }
