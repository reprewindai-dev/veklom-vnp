from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import socket
import ssl
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


VERSION = os.getenv("VNP_PROBE_VERSION", "1.0.0")
SITE_CODE = os.environ["SITE_CODE"]
NODE_ID = os.environ["NODE_ID"]
INGEST_BASE = os.getenv("VNP_INGEST_BASE", "https://vnp.veklom.com").rstrip("/")
KEY_DIR = Path(os.getenv("NODE_KEY_DIR", "/var/lib/vnp-node"))
TARGETS_FILE = Path(os.getenv("TARGETS_FILE", "/probe/targets.json"))


def canonicalize(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def payload_digest(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    unsigned.pop("payload_digest", None)
    return hashlib.sha256(canonicalize(unsigned)).hexdigest()


def sign_payload(private_key: Ed25519PrivateKey, payload: dict[str, Any]) -> dict[str, Any]:
    payload["payload_digest"] = payload_digest(payload)
    signature = private_key.sign(canonicalize(payload))
    payload["signature"] = base64.b64encode(signature).decode()
    return payload


def wire_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def load_identity() -> tuple[Ed25519PrivateKey, str]:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(KEY_DIR, 0o700)
    private_path = KEY_DIR / "node_ed25519_private.pem"
    public_path = KEY_DIR / "node_ed25519_public.b64"
    if private_path.exists():
        private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    else:
        private_key = Ed25519PrivateKey.generate()
        private_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        os.chmod(private_path, 0o600)
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_key = base64.b64encode(public_bytes).decode()
    public_path.write_text(public_key + "\n")
    os.chmod(public_path, 0o644)
    key_id = f"{NODE_ID}:{hashlib.sha256(public_bytes).hexdigest()[:16]}"
    return private_key, key_id


def load_state() -> dict[str, Any]:
    state_path = KEY_DIR / "probe-state.json"
    if not state_path.exists():
        return {"heartbeat_sequence": 0, "observations": {}}
    return json.loads(state_path.read_text())


def save_state(state: dict[str, Any]) -> None:
    state_path = KEY_DIR / "probe-state.json"
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True))
    os.chmod(temporary, 0o600)
    temporary.replace(state_path)


async def measure(target: dict[str, Any]) -> dict[str, Any]:
    parsed = urlparse(target["url"])
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    started = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    dns_ms = tcp_ms = tls_ms = write_ms = ttfb_ms = body_ms = None
    http_status = None
    body = b""
    tls_version = tls_cipher = None
    transport_reachable = False
    error_category = None
    error_code = None
    http_version = "1.1"
    semantic_assertion = False
    try:
        dns_start = time.perf_counter()
        await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
        dns_ms = int((time.perf_counter() - dns_start) * 1000)
        connect_start = time.perf_counter()
        context = ssl.create_default_context() if parsed.scheme == "https" else None
        reader, writer = await asyncio.open_connection(
            host, port, ssl=context, server_hostname=host if context else None
        )
        connected_ms = int((time.perf_counter() - connect_start) * 1000)
        tcp_ms = connected_ms
        transport_reachable = True
        if context:
            tls_ms = connected_ms
            cipher = writer.get_extra_info("cipher")
            tls_cipher = cipher[0] if cipher else None
            tls_version = writer.get_extra_info("ssl_object").version()
        request = (
            f"GET {parsed.path or '/'}{'?' + parsed.query if parsed.query else ''} HTTP/1.1\r\n"
            f"Host: {host}\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
        ).encode()
        write_start = time.perf_counter()
        writer.write(request)
        await writer.drain()
        write_ms = int((time.perf_counter() - write_start) * 1000)
        ttfb_start = time.perf_counter()
        status_line = await reader.readline()
        ttfb_ms = int((time.perf_counter() - ttfb_start) * 1000)
        parts = status_line.decode(errors="replace").split()
        http_status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        headers = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            if b":" in line:
                name, value = line.decode(errors="replace").split(":", 1)
                headers[name.lower()] = value.strip()
        body_start = time.perf_counter()
        body = await reader.read()
        body_ms = int((time.perf_counter() - body_start) * 1000)
        writer.close()
        await writer.wait_closed()
        semantic_assertion = (
            http_status == target["expected_status"]
            and "application/json" in headers.get("content-type", "")
            and bool(body)
        )
    except socket.gaierror as exc:
        error_category, error_code = "dns_error", type(exc).__name__
    except ssl.SSLError as exc:
        error_category, error_code = "tls_error", type(exc).__name__
    except (ConnectionError, TimeoutError, OSError) as exc:
        error_category, error_code = "transport_error", type(exc).__name__
    except Exception as exc:
        error_category, error_code = "probe_error", type(exc).__name__
    completed = datetime.now(timezone.utc)
    return {
        "schema": "veklom.vnp.observation.v1",
        "observation_id": str(uuid.uuid4()),
        "node_id": NODE_ID,
        "region": SITE_CODE,
        "site_code": SITE_CODE,
        "physical_location": os.environ["PHYSICAL_LOCATION"],
        "target_id": target["target_id"],
        "endpoint_url": target["url"],
        "measurement_profile": target["profile"],
        "measurement_version": "1.0.0",
        "started_at": wire_timestamp(started),
        "completed_at": wire_timestamp(completed),
        "dns_ms": dns_ms,
        "tcp_ms": tcp_ms,
        "tls_ms": tls_ms,
        "write_ms": write_ms,
        "ttfb_ms": ttfb_ms,
        "body_ms": body_ms,
        "total_ms": int((time.perf_counter() - started_clock) * 1000),
        "http_status": http_status,
        "http_version": http_version,
        "tls_version": tls_version,
        "tls_cipher": tls_cipher,
        "transport_reachable": transport_reachable,
        "semantic_assertion": semantic_assertion,
        "response_fingerprint": hashlib.sha256(body).hexdigest() if body else None,
        "error_code": error_code,
        "error_category": error_category,
        "_target": target,
    }


async def post_json(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(f"{INGEST_BASE}{path}", json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


async def run_once() -> None:
    private_key, key_id = load_identity()
    state = load_state()
    state["heartbeat_sequence"] = int(state.get("heartbeat_sequence", 0)) + 1
    heartbeat = sign_payload(
        private_key,
        {
            "heartbeat_id": str(uuid.uuid4()),
            "node_id": NODE_ID,
            "site_code": SITE_CODE,
            "timestamp": wire_timestamp(datetime.now(timezone.utc)),
            "sequence": state["heartbeat_sequence"],
            "software_version": VERSION,
            "signature_key_id": key_id,
        },
    )
    targets = json.loads(TARGETS_FILE.read_text())
    observations = []
    for target in targets:
        result = await measure(target)
        target_state = state.setdefault("observations", {}).setdefault(target["target_id"], {})
        result["sequence"] = int(target_state.get("sequence", 0)) + 1
        result["previous_observation_hash"] = target_state.get("hash", "bootstrap")
        result.pop("_target", None)
        result["signature_key_id"] = key_id
        result = sign_payload(private_key, result)
        target_state["sequence"] = result["sequence"]
        target_state["hash"] = hashlib.sha256(
            canonicalize(
                {"observation_id": result["observation_id"], "payload_digest": result["payload_digest"]}
            )
        ).hexdigest()
        observations.append(result)
    async with httpx.AsyncClient() as client:
        heartbeat_result = await post_json(client, "/api/v1/ingest/heartbeats", heartbeat)
        observation_result = await post_json(
            client, "/api/v1/ingest/observations/batches", {"observations": observations}
        )
    save_state(state)
    print(json.dumps({"heartbeat": heartbeat_result, "observations": observation_result}))


async def run() -> None:
    interval = max(10, int(os.getenv("PROBE_INTERVAL_SECONDS", "60")))
    while True:
        try:
            await run_once()
        except Exception as exc:
            print(json.dumps({"error": type(exc).__name__}), flush=True)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run())
