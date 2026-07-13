"""Capability status must report Insufficient Evidence with zero evidence."""
from fastapi.testclient import TestClient

from app.main import create_app
from app.api.routers.status import APPROVED_STATUS_VOCABULARY
from tests.conftest import requires_database


@requires_database
def test_capabilities_zero_evidence_is_insufficient_evidence():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/v1/status/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "veklom-vnp"
    assert body["demo_mode"] is False

    by_id = {c["capability_id"]: c for c in body["capabilities"]}

    probes = by_id["vnp_physical_probes"]
    if probes["evidence_count"] == 0:
        assert probes["operational_state"] == "Insufficient Evidence"
        assert probes["last_successful_event"] is None
        assert "node_registration" in probes["required_configuration"]

    for capability in body["capabilities"]:
        assert capability["operational_state"] in APPROVED_STATUS_VOCABULARY


@requires_database
def test_topology_reports_no_fictional_nodes():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/beacon/topology")
    assert response.status_code == 200
    topology = response.json()["topology"]
    assert topology["node_registry"] == "Not Yet Wired"
    for region in topology["regions"]:
        assert "stakeUsd" not in region
        assert "cpuMs" not in region
        assert "poolUtilization" not in region


@requires_database
def test_ready_endpoint_reports_database_state():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] in ("connected", "disconnected")
    assert body["ready"] == (body["database"] == "connected")
