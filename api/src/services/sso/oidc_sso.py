"""Generic OIDC SSO service — supports any OIDC-compliant IdP."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.services.security.public_http import request_checked_url

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class OIDCSSOService:
    """
    Generic OpenID Connect SSO handler.

    Supports:
    - Auto-discovery via /.well-known/openid-configuration
    - Manual endpoint configuration (fallback when discovery_url is absent)
    - JIT account provisioning
    - State parameter for CSRF protection
    """

    def __init__(self, config) -> None:
        """config: OIDCConfig model instance."""
        self.config = config
        self._discovered: dict | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def _discover(self) -> dict:
        """Fetch OIDC discovery document (cached per instance)."""
        if self._discovered is not None:
            return self._discovered

        if not self.config.discovery_url:
            # Build from manual config fields
            self._discovered = {
                "authorization_endpoint": self.config.authorization_endpoint,
                "token_endpoint": self.config.token_endpoint,
                "userinfo_endpoint": self.config.userinfo_endpoint,
                "jwks_uri": self.config.jwks_uri,
            }
            return self._discovered

        response = await request_checked_url(
            "GET",
            self.config.discovery_url,
            timeout=10.0,
            max_bytes=512 * 1024,
        )
        response.raise_for_status()
        self._discovered = response.json()
        return self._discovered

    # ------------------------------------------------------------------
    # Authorization URL
    # ------------------------------------------------------------------

    async def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Build the IdP authorization URL for the browser redirect."""
        from urllib.parse import urlencode

        discovery = await self._discover()
        auth_endpoint = discovery["authorization_endpoint"]
        if not auth_endpoint:
            raise ValueError("No authorization_endpoint configured for this OIDC provider")

        scopes = self.config.scopes or "openid email profile"
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # Token exchange
    # ------------------------------------------------------------------

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens."""
        from src.services.agents.security import decrypt_value

        discovery = await self._discover()
        token_endpoint = discovery["token_endpoint"]
        if not token_endpoint:
            raise ValueError("No token_endpoint configured for this OIDC provider")

        client_secret = decrypt_value(self.config.client_secret)
        response = await request_checked_url(
            "POST",
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.config.client_id,
                "client_secret": client_secret,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # UserInfo
    # ------------------------------------------------------------------

    async def get_user_info(self, access_token: str) -> dict:
        """Fetch user info from the IdP userinfo endpoint."""
        discovery = await self._discover()
        userinfo_endpoint = discovery["userinfo_endpoint"]
        if not userinfo_endpoint:
            raise ValueError("No userinfo_endpoint configured for this OIDC provider")

        response = await request_checked_url(
            "GET",
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Claim extraction
    # ------------------------------------------------------------------

    def extract_user_attributes(self, userinfo: dict) -> dict:
        """
        Extract email and display name from userinfo claims.

        Falls back gracefully through common alternative claim names when the
        configured claim is absent.
        """
        email = userinfo.get(self.config.email_claim) or userinfo.get("email")
        name = (
            userinfo.get(self.config.name_claim)
            or userinfo.get("name")
            or userinfo.get("given_name", "")
        )
        if not email:
            raise ValueError(
                f"No email found in OIDC userinfo (tried claim '{self.config.email_claim}' then 'email')"
            )
        return {"email": email.lower().strip(), "name": name}

    # ------------------------------------------------------------------
    # JIT provisioning
    # ------------------------------------------------------------------

    async def provision_or_get_account(
        self,
        db: "AsyncSession",
        tenant_id,
        email: str,
        name: str,
    ):
        """
        Return an existing Account for the given email, or create one via JIT.

        Follows the same pattern as SAMLService.get_or_create_account.

        Raises:
            ValueError: If account doesn't exist and auto_provision is disabled.
        """
        from sqlalchemy import select

        from src.models.tenant import Account, AccountRole, AccountStatus, TenantAccountJoin

        # Look up existing account by email
        result = await db.execute(select(Account).where(Account.email == email.lower()))
        account = result.scalar_one_or_none()

        if account is None:
            if not self.config.auto_provision:
                raise ValueError(
                    f"Account {email!r} not found and auto-provisioning is disabled for this tenant"
                )
            account = Account(
                email=email.lower(),
                name=name,
                password_hash="",  # No password for OIDC-only accounts
                status=AccountStatus.ACTIVE,
            )
            db.add(account)
            await db.flush()
            logger.info("OIDC JIT: created account %s for tenant %s", account.id, tenant_id)

        # Ensure membership in the target tenant
        result = await db.execute(
            select(TenantAccountJoin).where(
                TenantAccountJoin.account_id == account.id,
                TenantAccountJoin.tenant_id == tenant_id,
            )
        )
        membership = result.scalar_one_or_none()

        if membership is None:
            if not self.config.auto_provision:
                raise ValueError(
                    f"Account {email!r} is not a member of this tenant and auto-provisioning is disabled"
                )
            membership = TenantAccountJoin(
                tenant_id=tenant_id,
                account_id=account.id,
                role=AccountRole.NORMAL,
            )
            db.add(membership)
            logger.info("OIDC JIT: added account %s to tenant %s as NORMAL", account.id, tenant_id)

        await db.flush()
        return account
