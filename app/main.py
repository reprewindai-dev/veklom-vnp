#!/usr/bin/env python3
"""
VNP v0.1.5 FastAPI Service
Open-community API quality measurement platform
Standalone service (port 8089)

Architecture:
- Real-time scoring engine
- Provider claim system (DNS verification)
- Badge generation
- Public API endpoints
- Agent SDK support
- Integrated React UI
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import asyncio
import hashlib
import os
import re
import logging
from typing import Optional, Dict, List

# Try importing dns resolver, handle if missing
try:
    import dns.resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================
app = FastAPI(
    title="VNP v0.1.5",
    description="Open-community API quality measurement",
    version="0.1.5"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DATA MODELS
# ============================================================================
class Measurement(BaseModel):
    api_id: str
    region: str
    latency_p99: float
    latency_p95: float
    error_rate: float
    availability: float
    timestamp: datetime

class Score(BaseModel):
    api_id: str
    composite_score: float
    dimensions: Dict[str, float]
    confidence: float
    updated_at: datetime

class ProviderClaim(BaseModel):
    api_id: str
    api_domain: str
    company_name: str
    contact_email: str

class ClaimVerification(BaseModel):
    api_id: str
    dns_token: str
    status: str  # pending, verified, failed

# ============================================================================
# IN-MEMORY STORAGE (Replace with DB in production)
# ============================================================================
measurements_store: Dict[str, List[Measurement]] = {}
scores_store: Dict[str, Score] = {}
claims_store: Dict[str, ProviderClaim] = {}
claim_verifications: Dict[str, ClaimVerification] = {}

# Sample data for demo
SAMPLE_APIS = [
    "openai-api",
    "anthropic-api",
    "together-ai",
    "replicate-api",
    "huggingface-api"
]

# 10-Dimensional Scoring Weights (Locked until 2027-06-22)
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

# ============================================================================
# SCORING ENGINE
# ============================================================================
def calculate_composite_score(measurements: List[Measurement]) -> Score:
    """
    Calculate 10-dimensional composite score from measurements.
    Formula locked until 2027-06-22.
    """
    if not measurements:
        return None
    
    # Aggregate measurements (simple averaging for demo)
    avg_latency = sum(m.latency_p99 for m in measurements) / len(measurements)
    avg_error_rate = sum(m.error_rate for m in measurements) / len(measurements)
    avg_availability = sum(m.availability for m in measurements) / len(measurements)
    
    # Normalize scores (0-100)
    latency_score = max(0, 100 - (avg_latency / 10))  # Lower is better
    error_score = max(0, 100 - (avg_error_rate * 100))
    availability_score = avg_availability * 100
    throughput_score = 80  # Placeholder
    security_score = 85  # Placeholder
    documentation_score = 75  # Placeholder
    versioning_score = 80  # Placeholder
    x402_score = 70  # Placeholder
    rate_limit_score = 75  # Placeholder
    dx_score = 78  # Placeholder
    
    # Weighted composite
    dimensions = {
        "p99_latency": latency_score,
        "error_rate": error_score,
        "availability": availability_score,
        "throughput": throughput_score,
        "security": security_score,
        "documentation": documentation_score,
        "versioning": versioning_score,
        "x402_compliance": x402_score,
        "rate_limit_transparency": rate_limit_score,
        "developer_experience": dx_score,
    }
    
    composite = sum(
        dimensions[key] * SCORING_WEIGHTS[key]
        for key in dimensions.keys()
    )
    
    return Score(
        api_id=measurements[0].api_id,
        composite_score=composite,
        dimensions=dimensions,
        confidence=min(100, len(measurements) / 100 * 100),  # Confidence based on sample size
        updated_at=datetime.utcnow()
    )

# ============================================================================
# PROVIDER CLAIM SYSTEM (DNS Verification)
# ============================================================================
async def verify_dns_claim(api_domain: str, dns_token: str) -> bool:
    """
    Verify provider claim via DNS TXT record.
    Expected TXT record: vnp-verify={dns_token}
    """
    if not HAS_DNS:
        logger.warning("dnspython not installed, skipping real dns verification")
        return False
        
    try:
        answers = dns.resolver.resolve(f"_vnp.{api_domain}", "TXT")
        for rdata in answers:
            for txt_data in rdata.strings:
                if txt_data.decode() == f"vnp-verify={dns_token}":
                    return True
        return False
    except Exception as e:
        logger.warning(f"DNS verification failed for {api_domain}: {e}")
        return False

def generate_claim_token(api_id: str, company_name: str) -> str:
    """Generate unique DNS verification token."""
    token_data = f"{api_id}:{company_name}:{datetime.utcnow().isoformat()}"
    return hashlib.sha256(token_data.encode()).hexdigest()[:16]

# ============================================================================
# BADGE GENERATION
# ============================================================================
def generate_badge_svg(api_id: str, score: float) -> str:
    """
    Generate auto-updating SVG badge based on score.
    Gold: ≥85, Silver: ≥75, Bronze: ≥65
    """
    if score >= 85:
        color = "#FFD700"
        label = "Gold"
    elif score >= 75:
        color = "#C0C0C0"
        label = "Silver"
    elif score >= 65:
        color = "#CD7F32"
        label = "Bronze"
    else:
        color = "#808080"
        label = "Unrated"
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50">
    <rect width="200" height="50" fill="#1a1a1a"/>
    <text x="10" y="20" font-family="Arial" font-size="14" fill="#ffffff">VNP</text>
    <text x="10" y="35" font-family="Arial" font-size="12" fill="{color}">{label} ({score:.1f})</text>
    <rect x="100" y="10" width="80" height="30" fill="{color}" opacity="0.3"/>
    <text x="140" y="30" font-family="Arial" font-size="12" fill="{color}" text-anchor="middle">{score:.0f}</text>
</svg>'''
    return svg

# ============================================================================
# REAL-TIME SCORING (WebSocket support)
# ============================================================================
async def score_stream_generator():
    """
    Generate real-time score updates via Server-Sent Events.
    Simulates continuous measurement stream.
    """
    while True:
        for api_id in SAMPLE_APIS:
            if api_id in scores_store:
                score = scores_store[api_id]
                yield f"data: {json.dumps({'api_id': api_id, 'score': score.composite_score, 'timestamp': score.updated_at.isoformat()})}\n\n"
        await asyncio.sleep(5)  # Update every 5 seconds

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.5",
        "timestamp": datetime.utcnow().isoformat()
    }

# --- Measurements ---
@app.post("/api/v1/measurements")
async def post_measurement(measurement: Measurement):
    """
    Post a new measurement.
    In production: from k6 agents or external data pipeline.
    """
    api_id = measurement.api_id
    if api_id not in measurements_store:
        measurements_store[api_id] = []
    
    measurements_store[api_id].append(measurement)
    
    # Trigger scoring if we have 100+ measurements
    if len(measurements_store[api_id]) >= 100:
        score = calculate_composite_score(measurements_store[api_id][-100:])
        scores_store[api_id] = score
        logger.info(f"Scored {api_id}: {score.composite_score:.1f}")
    
    return {"status": "received", "api_id": api_id}

@app.get("/api/v1/measurements/{api_id}")
async def get_measurements(api_id: str, limit: int = 100):
    """Get recent measurements for an API."""
    if api_id not in measurements_store:
        raise HTTPException(status_code=404, detail=f"No measurements for {api_id}")
    
    measurements = measurements_store[api_id][-limit:]
    return {
        "api_id": api_id,
        "count": len(measurements),
        "measurements": [m.dict() for m in measurements]
    }

# --- Scores ---
@app.get("/api/v1/scores/{api_id}")
async def get_score(api_id: str):
    """Get current composite score for an API."""
    if api_id not in scores_store:
        raise HTTPException(status_code=404, detail=f"No score yet for {api_id}")
    
    score = scores_store[api_id]
    return {
        "api_id": api_id,
        "composite_score": score.composite_score,
        "dimensions": score.dimensions,
        "confidence": score.confidence,
        "updated_at": score.updated_at.isoformat()
    }

@app.get("/api/v1/scores")
async def get_all_scores():
    """Get all current scores."""
    return {
        "count": len(scores_store),
        "scores": {
            api_id: {
                "composite_score": score.composite_score,
                "updated_at": score.updated_at.isoformat()
            }
            for api_id, score in scores_store.items()
        }
    }

@app.get("/api/v1/scores/stream")
async def score_stream():
    """
    Real-time score updates via Server-Sent Events (SSE).
    Clients can subscribe to live score changes.
    """
    return StreamingResponse(
        score_stream_generator(),
        media_type="text/event-stream"
    )

# --- Badges ---
@app.get("/api/v1/badge/{api_id}.svg")
async def get_badge(api_id: str):
    """
    Get auto-updating SVG badge for an API.
    Can be embedded in GitHub, docs, websites.
    """
    if api_id not in scores_store:
        # Return default badge if no score yet
        svg = generate_badge_svg(api_id, 0)
    else:
        score = scores_store[api_id]
        svg = generate_badge_svg(api_id, score.composite_score)
    
    return FileResponse(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=300",  # 5-minute cache
            "Content-Disposition": f'inline; filename="{api_id}_vnp_badge.svg"'
        }
    )

@app.get("/api/v1/badge/{api_id}.json")
async def get_badge_json(api_id: str):
    """
    Get badge data as JSON for dynamic rendering.
    """
    if api_id not in scores_store:
        return {"api_id": api_id, "score": None, "label": "Unrated", "color": "#808080"}
    
    score = scores_store[api_id].composite_score
    if score >= 85:
        label, color = "Gold", "#FFD700"
    elif score >= 75:
        label, color = "Silver", "#C0C0C0"
    elif score >= 65:
        label, color = "Bronze", "#CD7F32"
    else:
        label, color = "Unrated", "#808080"
    
    return {
        "api_id": api_id,
        "score": score,
        "label": label,
        "color": color,
        "updated_at": scores_store[api_id].updated_at.isoformat()
    }

# --- Provider Claims ---
@app.post("/api/v1/claims")
async def create_claim(claim: ProviderClaim, background_tasks: BackgroundTasks):
    """
    Create a new provider claim.
    Returns DNS token for verification.
    """
    api_id = claim.api_id
    
    # Generate verification token
    token = generate_claim_token(api_id, claim.company_name)
    
    # Store claim
    claims_store[api_id] = claim
    claim_verifications[api_id] = ClaimVerification(
        api_id=api_id,
        dns_token=token,
        status="pending"
    )
    
    # Start background verification (every 10 seconds for 2 hours)
    background_tasks.add_task(verify_claim_background, api_id, claim.api_domain, token)
    
    logger.info(f"Claim created for {api_id}, token: {token}")
    
    return {
        "api_id": api_id,
        "status": "pending",
        "dns_record_required": f"_vnp.{claim.api_domain} TXT vnp-verify={token}",
        "instructions": [
            f"1. Add DNS TXT record: _vnp.{claim.api_domain} = vnp-verify={token}",
            "2. Wait for automatic verification (up to 2 hours)",
            f"3. Dashboard available at: https://vnp.io/provider/{api_id}",
            "4. When verified, email alerts will be active"
        ]
    }

async def verify_claim_background(api_id: str, api_domain: str, token: str):
    """Background task to verify DNS claim every 10 seconds."""
    max_attempts = 720  # 2 hours (720 * 10 seconds)
    attempts = 0
    
    while attempts < max_attempts:
        attempts += 1
        verified = await verify_dns_claim(api_domain, token)
        
        if verified:
            claim_verifications[api_id].status = "verified"
            logger.info(f"Claim verified for {api_id}")
            # TODO: Send email alert to contact_email
            return
        
        await asyncio.sleep(10)
    
    claim_verifications[api_id].status = "failed"
    logger.warning(f"Claim verification timeout for {api_id}")

@app.get("/api/v1/claims/{api_id}")
async def get_claim_status(api_id: str):
    """Get claim status for an API."""
    if api_id not in claim_verifications:
        raise HTTPException(status_code=404, detail=f"No claim for {api_id}")
    
    verification = claim_verifications[api_id]
    claim = claims_store[api_id]
    
    return {
        "api_id": api_id,
        "company": claim.company_name,
        "status": verification.status,
        "verified_at": datetime.utcnow().isoformat() if verification.status == "verified" else None
    }

# --- Agent SDKs Support ---
@app.get("/api/v1/sdk/select")
async def sdk_select_api(candidates: str, constraint: Optional[str] = None):
    """
    Agent SDK endpoint for selecting best API.
    """
    api_list = [api.strip() for api in candidates.split(",")]
    
    candidates_filtered = []
    for api_id in api_list:
        if api_id in scores_store:
            score = scores_store[api_id]
            candidates_filtered.append({
                "api": api_id,
                "score": score.composite_score,
                "dimensions": score.dimensions
            })
    
    candidates_filtered.sort(key=lambda x: x["score"], reverse=True)
    
    if not candidates_filtered:
        raise HTTPException(status_code=404, detail="No scored APIs in candidates")
    
    best = candidates_filtered[0]
    
    return {
        "selected_api": best["api"],
        "score": best["score"],
        "all_candidates": candidates_filtered,
        "uri": f"https://api.{best['api'].replace('-api', '.io')}"
    }

# --- Dummy Admin Endpoints for the UI ---
@app.post("/api/v1/admin/debug/storm")
async def admin_storm():
    return {"status": "storm_simulated"}

@app.post("/api/v1/admin/debug/slash")
async def admin_slash(payload: dict):
    return {"status": "slashed", "peer": payload.get("peer")}

@app.post("/api/v1/admin/config")
async def admin_config(payload: dict):
    return {"status": "config_updated"}

@app.get("/api/v1/beacon/topology")
async def get_topology():
    return {
        "topology": {
            "networkStatus": "ACTIVE",
            "activeNodes": 12,
            "shardDepth": 4,
            "securityLevel": "EAL4+"
        }
    }

# ============================================================================
# INITIALIZATION
# ============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize with sample data."""
    logger.info("VNP v0.1.5 service starting...")
    
    for api_id in SAMPLE_APIS:
        measurements = [
            Measurement(
                api_id=api_id,
                region="us-east",
                latency_p99=random_float(50, 200),
                latency_p95=random_float(30, 150),
                error_rate=random_float(0.001, 0.05),
                availability=random_float(0.95, 0.99),
                timestamp=datetime.utcnow() - timedelta(minutes=i)
            )
            for i in range(150)
        ]
        measurements_store[api_id] = measurements
        score = calculate_composite_score(measurements[-100:])
        scores_store[api_id] = score
        logger.info(f"Initialized {api_id}: score {score.composite_score:.1f}")

def random_float(min_val: float, max_val: float) -> float:
    import random
    return random.uniform(min_val, max_val)

# ============================================================================
# ROOT / FRONTEND STATIC MOUNT
# ============================================================================
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    async def root():
        """Root endpoint fallback."""
        return {
            "service": "Veklom Nexus Protocol v0.1.5",
            "status": "running",
            "port": 8089
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8089, reload=True)
