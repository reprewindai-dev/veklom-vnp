"""The canonical app mounts only database-backed routers by default."""
import httpx
from fastapi.testclient import TestClient

from app.main import create_app


def _routes(app):
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_demo_routes_not_mounted_by_default():
    app = create_app()
    for path in _routes(app):
        assert not path.startswith("/api/v1/demo"), path


def test_canonical_routes_mounted():
    routes = _routes(create_app())
    assert "/health" in routes
    assert "/ready" in routes
    assert "/v1/status/capabilities" in routes
    assert "/api/v1/ingest/heartbeats" in routes
    assert "/api/v1/beacon/topology" in routes
    assert "/api/v1/x402/config" in routes
    assert "/api/v1/ingest/probe-events" in routes
    assert "/api/v1/nexus/scores" in routes


def test_no_legacy_admin_debug_endpoints():
    routes = _routes(create_app())
    assert "/api/v1/admin/debug/storm" not in routes
    assert "/api/v1/admin/debug/slash" not in routes
    assert "/api/v1/admin/config" not in routes


def test_health_endpoint_reports_demo_mode_off():
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["demo_mode"] is False


def test_x402_config_proxy_reports_byos_config(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            assert url.endswith("/api/v1/x402/config")
            return httpx.Response(
                200,
                json={
                    "enabled": True,
                    "network": "base",
                    "missing_config": [],
                    "environment_mode": "production",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/x402/config")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["network"] == "base"
    assert body["missing_config"] == []
