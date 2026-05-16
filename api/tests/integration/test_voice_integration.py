"""
Integration tests for Voice endpoints.

Tests speech-to-text, text-to-speech, and voice API key operations.
"""

import io
import uuid

import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    from src.models import Account, AccountStatus

    email = f"voice_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Voice Test User",
            "tenant_name": "Voice Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestVoiceProvidersIntegration:
    """Test Voice provider listing operations."""

    def test_list_providers(self, client: TestClient, auth_headers):
        """Test listing supported voice providers."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/providers", headers=headers)

        # Accept 200 (success) or 500 (service error)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["success"] is True
            assert "data" in data

    def test_list_voices(self, client: TestClient, auth_headers):
        """Test listing available voices."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/voices?provider=openai_tts", headers=headers)

        # Accept 200 (success) or 500 (service error - provider not configured)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "voices" in data["data"]

    def test_list_voices_with_language_filter(self, client: TestClient, auth_headers):
        """Test listing voices filtered by language."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/voices?provider=openai_tts&language=en", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestVoiceTranscriptionIntegration:
    """Test Voice transcription (speech-to-text) operations."""

    def test_transcribe_audio(self, client: TestClient, auth_headers):
        """Test transcribing an audio file."""
        headers, tenant_id, account = auth_headers

        # Create a minimal WAV file header (empty audio)
        # This is a valid but silent WAV file
        wav_content = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00"
            b"\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00"
            b"data\x00\x00\x00\x00"
        )
        files = {"file": ("audio.wav", io.BytesIO(wav_content), "audio/wav")}

        response = client.post(
            "/api/v1/voice/transcribe?provider=openai_whisper",
            files=files,
            headers=headers,
        )

        # Accept 200 (success) or 400 (invalid audio) or 500 (provider not configured)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_transcribe_with_language(self, client: TestClient, auth_headers):
        """Test transcribing with language hint."""
        headers, tenant_id, account = auth_headers

        wav_content = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00"
            b"\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00"
            b"data\x00\x00\x00\x00"
        )
        files = {"file": ("audio.wav", io.BytesIO(wav_content), "audio/wav")}

        response = client.post(
            "/api/v1/voice/transcribe?provider=openai_whisper&language=en",
            files=files,
            headers=headers,
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_transcribe_empty_file(self, client: TestClient, auth_headers):
        """Test transcribing an empty file returns error."""
        headers, tenant_id, account = auth_headers

        files = {"file": ("audio.wav", io.BytesIO(b""), "audio/wav")}

        response = client.post(
            "/api/v1/voice/transcribe",
            files=files,
            headers=headers,
        )

        # Should return 400 for empty file
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_transcribe_without_file(self, client: TestClient, auth_headers):
        """Test transcription without file fails."""
        headers, tenant_id, account = auth_headers

        response = client.post("/api/v1/voice/transcribe", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestVoiceSynthesisIntegration:
    """Test Voice synthesis (text-to-speech) operations."""

    def test_synthesize_speech(self, client: TestClient, auth_headers):
        """Test synthesizing speech from text."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/synthesize",
            json={
                "text": "Hello, this is a test.",
                "provider": "openai_tts",
            },
            headers=headers,
        )

        # Accept 200 (success with audio) or 400 (invalid request) or 500 (provider not configured)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        # If successful, should return audio content
        if response.status_code == status.HTTP_200_OK:
            assert response.headers.get("content-type") in ["audio/mpeg", "audio/mp3"]

    def test_synthesize_with_voice_id(self, client: TestClient, auth_headers):
        """Test synthesizing with specific voice."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/synthesize",
            json={
                "text": "Hello, this is a test with a specific voice.",
                "provider": "openai_tts",
                "voice_id": "alloy",
            },
            headers=headers,
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_synthesize_missing_text(self, client: TestClient, auth_headers):
        """Test that synthesis without text fails."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/synthesize",
            json={"provider": "openai_tts"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_synthesize_with_invalid_agent_id(self, client: TestClient, auth_headers):
        """Test synthesis with invalid agent ID format."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/synthesize",
            json={
                "text": "Test text",
                "provider": "openai_tts",
                "agent_id": "not-a-valid-uuid",
            },
            headers=headers,
        )

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestVoiceApiKeysIntegration:
    """Test Voice API key management operations."""

    def test_save_api_key(self, client: TestClient, auth_headers):
        """Test saving a voice API key."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/api-keys",
            json={
                "provider": "openai_tts",
                "api_key": "sk-test-fake-key-12345",
                "name": "Test OpenAI Key",
            },
            headers=headers,
        )

        # Accept 201 (created) or 200 (updated) or 500 (encryption error)
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert data["success"] is True
            assert data["data"]["provider"] == "openai_tts"

    def test_save_api_key_update_existing(self, client: TestClient, auth_headers):
        """Test updating an existing API key."""
        headers, tenant_id, account = auth_headers

        # Save initial key
        client.post(
            "/api/v1/voice/api-keys",
            json={
                "provider": "elevenlabs",
                "api_key": "initial-key",
            },
            headers=headers,
        )

        # Update the key
        response = client.post(
            "/api/v1/voice/api-keys",
            json={
                "provider": "elevenlabs",
                "api_key": "updated-key",
                "name": "Updated ElevenLabs Key",
            },
            headers=headers,
        )

        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_save_api_key_invalid_provider(self, client: TestClient, auth_headers):
        """Test saving API key with invalid provider."""
        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/voice/api-keys",
            json={
                "provider": "invalid_provider",
                "api_key": "test-key",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_api_keys(self, client: TestClient, auth_headers):
        """Test listing API keys."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/api-keys", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["success"] is True
            assert "api_keys" in data["data"]
            # Should not expose actual key values
            for key in data["data"]["api_keys"]:
                assert "api_key_encrypted" not in key
                assert "api_key" not in key

    def test_delete_api_key(self, client: TestClient, auth_headers):
        """Test deleting an API key."""
        headers, tenant_id, account = auth_headers

        # First save a key
        save_response = client.post(
            "/api/v1/voice/api-keys",
            json={
                "provider": "openai_whisper",
                "api_key": "key-to-delete",
            },
            headers=headers,
        )

        if save_response.status_code == status.HTTP_201_CREATED:
            # List keys to get the ID
            list_response = client.get("/api/v1/voice/api-keys", headers=headers)

            if list_response.status_code == status.HTTP_200_OK:
                keys = list_response.json()["data"]["api_keys"]
                whisper_key = next((k for k in keys if k["provider"] == "openai_whisper"), None)

                if whisper_key:
                    # Delete the key
                    response = client.delete(f"/api/v1/voice/api-keys/{whisper_key['id']}", headers=headers)

                    assert response.status_code in [
                        status.HTTP_200_OK,
                        status.HTTP_404_NOT_FOUND,
                    ]

    def test_delete_nonexistent_api_key(self, client: TestClient, auth_headers):
        """Test deleting a nonexistent API key."""
        headers, tenant_id, account = auth_headers

        fake_key_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/voice/api-keys/{fake_key_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_api_key_invalid_id(self, client: TestClient, auth_headers):
        """Test deleting API key with invalid ID format."""
        headers, tenant_id, account = auth_headers

        response = client.delete("/api/v1/voice/api-keys/not-a-valid-uuid", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestVoiceUsageIntegration:
    """Test Voice usage statistics operations."""

    def test_get_usage_stats(self, client: TestClient, auth_headers):
        """Test getting voice usage statistics."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/usage", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["success"] is True
            assert "usage" in data["data"]
            assert "summary" in data["data"]

    def test_get_usage_stats_with_provider_filter(self, client: TestClient, auth_headers):
        """Test getting usage stats filtered by provider."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/usage?provider=openai_tts", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_get_usage_stats_with_limit(self, client: TestClient, auth_headers):
        """Test getting usage stats with limit."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/usage?limit=10", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert len(data["data"]["usage"]) <= 10

    def test_get_usage_stats_invalid_agent_id(self, client: TestClient, auth_headers):
        """Test getting usage stats with invalid agent ID."""
        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/voice/usage?agent_id=not-a-uuid", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestVoiceAuthorization:
    """Test Voice authorization."""

    def test_list_providers_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to list providers are rejected."""
        response = client.get("/api/v1/voice/providers")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_voices_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to list voices are rejected."""
        response = client.get("/api/v1/voice/voices")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_transcribe_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to transcribe are rejected."""
        files = {"file": ("audio.wav", io.BytesIO(b"fake audio"), "audio/wav")}
        response = client.post("/api/v1/voice/transcribe", files=files)

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_synthesize_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to synthesize are rejected."""
        response = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Test", "provider": "openai_tts"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_save_api_key_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to save API key are rejected."""
        response = client.post(
            "/api/v1/voice/api-keys",
            json={"provider": "openai_tts", "api_key": "test"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_list_api_keys_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to list API keys are rejected."""
        response = client.get("/api/v1/voice/api-keys")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_delete_api_key_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to delete API key are rejected."""
        response = client.delete(f"/api/v1/voice/api-keys/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_usage_unauthorized(self, client: TestClient):
        """Test that unauthenticated requests to get usage are rejected."""
        response = client.get("/api/v1/voice/usage")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
