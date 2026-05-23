"""
Phone configuration service.

Handles reading/writing agent.phone_config, saving/retrieving encrypted
provider credentials, and registering webhooks with Vapi.
"""

import json
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.phone_number import PhoneNumber
from src.models.phone_provider_credential import PhoneProviderCredential
from src.services.agents.security import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


class PhoneConfigService:
    """Manages phone-call configuration for agents."""

    # ------------------------------------------------------------------
    # Agent phone_config
    # ------------------------------------------------------------------

    @staticmethod
    async def get_phone_config(agent_id: UUID, tenant_id: UUID, db: AsyncSession) -> dict | None:
        """Return agent.phone_config or None if not set."""
        result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            return None
        return agent.phone_config

    @staticmethod
    async def save_phone_config(agent_id: UUID, tenant_id: UUID, config: dict, db: AsyncSession) -> None:
        """Persist phone_config on the agent row."""
        result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        agent.phone_config = config
        await db.commit()

    # ------------------------------------------------------------------
    # Provider credentials
    # ------------------------------------------------------------------

    @staticmethod
    async def save_vapi_credential(tenant_id: UUID, api_key: str, db: AsyncSession) -> None:
        """Upsert the Vapi API key (encrypted) for a tenant."""
        result = await db.execute(
            select(PhoneProviderCredential).where(
                PhoneProviderCredential.tenant_id == tenant_id,
                PhoneProviderCredential.provider == "vapi",
            )
        )
        cred = result.scalar_one_or_none()
        encrypted = encrypt_value(json.dumps({"api_key": api_key}))
        if cred:
            cred.credentials_encrypted = encrypted
            cred.is_active = True
        else:
            cred = PhoneProviderCredential(
                tenant_id=tenant_id,
                provider="vapi",
                credentials_encrypted=encrypted,
                is_active=True,
            )
            db.add(cred)
        await db.commit()

    @staticmethod
    async def get_vapi_api_key(tenant_id: UUID, db: AsyncSession) -> str | None:
        """Return the decrypted Vapi API key for a tenant, or None."""
        result = await db.execute(
            select(PhoneProviderCredential).where(
                PhoneProviderCredential.tenant_id == tenant_id,
                PhoneProviderCredential.provider == "vapi",
                PhoneProviderCredential.is_active.is_(True),
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return None
        try:
            data = json.loads(decrypt_value(cred.credentials_encrypted))
            return data.get("api_key")
        except Exception:
            logger.exception("Failed to decrypt Vapi credential")
            return None

    @staticmethod
    async def has_credential(tenant_id: UUID, provider: str, db: AsyncSession) -> bool:
        """Return True if an active credential exists for the provider."""
        result = await db.execute(
            select(PhoneProviderCredential.id).where(
                PhoneProviderCredential.tenant_id == tenant_id,
                PhoneProviderCredential.provider == provider,
                PhoneProviderCredential.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Phone numbers
    # ------------------------------------------------------------------

    @staticmethod
    async def list_phone_numbers(tenant_id: UUID, db: AsyncSession) -> list[PhoneNumber]:
        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.tenant_id == tenant_id,
                PhoneNumber.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def add_phone_number(
        tenant_id: UUID,
        agent_id: UUID,
        phone_number: str,
        provider: str,
        db: AsyncSession,
    ) -> PhoneNumber:
        """Register a BYOP phone number for an agent."""
        pn = PhoneNumber(
            tenant_id=tenant_id,
            agent_id=agent_id,
            provider=provider,
            phone_number=phone_number,
            is_provisioned=False,
            is_active=True,
        )
        db.add(pn)
        await db.commit()
        await db.refresh(pn)
        return pn

    @staticmethod
    async def remove_phone_number(number_id: UUID, tenant_id: UUID, db: AsyncSession) -> bool:
        """Soft-delete a phone number by setting is_active=False."""
        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == number_id,
                PhoneNumber.tenant_id == tenant_id,
            )
        )
        pn = result.scalar_one_or_none()
        if not pn:
            return False
        pn.is_active = False
        await db.commit()
        return True

    # ------------------------------------------------------------------
    # Vapi webhook registration
    # ------------------------------------------------------------------

    @staticmethod
    async def register_webhook_with_vapi(
        agent_slug: str,
        api_key: str,
        base_url: str,
    ) -> str | None:
        """
        Create (or update) a Vapi assistant configured with our webhook URL.

        Returns the Vapi assistant ID, or None on failure.
        """
        webhook_url = f"{base_url}/api/v1/phone/webhook/vapi"
        payload = {
            "name": f"synkora-{agent_slug}",
            "model": {
                "provider": "custom-llm",
                "url": webhook_url,
                "urlRequestMetadataEnabled": True,
            },
            "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "en"},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.vapi.ai/assistant",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    assistant_id = data.get("id")
                    logger.info(f"Registered Vapi assistant {assistant_id} for agent {agent_slug}")
                    return assistant_id
                else:
                    logger.warning(f"Vapi assistant registration failed: {resp.status_code} {resp.text}")
                    return None
        except Exception:
            logger.exception(f"Error registering Vapi webhook for agent {agent_slug}")
            return None
