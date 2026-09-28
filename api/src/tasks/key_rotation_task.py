"""
Encryption key rotation task.

Re-encrypts all sensitive fields with the primary (first) key in
ENCRYPTION_KEY, discarding the old key from the ciphertext.

Usage:
1. Set ENCRYPTION_KEY=NEW_KEY,OLD_KEY and restart the API/workers.
2. Run: celery -A src.celery_app call src.tasks.key_rotation_task.rotate_encryption_keys
   Or hit POST /api/v1/platform-settings/key-rotation/start (platform admin only).
3. Verify the task completes with no errors (check the returned stats / task result).
4. Set ENCRYPTION_KEY=NEW_KEY and restart.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from src.celery_app import celery_app
from src.core.database import create_celery_async_session

logger = logging.getLogger(__name__)


@celery_app.task(name="rotate_encryption_keys", bind=True, max_retries=0)
def rotate_encryption_keys(self, dry_run: bool = False) -> dict:
    """
    Re-encrypt all encrypted fields with the current primary key.

    Args:
        dry_run: If True, count rows that would be re-encrypted but don't write.

    Returns:
        dict with 'rotated', 'skipped', 'errors', 'dry_run', 'duration_seconds'
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_rotate_async(dry_run=dry_run))
    finally:
        loop.close()


async def _rotate_async(dry_run: bool = False) -> dict:
    """Async implementation: iterate every model/field and re-encrypt with primary key."""
    import os
    import time

    from cryptography.fernet import Fernet

    from src.services.agents.security import _build_fernet

    start = time.monotonic()
    stats: dict = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": dry_run}

    enc_key_str = os.environ.get("ENCRYPTION_KEY", "")
    if not enc_key_str:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")

    # MultiFernet: decrypts with any key in the list, encrypts with the first.
    multi_fernet = _build_fernet(enc_key_str)
    primary_key_bytes = enc_key_str.split(",")[0].strip().encode()
    primary_fernet = Fernet(primary_key_bytes)

    encrypted_fields = _get_encrypted_fields()

    factory = create_celery_async_session()
    async with factory() as db:
        for model_class, field_name, field_type in encrypted_fields:
            try:
                await _rotate_model_field(
                    db,
                    model_class,
                    field_name,
                    field_type,
                    multi_fernet,
                    primary_fernet,
                    stats,
                    dry_run,
                )
            except Exception as exc:
                logger.error(
                    "Key rotation failed for %s.%s: %s",
                    model_class.__name__,
                    field_name,
                    exc,
                    exc_info=True,
                )
                stats["errors"] += 1

        if not dry_run:
            await db.commit()

    stats["duration_seconds"] = round(time.monotonic() - start, 2)
    logger.info("Key rotation complete: %s", stats)
    return stats


def _get_encrypted_fields() -> list[tuple]:
    """
    Return all (ModelClass, field_name, field_type) tuples for encrypted fields.

    field_type is one of:
      "plain"    — the column value IS the raw Fernet token (decrypt / re-encrypt directly)
      "enc:"     — the column value is prefixed with "enc:" (strip prefix, decrypt, re-encrypt, restore prefix)

    Fields stored via Python property setters (MCPServer, UserOAuthToken, etc.) are handled
    by reading the backing column directly and writing back via the same backing column — no
    need to go through the property because the property would double-encrypt on set.
    """
    from src.models.agent_compute import AgentCompute
    from src.models.agent_llm_config import AgentLLMConfig
    from src.models.agent_widget import AgentWidget
    from src.models.database_connection import DatabaseConnection
    from src.models.data_source import DataSource
    from src.models.load_test import LoadTest
    from src.models.mcp_server import MCPServer
    from src.models.monitoring_integration import MonitoringIntegration
    from src.models.oauth_app import OAuthApp
    from src.models.okta_tenant import OktaTenant
    from src.models.phone_provider_credential import PhoneProviderCredential
    from src.models.platform_settings import PlatformSettings
    from src.models.slack_bot import SlackBot
    from src.models.social_auth_provider import SocialAuthProvider
    from src.models.telegram_bot import TelegramBot
    from src.models.user_oauth_token import UserOAuthToken
    from src.models.voice_api_key import VoiceApiKey
    from src.models.whatsapp_bot import WhatsAppBot

    return [
        # AgentLLMConfig.api_key — plain Fernet token
        (AgentLLMConfig, "api_key", "plain"),
        # AgentWidget.api_key — plain Fernet token (encrypted widget secret key)
        (AgentWidget, "api_key", "plain"),
        # AgentCompute.remote_credentials_encrypted — plain Fernet token
        (AgentCompute, "remote_credentials_encrypted", "plain"),
        # DatabaseConnection.password_encrypted — plain Fernet token
        (DatabaseConnection, "password_encrypted", "plain"),
        # DataSource.access_token_encrypted / refresh_token_encrypted — plain Fernet tokens
        (DataSource, "access_token_encrypted", "plain"),
        (DataSource, "refresh_token_encrypted", "plain"),
        # LoadTest.auth_config_encrypted — plain Fernet token
        (LoadTest, "auth_config_encrypted", "plain"),
        # MCPServer backing columns store "enc:<token>" — use enc: field_type
        (MCPServer, "_auth_config_enc", "enc:"),
        (MCPServer, "_env_vars_enc", "enc:"),
        (MCPServer, "_headers_enc", "enc:"),
        # MonitoringIntegration.config_data_encrypted — plain Fernet token
        (MonitoringIntegration, "config_data_encrypted", "plain"),
        # OAuthApp — client_secret and api_token are plain Fernet tokens
        (OAuthApp, "client_secret", "plain"),
        (OAuthApp, "api_token", "plain"),
        # OktaTenant.client_secret — plain Fernet token
        (OktaTenant, "client_secret", "plain"),
        # PhoneProviderCredential.credentials_encrypted — plain Fernet token
        (PhoneProviderCredential, "credentials_encrypted", "plain"),
        # PlatformSettings — Stripe secrets are plain Fernet tokens
        (PlatformSettings, "stripe_secret_key", "plain"),
        (PlatformSettings, "stripe_webhook_secret", "plain"),
        # SlackBot tokens — plain Fernet tokens
        (SlackBot, "slack_bot_token", "plain"),
        (SlackBot, "slack_app_token", "plain"),
        (SlackBot, "signing_secret", "plain"),
        # SocialAuthProvider.client_secret — plain Fernet token
        (SocialAuthProvider, "client_secret", "plain"),
        # TelegramBot — plain Fernet tokens
        (TelegramBot, "bot_token", "plain"),
        (TelegramBot, "webhook_secret", "plain"),
        # UserOAuthToken backing columns (properties would double-encrypt)
        (UserOAuthToken, "_access_token_enc", "plain"),
        (UserOAuthToken, "_refresh_token_enc", "plain"),
        # VoiceApiKey.api_key_encrypted — plain Fernet token
        (VoiceApiKey, "api_key_encrypted", "plain"),
        # WhatsAppBot — access_token and session_data are plain Fernet tokens
        (WhatsAppBot, "access_token", "plain"),
        (WhatsAppBot, "session_data", "plain"),
    ]


async def _rotate_model_field(
    db,
    model_class,
    field_name: str,
    field_type: str,
    multi_fernet,
    primary_fernet,
    stats: dict,
    dry_run: bool,
) -> None:
    """
    Re-encrypt a single (model, field) pair in bulk.

    Loads all rows, decrypts each value with multi_fernet (tries all keys),
    re-encrypts with primary_fernet only, and updates the row if the ciphertext changed.
    Skips NULL/empty values.
    """
    stmt = select(model_class)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    logger.debug(
        "Rotating %s.%s — %d rows to inspect",
        model_class.__name__,
        field_name,
        len(rows),
    )

    for row in rows:
        raw_value = getattr(row, field_name, None)

        # --- Determine the ciphertext to decrypt ---
        if field_type == "enc:":
            # Value is "enc:<fernet_token>" or None/plain-JSON (legacy unencrypted)
            if not raw_value or not raw_value.startswith("enc:"):
                stats["skipped"] += 1
                continue
            ciphertext = raw_value[4:]  # strip "enc:" prefix
        else:
            # "plain": the column holds the Fernet token directly
            if not raw_value:
                stats["skipped"] += 1
                continue
            ciphertext = raw_value

        # --- Decrypt with MultiFernet (handles any key in the rotation set) ---
        try:
            plaintext_bytes = multi_fernet.decrypt(ciphertext.encode())
        except Exception as exc:
            logger.warning(
                "Could not decrypt %s.%s (id=%s): %s — skipping",
                model_class.__name__,
                field_name,
                getattr(row, "id", "?"),
                exc,
            )
            stats["errors"] += 1
            continue

        # --- Re-encrypt with primary key only ---
        new_ciphertext = primary_fernet.encrypt(plaintext_bytes).decode()

        if field_type == "enc:":
            new_value = f"enc:{new_ciphertext}"
        else:
            new_value = new_ciphertext

        if new_value == raw_value:
            # Already encrypted with primary key — nothing to do
            stats["skipped"] += 1
            continue

        if not dry_run:
            setattr(row, field_name, new_value)
            db.add(row)

        stats["rotated"] += 1
