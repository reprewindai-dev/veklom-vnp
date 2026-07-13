import logging
import asyncio
import httpx
import hmac
import hashlib
from datetime import datetime, timezone
import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import ProviderBond, BondState, BondChallenge, ChallengeState, BondResolution
from app.pgl.client import PGLClient, PGLConnectionError
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class SlashingEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.cappo_base_url = getattr(self.settings, "cappo_interlink_url", "http://localhost:8088")
        self.interlink_secret = getattr(self.settings, "vnp_cappo_interlink_secret", "dev-interlink-secret")

    async def evaluate_bond_for_slash(self, bond_id: uuid.UUID) -> None:
        """
        Evaluate if a bond has breached its SLA conditions.
        If breached, autonomously challenge and execute the slash via CAPPO.
        """
        stmt = select(ProviderBond).where(ProviderBond.id == bond_id)
        res = await self.db.execute(stmt)
        bond = res.scalar_one_or_none()
        
        if not bond or bond.state not in [BondState.active, BondState.funded]:
            return

        # For the autonomous engine, we assume the evaluation logic determined a breach.
        # Here we generate the challenge record internally.
        
        now = datetime.now(timezone.utc)
        
        challenge = BondChallenge(
            bond_id=bond.id,
            challenger_id=str(uuid.uuid4()), # System challenger
            state=ChallengeState.pending,
            created_at=now
        )
        self.db.add(challenge)
        await self.db.commit()
        await self.db.refresh(challenge)

        logger.info(f"SlashingEngine: Generated breach challenge {challenge.id} for bond {bond.id}")
        
        # Now execute the slash via CAPPO
        await self.execute_slash(bond, challenge)

    async def execute_slash(self, bond: ProviderBond, challenge: BondChallenge) -> None:
        """
        Calls CAPPO interlink to authorize the slash.
        If authorized, updates bond state and mints PGL receipt.
        """
        logger.info(f"SlashingEngine: Requesting CAPPO authorization for slashing bond {bond.id}")
        
        timestamp = datetime.now(timezone.utc).isoformat()
        mac = hmac.new(
            self.interlink_secret.encode(),
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()

        # Generate PGL receipt for the slash attempt evidence
        try:
            pgl_client = PGLClient()
            evidence_receipt_id = await pgl_client.mint_receipt("slash_attempt_evidence", {
                "bond_id": str(bond.id),
                "challenge_id": str(challenge.id)
            })
        except PGLConnectionError as e:
            logger.error(f"Failed to mint PGL evidence receipt: {e}")
            evidence_receipt_id = "pending_pgl_" + str(uuid.uuid4())[:8]

        execution_identity = {
            "principal": "vnp-slashing-engine",
            "role": "system",
            "permissions": ["execute_slash"]
        }

        headers = {
            "x-vnp-signature": mac,
            "x-vnp-timestamp": timestamp,
            "x-agent-id": "vnp-system",
            "x-request-id": str(uuid.uuid4()),
            "x-execution-identity": json.dumps(execution_identity),
            "x-capability-id": "cap_slash",
            "x-target-url": "internal://vnp/slash",
            "x-payment": "BYPASS",
            "x-pgl-pre-cert": evidence_receipt_id
        }

        payload = {
            "bond_id": str(bond.id),
            "challenge_id": str(challenge.id),
            "pgl_evidence_id": evidence_receipt_id
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.cappo_base_url}/api/internal/interlink/vnp/authorize-slash",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
            if resp.status_code == 200:
                data = resp.json()
                if data.get("authorized") is True:
                    logger.info(f"CAPPO authorized slash for {bond.id}. Updating ledger.")
                    await self._commit_slash(bond, challenge, evidence_receipt_id)
                else:
                    logger.warning(f"CAPPO denied slash for {bond.id}: {data}")
            else:
                logger.error(f"CAPPO slash authorization failed with {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"SlashingEngine failed to contact CAPPO: {e}")

    async def _commit_slash(self, bond: ProviderBond, challenge: BondChallenge, evidence_receipt_id: str):
        bond.state = BondState.slashed
        challenge.state = ChallengeState.upheld
        challenge.resolved_at = datetime.now(timezone.utc)
        
        resolution = BondResolution(
            challenge_id=challenge.id,
            action="slash",
            amount_minor=bond.amount_minor,
            pgl_receipt_id=evidence_receipt_id
        )
        self.db.add(resolution)
        await self.db.commit()
        logger.info(f"SlashingEngine: Bond {bond.id} successfully slashed.")
