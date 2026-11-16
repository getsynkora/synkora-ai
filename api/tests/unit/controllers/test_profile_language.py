"""The interface language on the profile, /auth/me and sign-up."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.console.auth import RegisterRequest
from src.controllers.profiles import ProfileUpdate, router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account


def _profile(account_id, language):
    profile = MagicMock()
    profile.id = account_id
    profile.name = "Test User"
    profile.email = "test@example.com"
    for field in ("phone", "bio", "company", "job_title", "location", "website", "avatar_url"):
        setattr(profile, field, None)
    profile.two_factor_enabled = False
    profile.is_platform_admin = False
    profile.notification_preferences = {}
    profile.interface_language = language
    profile.last_login_at = datetime.now(UTC)
    profile.created_at = datetime.now(UTC)
    profile.updated_at = datetime.now(UTC)
    return profile


@pytest.fixture
def client():
    with patch("src.controllers.profiles.ProfileService") as service_cls:
        service = AsyncMock()
        service_cls.return_value = service
        app = FastAPI()
        app.include_router(router)

        async def mock_db():
            yield AsyncMock()

        account = MagicMock()
        account.id = uuid.uuid4()
        app.dependency_overrides[get_async_db] = mock_db
        app.dependency_overrides[get_current_account] = lambda: account
        yield TestClient(app), account, service


@pytest.mark.unit
@pytest.mark.parametrize(
    ("stored", "shown"), [("de", "de"), ("en-US", "en"), ("de-AT", "de"), ("fr", "en"), (None, "en")]
)
def test_profile_shows_a_supported_language(client, stored, shown):
    test_client, account, service = client
    service.get_profile.return_value = _profile(account.id, stored)

    response = test_client.get("/profile/me")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["interface_language"] == shown


@pytest.mark.unit
def test_profile_update_passes_the_normalized_language(client):
    test_client, account, service = client
    service.update_profile.return_value = _profile(account.id, "de")

    with patch("src.controllers.profiles._forget_cached_me", AsyncMock()) as forget:
        response = test_client.put("/profile/me", json={"interface_language": "DE-AT"})

    assert response.status_code == status.HTTP_200_OK
    assert service.update_profile.await_args.kwargs["interface_language"] == "de"
    assert response.json()["interface_language"] == "de"
    forget.assert_awaited_once_with(account.id)


@pytest.mark.unit
def test_profile_update_without_a_language_keeps_the_cached_me(client):
    test_client, account, service = client
    service.update_profile.return_value = _profile(account.id, "en")

    with patch("src.controllers.profiles._forget_cached_me", AsyncMock()) as forget:
        response = test_client.put("/profile/me", json={"name": "New Name"})

    assert response.status_code == status.HTTP_200_OK
    forget.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize("value", ["fr", "german", "de; drop", "x" * 30, ""])
def test_profile_update_rejects_an_unsupported_language(client, value):
    test_client, _account, service = client

    response = test_client.put("/profile/me", json={"interface_language": value})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    service.update_profile.assert_not_awaited()


@pytest.mark.unit
def test_profile_update_model_lists_the_languages_in_its_error():
    with pytest.raises(ValueError, match="en, de"):
        ProfileUpdate(interface_language="fr")


@pytest.mark.unit
def test_register_request_accepts_an_optional_language():
    base = {"email": "a@example.com", "password": "Str0ng!Passw0rd#", "name": "A"}

    assert RegisterRequest(**base).interface_language is None
    assert RegisterRequest(**base, interface_language="de").interface_language == "de"


@pytest.mark.unit
async def test_register_stores_the_supported_language():
    from src.models import Account
    from src.services.auth_service import AuthService

    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    added = []
    db.add = added.append

    await AuthService.register(db, "a@example.com", "Str0ng!Passw0rd#", "A", interface_language="de-AT")

    account = next(obj for obj in added if isinstance(obj, Account))
    assert account.interface_language == "de"


@pytest.mark.unit
@pytest.mark.parametrize("language", [None, "fr", "junk;x"])
async def test_register_falls_back_to_english(language):
    from src.models import Account
    from src.services.auth_service import AuthService

    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    added = []
    db.add = added.append

    await AuthService.register(db, "a@example.com", "Str0ng!Passw0rd#", "A", interface_language=language)

    account = next(obj for obj in added if isinstance(obj, Account))
    assert account.interface_language == "en"


@pytest.mark.unit
@pytest.mark.parametrize(("stored", "shown"), [("de", "de"), ("en-US", "en"), ("fr", "en")])
async def test_auth_me_includes_a_supported_language(stored, shown):
    from src.controllers.console.auth import get_current_user

    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "a@example.com"
    account.name = "A"
    account.status = "active"
    account.interface_language = stored
    account.created_at = datetime.now(UTC)

    with (
        patch("src.config.redis.get_redis_async", return_value=None),
        patch("src.controllers.console.auth.AuthService.get_account_tenants", AsyncMock(return_value=[])),
    ):
        body = await get_current_user(current_account=account, db=AsyncMock())

    assert body["data"]["account"]["interface_language"] == shown
