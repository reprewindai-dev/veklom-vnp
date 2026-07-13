import pytest
import uuid
import httpx
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProviderBond, BondState, BondChallenge, ChallengeState, BondResolution
from app.services.slashing_engine import SlashingEngine
from app.pgl.client import PGLClient

@pytest.fixture
def mock_httpx_post():
    with patch("httpx.AsyncClient.post") as mock_post:
        yield mock_post

@pytest.fixture
def mock_pgl_client():
    with patch("app.services.slashing_engine.PGLClient") as mock_client:
        instance = mock_client.return_value
        instance.mint_receipt = AsyncMock(return_value="mock_pgl_receipt_id")
        yield instance

@pytest.mark.asyncio
async def test_evaluate_bond_for_slash_and_execute(mock_httpx_post, mock_pgl_client):
    # Setup mock db
    from unittest.mock import MagicMock
    
    mock_db = MagicMock(spec=AsyncSession)
    mock_res = MagicMock()
    
    bond_id = uuid.uuid4()
    bond = ProviderBond(
        id=bond_id,
        provider_id=uuid.uuid4(),
        target_api_id="api-123",
        amount_minor=10000,
        currency="USD",
        state=BondState.active
    )
    
    mock_res.scalar_one_or_none.return_value = bond
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    # Setup httpx mock response
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"authorized": True}
    mock_httpx_post.return_value = mock_response

    # Initialize Engine
    engine = SlashingEngine(mock_db)

    # Execute
    await engine.evaluate_bond_for_slash(bond_id)

    # Verify httpx was called
    assert mock_httpx_post.called
    call_args, call_kwargs = mock_httpx_post.call_args
    assert "authorize-slash" in call_args[0]
    assert call_kwargs["json"]["bond_id"] == str(bond_id)
    assert call_kwargs["json"]["pgl_evidence_id"] == "mock_pgl_receipt_id"

    # Verify database state was updated
    assert bond.state == BondState.slashed

    # Verify resolution was created
    assert mock_db.add.called
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, BondResolution) or isinstance(added_obj, BondChallenge)

