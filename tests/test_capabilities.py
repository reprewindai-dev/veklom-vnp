"""Capability status must report Insufficient Evidence with zero evidence."""
from fastapi.testclient import TestClient

from app.main import create_app
from app.api.routers.status import APPROVED_STATUS_VOCABULARY, _methodology_capability
from tests.conftest import requires_database


def test_byos_methodology_mapping_preserves_live_statuses():
    signed = _methodology_capability("Signed telemetry", "Live")
    scoring = _methodology_capability("Robust scoring", "Connected")

    assert signed.capability_id == "vnp_signed_telemetry"
    assert signed.implementation_state == "Live"
    assert signed.operational_state == "Connected"
    assert signed.required_configuration == []

    assert scoring.capability_id == "vnp_regional_scoring"
    assert scoring.implementation_state == "Connected"
    assert scoring.operational_state == "Connected"
    assert scoring.required_configuration == []


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

    node_registry = by_id["vnp_node_registry"]
    assert node_registry["operational_state"] in (
        "Connected",
        "Config Incomplete",
        "Not Yet Wired",
    )
    if node_registry["operational_state"] == "Connected":
        assert node_registry["implementation_state"] == "Live"
        assert node_registry["required_configuration"] == []


@requires_database
def test_topology_reports_no_fictional_nodes():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/beacon/topology")
    assert response.status_code == 200
    topology = response.json()["topology"]
    if "node_registry" in topology:
        assert topology["node_registry"] == "Disconnected"
    for region in topology.get("regions", []):
        assert "stakeUsd" not in region
        assert "cpuMs" not in region
        assert "poolUtilization" not in region
    for node in topology.get("nodes", []):
        assert node["status_str"] in ("Connected", "Disconnected", "Config Incomplete", "Partially Implemented")


@requires_database
def test_ready_endpoint_reports_database_state():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] in ("connected", "disconnected")
    assert body["ready"] == (body["database"] == "connected")
