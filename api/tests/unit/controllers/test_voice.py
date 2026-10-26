"""Tests for voice controller."""

import uuid
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.voice import voice_router as router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    yield TestClient(app), tenant_id, mock_db_session


class TestTranscribeAudio:
    """Tests for audio transcription endpoint."""

    def test_transcribe_audio_success(self, client):
        """Test successful audio transcription."""
        test_client, tenant_id, mock_db = client

        # MP3 magic bytes (ID3 header or MPEG frame sync)
        mp3_magic = b"\xff\xfb\x90\x00" + b"\x00" * 100  # MPEG Audio frame sync

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.transcribe = AsyncMock(return_value={"text": "Hello world", "language": "en", "duration": 2.5})

            response = test_client.post(
                "/transcribe",
                files={"file": ("test.mp3", BytesIO(mp3_magic), "audio/mpeg")},
                data={"provider": "openai_whisper"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["text"] == "Hello world"

    def test_transcribe_audio_with_language(self, client):
        """Test transcription with language specified."""
        test_client, tenant_id, mock_db = client

        # MP3 magic bytes
        mp3_magic = b"\xff\xfb\x90\x00" + b"\x00" * 100

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.transcribe = AsyncMock(return_value={"text": "Bonjour", "language": "fr"})

            response = test_client.post(
                "/transcribe",
                files={"file": ("test.mp3", BytesIO(mp3_magic), "audio/mpeg")},
                data={"provider": "openai_whisper", "language": "fr"},
            )

        assert response.status_code == status.HTTP_200_OK

    def test_transcribe_audio_empty_file(self, client):
        """Test transcription with empty file."""
        test_client, tenant_id, mock_db = client

        response = test_client.post("/transcribe", files={"file": ("test.mp3", BytesIO(b""), "audio/mpeg")})

        # Empty file should return 400 Bad Request
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_transcribe_audio_invalid_agent_id(self, client):
        """Test transcription with invalid agent ID."""
        test_client, tenant_id, mock_db = client

        audio_content = b"fake audio content"

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.transcribe = AsyncMock(side_effect=ValueError("Invalid agent ID"))

            response = test_client.post(
                "/transcribe",
                files={"file": ("test.mp3", BytesIO(audio_content), "audio/mpeg")},
                data={"agent_id": "invalid-uuid"},
            )

        # The response depends on how the controller handles the error
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestSynthesizeSpeech:
    """Tests for text-to-speech synthesis endpoint."""

    def test_synthesize_speech_success(self, client):
        """Test successful speech synthesis."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.synthesize = AsyncMock(return_value=b"audio data")

            response = test_client.post("/synthesize", json={"text": "Hello world", "provider": "openai_tts"})

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "audio/mpeg"

    def test_synthesize_speech_with_voice(self, client):
        """Test synthesis with specific voice."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.synthesize = AsyncMock(return_value=b"audio data")

            response = test_client.post(
                "/synthesize", json={"text": "Hello world", "provider": "openai_tts", "voice_id": "alloy"}
            )

        assert response.status_code == status.HTTP_200_OK

    def test_synthesize_speech_passes_speed(self, client):
        """Speaking rate is forwarded to the provider only when supplied."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.synthesize = AsyncMock(return_value=b"audio data")

            response = test_client.post("/synthesize", json={"text": "Hi", "provider": "openai_tts", "speed": 1.2})
            assert response.status_code == status.HTTP_200_OK
            assert mock_service.synthesize.call_args.kwargs["speed"] == 1.2

            test_client.post("/synthesize", json={"text": "Hi", "provider": "openai_tts"})
            assert "speed" not in mock_service.synthesize.call_args.kwargs

    def test_synthesize_speech_rejects_out_of_range_speed(self, client):
        test_client, tenant_id, mock_db = client

        response = test_client.post("/synthesize", json={"text": "Hi", "provider": "openai_tts", "speed": 9})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_synthesize_speech_invalid_agent_id(self, client):
        """Test synthesis with invalid agent ID."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.synthesize = AsyncMock(side_effect=ValueError("Invalid agent ID"))

            response = test_client.post(
                "/synthesize", json={"text": "Hello", "provider": "openai_tts", "agent_id": "invalid-uuid"}
            )

        # The response depends on how the controller handles the error
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestListVoices:
    """Tests for listing available voices."""

    def test_list_voices_success(self, client):
        """Test listing voices."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.get_voices = AsyncMock(
                return_value=[{"id": "alloy", "name": "Alloy"}, {"id": "nova", "name": "Nova"}]
            )

            response = test_client.get("/voices?provider=openai_tts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["voices"]) == 2

    def test_list_voices_with_language(self, client):
        """Test listing voices with language filter."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.get_voices = AsyncMock(return_value=[])

            response = test_client.get("/voices?provider=elevenlabs&language=en")

        assert response.status_code == status.HTTP_200_OK


class TestListProviders:
    """Tests for listing voice providers."""

    def test_list_providers_success(self, client):
        """Test listing providers."""
        test_client, tenant_id, mock_db = client

        with patch("src.controllers.voice.VoiceService") as MockVoiceService:
            mock_service = MockVoiceService.return_value
            mock_service.get_supported_providers = AsyncMock(
                return_value={"stt": ["openai_whisper"], "tts": ["openai_tts", "elevenlabs"]}
            )

            response = test_client.get("/providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "stt" in data["data"]
        assert "tts" in data["data"]


class TestSaveApiKey:
    """Tests for saving API keys."""

    def test_save_api_key_unknown_provider(self, client):
        """Test saving API key with unknown provider returns 400."""
        test_client, tenant_id, mock_db = client

        response = test_client.post("/api-keys", json={"provider": "unknown_provider", "api_key": "test-key"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Unknown provider" in data["detail"]

    def test_save_api_key_update_existing(self, client):
        """Test updating existing API key."""
        test_client, tenant_id, mock_db = client

        existing_key = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_key
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        with (
            patch("src.controllers.voice.encrypt_value") as mock_encrypt,
            patch("src.controllers.voice.select") as mock_select,
        ):
            mock_encrypt.return_value = "new_encrypted_key"
            mock_select.return_value.where.return_value = MagicMock()

            response = test_client.post("/api-keys", json={"provider": "openai_tts", "api_key": "sk-new-key"})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "updated" in data["message"]


class TestListApiKeys:
    """Tests for listing API keys."""

    def test_list_api_keys_success(self, client):
        """Test listing API keys."""
        test_client, tenant_id, mock_db = client

        mock_key = MagicMock()
        mock_key.id = uuid.uuid4()
        mock_key.provider = MagicMock(value="openai_tts")
        mock_key.name = "Test Key"
        mock_key.is_active = True
        mock_key.created_at = datetime.now(UTC)
        mock_key.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_key]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api-keys")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["api_keys"]) == 1

    def test_list_api_keys_empty(self, client):
        """Test listing API keys when none exist."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api-keys")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]["api_keys"]) == 0


class TestDeleteApiKey:
    """Tests for deleting API keys."""

    def test_delete_api_key_success(self, client):
        """Test deleting an API key."""
        test_client, tenant_id, mock_db = client

        key_id = uuid.uuid4()
        mock_key = MagicMock()
        mock_key.provider = MagicMock(value="openai_tts")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        response = test_client.delete(f"/api-keys/{key_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        mock_db.delete.assert_called_once_with(mock_key)

    def test_delete_api_key_not_found(self, client):
        """Test deleting non-existent API key."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.delete(f"/api-keys/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_api_key_invalid_id(self, client):
        """Test deleting with invalid ID format."""
        test_client, tenant_id, mock_db = client

        response = test_client.delete("/api-keys/invalid-uuid")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetUsageStats:
    """Tests for getting voice usage statistics."""

    def test_get_usage_stats_success(self, client):
        """Test getting usage stats."""
        test_client, tenant_id, mock_db = client

        mock_usage = MagicMock()
        mock_usage.id = uuid.uuid4()
        mock_usage.provider = MagicMock(value="openai_tts")
        mock_usage.operation_type = MagicMock(value="synthesize")
        mock_usage.characters_processed = 100
        mock_usage.duration_seconds = 2.5
        mock_usage.cost = 0.015
        mock_usage.agent_id = None
        mock_usage.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_usage]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/usage")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["usage"]) == 1
        assert "summary" in data["data"]

    def test_get_usage_stats_with_filters(self, client):
        """Test getting usage stats with filters."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        agent_id = uuid.uuid4()
        response = test_client.get(f"/usage?provider=openai_tts&agent_id={agent_id}&limit=50")

        assert response.status_code == status.HTTP_200_OK

    def test_get_usage_stats_invalid_agent_id(self, client):
        """Test getting stats with invalid agent ID."""
        test_client, tenant_id, mock_db = client

        response = test_client.get("/usage?agent_id=invalid-uuid")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
