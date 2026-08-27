"""Regression coverage for a production incident: OAuthApp.token_expires_at is a plain
(non-timezone-aware) DateTime column, but the GitLab/Jira/Zoom/Google Calendar/Google
Drive token-refresh code in credential_resolver.py was writing timezone-aware
datetime.now(UTC) values into it. asyncpg rejects that at commit time with
"can't subtract offset-naive and offset-aware datetimes" — a mocked unit test can't
reproduce this since it never touches a real DB column, so this hits Postgres for real.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import DBAPIError

from src.models.oauth_app import OAuthApp


class TestOAuthAppTokenExpiresAtColumnType:
    @pytest.mark.asyncio
    async def test_naive_datetime_persists_successfully(self, async_db_session, tenant):
        app = OAuthApp(
            tenant_id=tenant.id,
            provider="gitlab",
            app_name="test-gitlab-app-naive",
            auth_method="oauth",
            is_active=True,
        )
        app.token_expires_at = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None)
        async_db_session.add(app)
        await async_db_session.commit()  # must not raise

    @pytest.mark.asyncio
    async def test_timezone_aware_datetime_fails_to_persist(self, async_db_session, tenant):
        """Documents the exact failure mode this regression test guards against."""
        app = OAuthApp(
            tenant_id=tenant.id,
            provider="gitlab",
            app_name="test-gitlab-app-aware",
            auth_method="oauth",
            is_active=True,
        )
        app.token_expires_at = datetime.now(UTC) + timedelta(hours=2)  # tz-aware — must fail
        async_db_session.add(app)
        with pytest.raises(DBAPIError, match="offset-naive and offset-aware"):
            await async_db_session.commit()
        await async_db_session.rollback()
