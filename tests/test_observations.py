import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.api.routers.vnp_ingest import ingest_observations_batches, ObservationBatch, CanonicalObservation
from app.core.security import VNPEventVerifier, VNPSecurityError
from app.db.models import Node, NodeKey, Observation

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

@pytest.fixture
def valid_observation():
    now = datetime.now(timezone.utc)
    return CanonicalObservation(
        observation_id="obs_123",
        node_id="00000000-0000-0000-0000-000000000001",
        region="us-ashburn",
        physical_location="Ashburn, Virginia, United States",
        target_id="api_veklom_com",
        measurement_profile="ping",
        measurement_version="1.0",
        started_at=now - timedelta(seconds=1),
        completed_at=now,
        total_ms=45,
        sequence=2,
        previous_observation_hash="hash_1234567890abcdef",
        signature_key_id="key_1",
        signature="sig_abc123"
    )

@pytest.mark.asyncio
async def test_valid_observation_ingest(mocker, mock_db, valid_observation):
    # Mock VNPEventVerifier
    mocker.patch.object(VNPEventVerifier, "verify_event_signature", return_value=True)
    mock_pgl = mocker.patch("app.api.routers.vnp_ingest.PGLClient")
    mock_pgl.return_value.mint_receipt = AsyncMock(return_value="pgl_receipt_123")

    # Mock DB executes
    mock_execute = AsyncMock()
    # first call: existing observation check -> returns None
    # second call: NodeKey lookup -> returns NodeKey
    # third call: Node lookup -> returns Node
    # fourth call: sequence check -> returns previous Observation
    
    mock_node_key = NodeKey(key_id="key_1", node_id="00000000-0000-0000-0000-000000000001", public_key="pub_key", active=True)
    mock_node = Node(id="00000000-0000-0000-0000-000000000001", region_code="us-ashburn")
    mock_prev_obs = Observation(sequence=1, signature="1234567890abcdef_sig")
    
    # We will just patch the execute to return a mock scalar_one_or_none that cycles
    # But since execute returns an object with `first` or `scalar_one_or_none`, let's make a smart mock
    
    class SmartMockResult:
        def __init__(self, val=None):
            self.val = val
        def first(self):
            return self.val
        def scalar_one_or_none(self):
            return self.val

    def side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "from vnp_observations" in stmt_str and "observation_id =" in stmt_str:
            return SmartMockResult(None) # Duplicate check
        if "from vnp_node_keys" in stmt_str:
            return SmartMockResult(mock_node_key)
        if "from vnp_nodes" in stmt_str:
            return SmartMockResult(mock_node)
        if "from vnp_observations" in stmt_str and "order by" in stmt_str:
            return SmartMockResult(mock_prev_obs)
        return SmartMockResult(None)

    mock_db.execute.side_effect = side_effect

    batch = ObservationBatch(observations=[valid_observation])
    result = await ingest_observations_batches(batch=batch, db=mock_db)
    
    assert result["accepted"] == 1
    assert result["rejected"] == 0
    assert result["deduplicated"] == 0
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_invalid_region_reject(mocker, mock_db, valid_observation):
    mocker.patch.object(VNPEventVerifier, "verify_event_signature", return_value=True)

    mock_node_key = NodeKey(key_id="key_1", node_id="00000000-0000-0000-0000-000000000001", public_key="pub_key", active=True)
    # The node is registered in de-nuremberg but observation claims us-ashburn.
    mock_node = Node(id="00000000-0000-0000-0000-000000000001", region_code="de-nuremberg")
    mock_prev_obs = Observation(sequence=1, signature="1234567890abcdef_sig")
    
    class SmartMockResult:
        def __init__(self, val=None):
            self.val = val
        def first(self):
            return self.val
        def scalar_one_or_none(self):
            return self.val

    def side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "from vnp_observations" in stmt_str and "observation_id =" in stmt_str:
            return SmartMockResult(None) # Duplicate check
        if "from vnp_node_keys" in stmt_str:
            return SmartMockResult(mock_node_key)
        if "from vnp_nodes" in stmt_str:
            return SmartMockResult(mock_node)
        if "from vnp_observations" in stmt_str and "order by" in stmt_str:
            return SmartMockResult(mock_prev_obs)
        return SmartMockResult(None)

    mock_db.execute.side_effect = side_effect

    batch = ObservationBatch(observations=[valid_observation])
    result = await ingest_observations_batches(batch=batch, db=mock_db)
    
    assert result["accepted"] == 0
    assert result["rejected"] == 1
    assert result["deduplicated"] == 0
    mock_db.add.assert_not_called()

@pytest.mark.asyncio
async def test_sequence_replay_reject(mocker, mock_db, valid_observation):
    mocker.patch.object(VNPEventVerifier, "verify_event_signature", return_value=True)

    mock_node_key = NodeKey(key_id="key_1", node_id="00000000-0000-0000-0000-000000000001", public_key="pub_key", active=True)
    mock_node = Node(id="00000000-0000-0000-0000-000000000001", region_code="us-ashburn")
    # Previous observation already has sequence 2, so the incoming sequence 2 is a replay
    mock_prev_obs = Observation(sequence=2, signature="1234567890abcdef_sig")
    
    class SmartMockResult:
        def __init__(self, val=None):
            self.val = val
        def first(self):
            return self.val
        def scalar_one_or_none(self):
            return self.val

    def side_effect(stmt):
        stmt_str = str(stmt).lower()
        if "from vnp_observations" in stmt_str and "observation_id =" in stmt_str:
            return SmartMockResult(None) # Duplicate check
        if "from vnp_node_keys" in stmt_str:
            return SmartMockResult(mock_node_key)
        if "from vnp_nodes" in stmt_str:
            return SmartMockResult(mock_node)
        if "from vnp_observations" in stmt_str and "order by" in stmt_str:
            return SmartMockResult(mock_prev_obs)
        return SmartMockResult(None)

    mock_db.execute.side_effect = side_effect

    batch = ObservationBatch(observations=[valid_observation])
    result = await ingest_observations_batches(batch=batch, db=mock_db)
    
    assert result["accepted"] == 0
    assert result["rejected"] == 1
    assert result["deduplicated"] == 0
    mock_db.add.assert_not_called()
