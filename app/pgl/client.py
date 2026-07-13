import httpx
import logging
import json
import base64
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class PGLConnectionError(Exception):
    """Raised when PGL evidence layer is unreachable."""
    pass

class PGLClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.pgl_service_url
        self.signing_key = self.settings.pgl_signing_key.encode('utf-8')

    def _sign_payload(self, payload: dict) -> str:
        """Strict payload signing representing rotated keys logic."""
        payload_str = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = hmac.new(self.signing_key, payload_str, hashlib.sha256).digest()
        return base64.b64encode(signature).decode('utf-8')

    async def mint_receipt(self, event_type: str, event_data: dict) -> str:
        """Mint a PGL receipt. Throws PGLConnectionError if unreachable."""
        
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": event_data,
            "nonce": str(uuid.uuid4())
        }
        
        signature = self._sign_payload(payload)
        headers = {
            "X-PGL-Signature": signature,
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/receipts",
                    json=payload,
                    headers=headers,
                    timeout=5.0
                )
                response.raise_for_status()
                return response.json().get("receipt_id", str(uuid.uuid4()))
        except httpx.RequestError as e:
            logger.error(f"PGL Connection failed: {str(e)}")
            raise PGLConnectionError(f"Failed to communicate with PGL: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"PGL responded with error: {e.response.status_code}")
            raise PGLConnectionError(f"PGL responded with HTTP {e.response.status_code}")
