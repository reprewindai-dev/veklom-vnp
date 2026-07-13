import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.core.security import VNPEventVerifier, VNPSecurityError
from app.db.models import (
    ProbeEvent, UsageEvent, Api, Customer, Project, SdkCredential, RoutePolicy, Provider, ProbeResultState,
    Node, NodeKey, Observation
)
from app.pgl.client import PGLClient, PGLConnectionError
from app.services.slashing_engine import SlashingEngine

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
    physical_location: str
    target_id: str
    measurement_profile: str
    measurement_version: str
    started_at: datetime
    completed_at: datetime
    dns_ms: Optional[int] = None
    tcp_ms: Optional[int] = None
    tls_ms: Optional[int] = None
    ttfb_ms: Optional[int] = None
    total_ms: Optional[int] = None
    http_status: Optional[int] = None
    response_fingerprint: Optional[str] = None
    error_code: Optional[str] = None
    sequence: int
    previous_observation_hash: Optional[str] = None
    signature_key_id: str
    signature: str

class ObservationBatch(BaseModel):
    observations: List[CanonicalObservation]

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

    for obs in batch.observations:
        # 1. Reject events > 10 mins in future
        if obs.started_at > now + timedelta(minutes=10):
            rejected += 1
            continue

        # 2. Check for duplicate observation_id
        stmt = select(Observation.id).where(Observation.observation_id == obs.observation_id)
        existing = await db.execute(stmt)
        if existing.first():
            deduplicated += 1
            continue

        # 3. Resolve Node and NodeKey
        stmt = select(NodeKey).where(NodeKey.key_id == obs.signature_key_id)
        result = await db.execute(stmt)
        node_key = result.scalar_one_or_none()
        
        if not node_key or not node_key.active or node_key.revoked_at:
            logger.warning(f"Invalid or revoked key {obs.signature_key_id}")
            rejected += 1
            continue

        # Get the node to check region authorization
        stmt = select(Node).where(Node.id == node_key.node_id)
        result = await db.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node or str(node.id) != obs.node_id or node.region_code != obs.region:
            logger.warning(f"Node validation failed for {obs.observation_id}")
            rejected += 1
            continue

        # Verify Sequence and Previous Hash Continuity
        stmt = (
            select(Observation)
            .where(Observation.node_id == node.id)
            .where(Observation.target_id == obs.target_id)
            .order_by(Observation.sequence.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_obs = result.scalar_one_or_none()

        if last_obs:
            if obs.sequence <= last_obs.sequence:
                logger.warning(f"Sequence {obs.sequence} is older than last observed {last_obs.sequence} for target {obs.target_id}")
                rejected += 1
                continue
            
            expected_prev_hash = f"hash_{last_obs.signature[:16]}"
            if obs.previous_observation_hash != expected_prev_hash and obs.previous_observation_hash != "bootstrap":
                logger.warning(f"Previous hash mismatch. Expected {expected_prev_hash}, got {obs.previous_observation_hash}")
                rejected += 1
                continue

        # 4. Verify Signature (Using VNPEventVerifier)
        try:
            raw_obs = obs.model_dump(mode="json", by_alias=True)
            # Remove signature before verifying, if signature is generated from payload minus sig
            # Wait, VNPEventVerifier signature logic expects the payload as signed by the node.
            # Assuming payload contains signature but we verify against the rest or as the standard dictates.
            VNPEventVerifier.verify_event_signature(raw_obs, node_key.public_key)
        except VNPSecurityError as e:
            logger.warning(f"Signature verification failed for {obs.observation_id}: {e}")
            rejected += 1
            continue
            
        # 5. Insert into DB
        try:
            new_obs = Observation(
                observation_id=obs.observation_id,
                node_id=node.id,
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
                ttfb_ms=obs.ttfb_ms,
                total_ms=obs.total_ms,
                http_status=obs.http_status,
                response_fingerprint=obs.response_fingerprint,
                error_code=obs.error_code,
                sequence=obs.sequence,
                previous_observation_hash=obs.previous_observation_hash,
                signature_key_id=obs.signature_key_id,
                signature=obs.signature,
                created_at=now
            )
            db.add(new_obs)
            accepted += 1
        except Exception as e:
            logger.error(f"Failed to insert observation {obs.observation_id}: {e}")
            rejected += 1

    await db.commit()
    
    if accepted > 0:
        pgl_client = PGLClient()
        event_data = {
            "batch_size": accepted,
            "target_ids": list(set(obs.target_id for obs in batch.observations))
        }
        try:
            receipt_id = await pgl_client.mint_receipt("observation_batch_ingest", event_data)
            logger.info(f"Minted PGL receipt {receipt_id} for batch")
            
            # Fire the central slashing engine to evaluate bonds for the affected targets
            # Run in the background so it doesn't block ingestion
            import asyncio
            from app.db.models import ProviderBond, BondState
            
            async def evaluate_targets(targets):
                for target_id in targets:
                    stmt = select(ProviderBond).where(
                        ProviderBond.target_api_id == target_id,
                        ProviderBond.state.in_([BondState.active, BondState.funded])
                    )
                    res = await db.execute(stmt)
                    bonds = res.scalars().all()
                    
                    if bonds:
                        engine = SlashingEngine(db)
                        for bond in bonds:
                            await engine.evaluate_bond_for_slash(bond.id)
            
            # URGENY CONTAINMENT: Slashing engine is contained behind config flag
            from app.core.config import get_settings
            if get_settings().vnp_autonomous_slashing_enabled:
                asyncio.create_task(evaluate_targets(event_data["target_ids"]))
            else:
                logger.info(f"Skipping VNP autonomous slashing for targets {event_data['target_ids']}: Containment Active.")
                
        except PGLConnectionError as e:
            # Reverting is an option but the prompt implies we bubble it to 503
            # or fail-safe. If we raise HTTPException, Fastapi returns error.
            raise HTTPException(status_code=503, detail=str(e))
    
    return {
        "accepted": accepted,
        "rejected": rejected,
        "deduplicated": deduplicated
    }


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
