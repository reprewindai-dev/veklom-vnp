import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.api.routers.vnp_ingest import (
    CanonicalObservation,
    ObservationBatch,
    ingest_observations_batches,
)
from app.core.security import VNPEventVerifier
from app.db.models import Node, NodeKey, Observation


NODE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SITE_CODE = "us-ashburn"
LOCATION = "Ashburn, Virginia, US"


class Result:
    def __init__(self, value=None):
        self.value = value

    def first(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


def _signed_payload(private_key, key_id, *, sequence=1, previous="bootstrap"):
    now = datetime.now(timezone.utc)
    payload = {
        "schema": "veklom.vnp.observation.v1",
        "observation_id": f"obs-{uuid.uuid4()}",
        "node_id": str(NODE_ID),
        "region": SITE_CODE,
        "site_code": SITE_CODE,
        "physical_location": LOCATION,
        "target_id": "vnp-health",
        "endpoint_url": "https://vnp.veklom.com/health",
        "measurement_profile": "https-health-v1",
        "measurement_version": "1.0.0",
        "started_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "completed_at": now.isoformat().replace("+00:00", "Z"),
        "dns_ms": 1,
        "tcp_ms": 2,
        "tls_ms": 3,
        "write_ms": 1,
        "ttfb_ms": 4,
        "body_ms": 1,
        "total_ms": 8,
        "http_status": 200,
        "http_version": "1.1",
        "tls_version": "TLSv1.3",
        "tls_cipher": "TLS_AES_256_GCM_SHA384",
        "transport_reachable": True,
        "semantic_assertion": True,
        "response_fingerprint": "a" * 64,
        "error_code": None,
        "error_category": None,
        "sequence": sequence,
        "previous_observation_hash": previous,
        "signature_key_id": key_id,
    }
    payload["payload_digest"] = VNPEventVerifier.payload_digest(payload)
    signature = private_key.sign(VNPEventVerifier.canonicalize_payload(payload))
    payload["signature"] = base64.b64encode(signature).decode()
    return CanonicalObservation.model_validate(payload, from_attributes=False)


def _public_key_bytes(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def _db_for(node_key, node, previous=None):
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    results = iter([Result(None), Result(node_key), Result(node), Result(previous)])
    db.execute.side_effect = lambda _: next(results)
    return db


@pytest.mark.asyncio
async def test_valid_signed_observation_ingest():
    private_key = Ed25519PrivateKey.generate()
    public_key = _public_key_bytes(private_key)
    key_id = f"{NODE_ID}:{hashlib.sha256(public_key).hexdigest()[:16]}"
    observation = _signed_payload(private_key, key_id)
    node_key = NodeKey(
        key_id=key_id,
        node_id=NODE_ID,
        public_key=base64.b64encode(public_key).decode(),
        active=True,
    )
    node = Node(
        id=NODE_ID,
        site_code=SITE_CODE,
        region_code=SITE_CODE,
        physical_location=LOCATION,
    )
    db = _db_for(node_key, node)

    result = await ingest_observations_batches(
        batch=ObservationBatch(observations=[observation]), db=db
    )

    assert result == {"accepted": 1, "rejected": 0, "deduplicated": 0}
    assert db.add.call_count == 1
    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_unsigned_observation_is_rejected_and_recorded():
    private_key = Ed25519PrivateKey.generate()
    public_key = _public_key_bytes(private_key)
    key_id = f"{NODE_ID}:{hashlib.sha256(public_key).hexdigest()[:16]}"
    observation = _signed_payload(private_key, key_id)
    observation.signature = "not-a-signature"
    node_key = NodeKey(
        key_id=key_id,
        node_id=NODE_ID,
        public_key=base64.b64encode(public_key).decode(),
        active=True,
    )
    node = Node(id=NODE_ID, site_code=SITE_CODE, region_code=SITE_CODE, physical_location=LOCATION)
    db = _db_for(node_key, node)

    result = await ingest_observations_batches(
        batch=ObservationBatch(observations=[observation]), db=db
    )

    assert result["accepted"] == 0
    assert result["rejected"] == 1
    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_unknown_key_is_rejected():
    private_key = Ed25519PrivateKey.generate()
    observation = _signed_payload(private_key, f"{NODE_ID}:unknown")
    db = _db_for(None, None)

    result = await ingest_observations_batches(
        batch=ObservationBatch(observations=[observation]), db=db
    )

    assert result["accepted"] == 0
    assert result["rejected"] == 1


@pytest.mark.asyncio
async def test_replayed_sequence_is_rejected():
    private_key = Ed25519PrivateKey.generate()
    public_key = _public_key_bytes(private_key)
    key_id = f"{NODE_ID}:{hashlib.sha256(public_key).hexdigest()[:16]}"
    observation = _signed_payload(private_key, key_id, sequence=2)
    previous = Observation(
        observation_id="previous",
        payload_digest="b" * 64,
        sequence=2,
        signature="previous-signature",
    )
    node_key = NodeKey(
        key_id=key_id,
        node_id=NODE_ID,
        public_key=base64.b64encode(public_key).decode(),
        active=True,
    )
    node = Node(id=NODE_ID, site_code=SITE_CODE, region_code=SITE_CODE, physical_location=LOCATION)
    db = _db_for(node_key, node, previous)

    result = await ingest_observations_batches(
        batch=ObservationBatch(observations=[observation]), db=db
    )

    assert result["accepted"] == 0
    assert result["rejected"] == 1
