"""Authenticated deployment-side node registration.

The orchestrator supplies only public identity and deployment metadata. This
script is intended to run through an authenticated SSH/deployment channel or
inside the VNP application container; it is not mounted as a public API.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db.database import async_session_factory
from app.db.models import Node, NodeKey


async def register(payload: dict) -> None:
    required = {
        "node_id",
        "site_code",
        "public_key",
        "key_id",
        "coolify_application_uuid",
        "image_digest",
        "software_version",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"missing registration fields: {', '.join(missing)}")
    public_key = base64.b64decode(payload["public_key"], validate=True)
    if len(public_key) != 32:
        raise ValueError("public_key must be a base64 Ed25519 public key")
    expected_key_id = f"{payload['node_id']}:{hashlib.sha256(public_key).hexdigest()[:16]}"
    if payload["key_id"] != expected_key_id:
        raise ValueError("key_id does not match public_key")

    async with async_session_factory() as db:
        node = (
            await db.execute(select(Node).where(Node.id == UUID(payload["node_id"])))
        ).scalar_one_or_none()
        if not node:
            raise ValueError("node_id is not in canonical registry")
        if node.site_code != payload["site_code"] or node.region_code != payload["site_code"]:
            raise ValueError("site assignment does not match canonical registry")
        active_keys = (
            await db.execute(
                select(NodeKey).where(NodeKey.node_id == node.id).where(NodeKey.active.is_(True))
            )
        ).scalars().all()
        for key in active_keys:
            if key.key_id != payload["key_id"]:
                key.active = False
                key.revoked_at = datetime.now(timezone.utc)
        current = (
            await db.execute(select(NodeKey).where(NodeKey.key_id == payload["key_id"]))
        ).scalar_one_or_none()
        if current:
            if current.node_id != node.id or current.public_key != payload["public_key"]:
                raise ValueError("key_id is already registered to another identity")
            current.active = True
            current.revoked_at = None
        else:
            db.add(
                NodeKey(
                    node_id=node.id,
                    key_id=payload["key_id"],
                    public_key=payload["public_key"],
                    active=True,
                    created_at=datetime.now(timezone.utc),
                )
            )
        node.key_verified_at = datetime.now(timezone.utc)
        node.coolify_application_uuid = payload["coolify_application_uuid"]
        node.image_digest = payload["image_digest"]
        node.software_version = payload["software_version"]
        node.probe_deployed_at = datetime.now(timezone.utc)
        node.registration_status = "registered"
        node.health_state = "standby"
        await db.commit()
    print(json.dumps({"registered": True, "node_id": payload["node_id"], "key_id": payload["key_id"]}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", help="JSON file containing public registration metadata")
    args = parser.parse_args()
    payload = json.loads(
        open(args.payload, encoding="utf-8").read() if args.payload else sys.stdin.read()
    )
    asyncio.run(register(payload))


if __name__ == "__main__":
    main()
