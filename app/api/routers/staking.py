from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging

from app.db.database import get_db
from app.db.models import (
    ProviderBond, BondState, BondCondition, BondChallenge, ChallengeState,
    ChallengeEvidence, BondResolution, MeasurementWindow, VabpTestResult
)
from app.pgl.client import PGLClient, PGLConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Staking & Bonds"])

class ConditionCreate(BaseModel):
    metric_type: str
    operator: str
    threshold_value: float

class BondCreateRequest(BaseModel):
    provider_id: str
    target_api_id: str
    amount_minor: int
    currency: str = "USD"
    conditions: List[ConditionCreate]

class BondResponse(BaseModel):
    id: str
    provider_id: str
    target_api_id: str
    state: str
    amount_minor: int
    currency: str

class ChallengeRequest(BaseModel):
    challenger_id: str
    measurement_window_id: Optional[str] = None
    vabp_run_id: Optional[str] = None

class ChallengeResponse(BaseModel):
    challenge_id: str
    state: str
    evidence_id: str

@router.post("/bonds", response_model=BondResponse, status_code=201)
async def create_bond(req: BondCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a new Provider Bond in DRAFT state."""
    new_bond = ProviderBond(
        provider_id=uuid.UUID(req.provider_id),
        target_api_id=req.target_api_id,
        amount_minor=req.amount_minor,
        currency=req.currency,
        state=BondState.draft
    )
    db.add(new_bond)
    await db.flush()

    for cond in req.conditions:
        new_cond = BondCondition(
            bond_id=new_bond.id,
            metric_type=cond.metric_type,
            operator=cond.operator,
            threshold_value=cond.threshold_value
        )
        db.add(new_cond)
    
    await db.commit()
    await db.refresh(new_bond)
    return {
        "id": str(new_bond.id),
        "provider_id": str(new_bond.provider_id),
        "target_api_id": new_bond.target_api_id,
        "state": new_bond.state.value,
        "amount_minor": new_bond.amount_minor,
        "currency": new_bond.currency
    }

@router.post("/bonds/{bond_id}/fund", response_model=BondResponse)
async def fund_bond(bond_id: str, db: AsyncSession = Depends(get_db)):
    """Transition a DRAFT bond to FUNDED and ACTIVE."""
    stmt = select(ProviderBond).where(ProviderBond.id == uuid.UUID(bond_id))
    result = await db.execute(stmt)
    bond = result.scalar_one_or_none()
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")
    
    if bond.state != BondState.draft:
        raise HTTPException(status_code=400, detail=f"Bond is not in draft state (current: {bond.state.value})")
    
    now = datetime.now(timezone.utc)
    bond.state = BondState.active
    bond.funded_at = now
    
    try:
        pgl_client = PGLClient()
        receipt_id = await pgl_client.mint_receipt("bond_funded", {"bond_id": str(bond.id), "amount": bond.amount_minor})
        logger.info(f"Minted PGL receipt {receipt_id} for funding bond {bond.id}")
    except PGLConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    await db.commit()
    await db.refresh(bond)
    return {
        "id": str(bond.id),
        "provider_id": str(bond.provider_id),
        "target_api_id": bond.target_api_id,
        "state": bond.state.value,
        "amount_minor": bond.amount_minor,
        "currency": bond.currency
    }

@router.post("/bonds/{bond_id}/challenges", response_model=ChallengeResponse, status_code=202)
async def challenge_bond(bond_id: str, req: ChallengeRequest, db: AsyncSession = Depends(get_db)):
    """Challenge a bond by providing empirical evidence."""
    if not req.measurement_window_id and not req.vabp_run_id:
        raise HTTPException(status_code=400, detail="Must provide measurement_window_id or vabp_run_id as evidence")
    
    stmt = select(ProviderBond).where(ProviderBond.id == uuid.UUID(bond_id))
    result = await db.execute(stmt)
    bond = result.scalar_one_or_none()
    
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")
    
    if bond.state not in [BondState.active, BondState.breach_pending]:
        raise HTTPException(status_code=400, detail=f"Bond cannot be challenged in state {bond.state.value}")

    evidence_payload = {}
    if req.measurement_window_id:
        w_stmt = select(MeasurementWindow).where(MeasurementWindow.id == uuid.UUID(req.measurement_window_id))
        w_res = await db.execute(w_stmt)
        if not w_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Measurement window not found")
        evidence_payload["source"] = "measurement_window"
    
    if req.vabp_run_id:
        v_stmt = select(VabpTestResult).where(VabpTestResult.run_id == uuid.UUID(req.vabp_run_id))
        v_res = await db.execute(v_stmt)
        if not v_res.first():
            raise HTTPException(status_code=404, detail="VABP test results not found")
        evidence_payload["source"] = "vabp_run"

    challenge = BondChallenge(
        bond_id=bond.id,
        challenger_id=req.challenger_id,
        state=ChallengeState.verifying
    )
    db.add(challenge)
    await db.flush()

    evidence = ChallengeEvidence(
        challenge_id=challenge.id,
        measurement_window_id=uuid.UUID(req.measurement_window_id) if req.measurement_window_id else None,
        vabp_run_id=uuid.UUID(req.vabp_run_id) if req.vabp_run_id else None,
        evidence_payload=evidence_payload
    )
    db.add(evidence)
    
    bond.state = BondState.breach_pending
    
    await db.commit()
    await db.refresh(challenge)
    await db.refresh(evidence)
    
    return {
        "challenge_id": str(challenge.id),
        "state": challenge.state.value,
        "evidence_id": str(evidence.id)
    }

@router.post("/bonds/{bond_id}/resolutions", status_code=200)
async def resolve_challenge(bond_id: str, challenge_id: str = Body(embed=True), action: str = Body(embed=True), db: AsyncSession = Depends(get_db)):
    """Resolve a challenge by slashing or releasing the bond."""
    if action not in ["slash", "release", "dismiss"]:
        raise HTTPException(status_code=400, detail="Action must be 'slash', 'release', or 'dismiss'")
        
    c_stmt = select(BondChallenge).where(BondChallenge.id == uuid.UUID(challenge_id))
    c_res = await db.execute(c_stmt)
    challenge = c_res.scalar_one_or_none()
    
    if not challenge or str(challenge.bond_id) != bond_id:
        raise HTTPException(status_code=404, detail="Challenge not found for this bond")
        
    b_stmt = select(ProviderBond).where(ProviderBond.id == uuid.UUID(bond_id))
    b_res = await db.execute(b_stmt)
    bond = b_res.scalar_one_or_none()
    
    now = datetime.now(timezone.utc)
    
    if action == "slash":
        bond.state = BondState.slashed
        challenge.state = ChallengeState.upheld
    elif action == "release":
        bond.state = BondState.released
        challenge.state = ChallengeState.rejected
    else:
        bond.state = BondState.active
        challenge.state = ChallengeState.rejected
        
    challenge.resolved_at = now
    
    resolution = BondResolution(
        challenge_id=challenge.id,
        action=action,
        amount_minor=bond.amount_minor,
        pgl_receipt_id=None
    )
    
    try:
        pgl_client = PGLClient()
        receipt_id = await pgl_client.mint_receipt("challenge_resolved", {
            "challenge_id": str(challenge.id),
            "bond_id": str(bond.id),
            "action": action
        })
        resolution.pgl_receipt_id = receipt_id
        logger.info(f"Minted PGL receipt {receipt_id} for resolution {action} on challenge {challenge.id}")
    except PGLConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    db.add(resolution)
    
    await db.commit()
    
    return {"status": "resolved", "action": action, "bond_state": bond.state.value}
