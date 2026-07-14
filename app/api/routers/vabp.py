import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import VabpRun, VabpRunState, VabpTestResult, TrustCertificate, Api

router = APIRouter(prefix="/vabp", tags=["vabp"])

class VabpRunRequest(BaseModel):
    target_id: str = Field(..., description="API DID or target string")
    suite_version: str = Field("v1.0", description="Version of the test suite to run")

class VabpTestResultSchema(BaseModel):
    test_name: str
    dimension: str
    passed: bool
    score_awarded: int
    max_score: int

class VabpRunResponse(BaseModel):
    id: uuid.UUID
    target_id: str
    run_state: str
    total_score: Optional[int]
    suite_version: str
    started_at: datetime
    completed_at: Optional[datetime]
    results: List[VabpTestResultSchema] = []

class TrustCertificateResponse(BaseModel):
    id: uuid.UUID
    target_id: str
    vabp_run_id: uuid.UUID
    score: int
    passed_threshold: bool
    issued_at: datetime
    expires_at: datetime
    pgl_evidence_id: Optional[str]
    revoked: bool

async def execute_vabp_tests(run_id: uuid.UUID, target_id: str, db: AsyncSession):
    # This is a synthetic deterministic execution.
    # In a real environment, this would reach out to the actual API using HTTP clients.
    
    # Let's wait a moment to simulate network time
    await asyncio.sleep(2)
    
    # Synthetic logic based on target_id (just deterministic logic for the sandbox)
    is_good = "byos" in target_id.lower() or "cappo" in target_id.lower()
    
    tests = [
        {"name": "TLS Security Validation", "dimension": "security", "max_score": 100, "passed": True},
        {"name": "PGL Identity Verification", "dimension": "authentication", "max_score": 200, "passed": is_good},
        {"name": "Zero-Trust Header Check", "dimension": "compliance", "max_score": 200, "passed": is_good},
        {"name": "OpenAPI Spec Adherence", "dimension": "interoperability", "max_score": 250, "passed": True},
        {"name": "VNP SLA Instrumentation", "dimension": "instrumentation", "max_score": 250, "passed": True},
    ]
    
    total_score = 0
    results = []
    
    for t in tests:
        awarded = t["max_score"] if t["passed"] else 0
        total_score += awarded
        
        tr = VabpTestResult(
            run_id=run_id,
            test_name=t["name"],
            dimension=t["dimension"],
            passed=t["passed"],
            score_awarded=awarded,
            max_score=t["max_score"]
        )
        db.add(tr)
    
    # Update run
    run = await db.get(VabpRun, run_id)
    if run:
        run.run_state = VabpRunState.completed
        run.total_score = total_score
        run.completed_at = datetime.now(timezone.utc)
        
    await db.commit()


@router.post("/runs", response_model=VabpRunResponse, status_code=202)
async def start_vabp_run(req: VabpRunRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Trigger an ephemeral VABP sandbox test run.
    """
    # Create the run in pending state
    run = VabpRun(
        target_id=req.target_id,
        suite_version=req.suite_version,
        run_state=VabpRunState.running
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    
    # Queue background task to execute tests
    background_tasks.add_task(execute_vabp_tests, run.id, req.target_id, db)
    
    return VabpRunResponse(
        id=run.id,
        target_id=run.target_id,
        run_state=run.run_state.value,
        total_score=run.total_score,
        suite_version=run.suite_version,
        started_at=run.started_at,
        completed_at=run.completed_at
    )


@router.get("/runs/{run_id}", response_model=VabpRunResponse)
async def get_vabp_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the status and results of a VABP test run.
    """
    run = await db.get(VabpRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Get results
    stmt = select(VabpTestResult).where(VabpTestResult.run_id == run_id)
    result_rows = (await db.execute(stmt)).scalars().all()
    
    results = [
        VabpTestResultSchema(
            test_name=r.test_name,
            dimension=r.dimension,
            passed=r.passed,
            score_awarded=r.score_awarded,
            max_score=r.max_score
        ) for r in result_rows
    ]
    
    return VabpRunResponse(
        id=run.id,
        target_id=run.target_id,
        run_state=run.run_state.value,
        total_score=run.total_score,
        suite_version=run.suite_version,
        started_at=run.started_at,
        completed_at=run.completed_at,
        results=results
    )


@router.post("/runs/{run_id}/certificate", response_model=TrustCertificateResponse)
async def issue_certificate(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Issue a trust certificate based on a completed VABP test run.
    """
    run = await db.get(VabpRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if run.run_state != VabpRunState.completed:
        raise HTTPException(status_code=400, detail="Cannot issue certificate: run is not completed")
        
    # Check if certificate already exists
    stmt = select(TrustCertificate).where(TrustCertificate.vabp_run_id == run_id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing
        
    # VABP threshold is 750 / 1000
    passed_threshold = run.total_score is not None and run.total_score >= 750
    
    from datetime import timedelta
    # Issue cert for 1 year
    expires = datetime.now(timezone.utc) + timedelta(days=365)
    
    cert = TrustCertificate(
        target_id=run.target_id,
        vabp_run_id=run.id,
        score=run.total_score,
        passed_threshold=passed_threshold,
        expires_at=expires,
        pgl_evidence_id=None,
    )
    
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    
    return cert
