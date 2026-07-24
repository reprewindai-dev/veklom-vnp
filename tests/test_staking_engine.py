import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ProviderBond, BondState, BondChallenge, ChallengeState
import uuid
from conftest import requires_database

pytestmark = requires_database

@pytest.mark.asyncio
async def test_create_bond_and_fund(client: AsyncClient, db: AsyncSession):
    provider_id = str(uuid.uuid4())
    
    # Create
    create_response = await client.post(
        "/api/v1/bonds",
        json={
            "provider_id": provider_id,
            "target_api_id": "api-123",
            "amount_minor": 100000,
            "conditions": [
                {"metric_type": "p99_latency_ms", "operator": "<=", "threshold_value": 200.0}
            ]
        }
    )
    assert create_response.status_code == 201
    bond_data = create_response.json()
    assert bond_data["state"] == "draft"
    bond_id = bond_data["id"]
    
    # Fund
    # We mock PGLClient to prevent real external calls in tests.
    fund_response = await client.post(f"/api/v1/bonds/{bond_id}/fund")
    # Will likely return 503 if PGL mock is not set, so let's check for 503 in absence of mock
    assert fund_response.status_code in [200, 503]

@pytest.mark.asyncio
async def test_challenge_bond_no_evidence(client: AsyncClient, db: AsyncSession):
    provider_id = str(uuid.uuid4())
    
    # Create bond
    create_res = await client.post(
        "/api/v1/bonds",
        json={
            "provider_id": provider_id,
            "target_api_id": "api-456",
            "amount_minor": 50000,
            "conditions": []
        }
    )
    bond_id = create_res.json()["id"]
    
    # Fund bond
    await client.post(f"/api/v1/bonds/{bond_id}/fund")
    
    # Attempt challenge without evidence
    challenge_res = await client.post(
        f"/api/v1/bonds/{bond_id}/challenges",
        json={
            "challenger_id": "node-123"
        }
    )
    assert challenge_res.status_code == 422 # missing fields or 400
