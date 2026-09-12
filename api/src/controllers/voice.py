"""
Voice API endpoints for speech-to-text and text-to-speech operations.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.voice_api_key import VoiceApiKey, VoiceProvider
from src.models.voice_usage import VoiceUsage
from src.services.agents.security import encrypt_value
from src.services.voice import VoiceService

logger = logging.getLogger(__name__)

# Create router
voice_router = APIRouter()

# SECURITY: File upload validation constants
MAX_AUDIO_FILE_SIZE = 25 * 1024 * 1024  # 25 MB max for audio files
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",  # MP3
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".webm", ".ogg", ".flac", ".m4a", ".mp4"}

# Audio file magic bytes for validation
AUDIO_MAGIC_BYTES = {
    b"\xff\xfb": "audio/mpeg",  # MP3 (ID3v1)
    b"\xff\xfa": "audio/mpeg",  # MP3 (ID3v1)
    b"\xff\xf3": "audio/mpeg",  # MP3 (ID3v1)
    b"\xff\xf2": "audio/mpeg",  # MP3 (ID3v1)
    b"ID3": "audio/mpeg",  # MP3 (ID3v2)
    b"RIFF": "audio/wav",  # WAV
    b"OggS": "audio/ogg",  # Ogg
    b"fLaC": "audio/flac",  # FLAC
    b"\x1aE\xdf\xa3": "audio/webm",  # WebM/Matroska
}


def _validate_audio_file(file: UploadFile, file_content: bytes) -> None:
    """
    Validate audio file for security.

    SECURITY: Validates file size, extension, MIME type, and magic bytes
    to prevent malicious file uploads.

    Args:
        file: Uploaded file object
        file_content: File content bytes

    Raises:
        HTTPException: If file validation fails
    """
    import os

    # Check file size
    if len(file_content) > MAX_AUDIO_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large. Maximum size is {MAX_AUDIO_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Check file extension
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid audio file extension. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
            )

    # Check MIME type
    if file.content_type and file.content_type.lower() not in ALLOWED_AUDIO_MIME_TYPES:
        # Log but don't reject - MIME types can be unreliable
        logger.warning(f"Unexpected audio MIME type: {file.content_type} for file {file.filename}")

    # SECURITY: Validate magic bytes to ensure file is actually audio
    if len(file_content) >= 12:
        is_valid_audio = False

        # Check for known audio magic bytes
        for magic, _ in AUDIO_MAGIC_BYTES.items():
            if file_content.startswith(magic):
                is_valid_audio = True
                break

        # Also check for MP4/M4A container (ftyp atom)
        if not is_valid_audio and file_content[4:8] == b"ftyp":
            is_valid_audio = True

        if not is_valid_audio:
            logger.warning(f"SECURITY: File {file.filename} has invalid magic bytes: {file_content[:12].hex()}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio file format. File content does not match expected audio format.",
            )


# Request/Response Models
class VoiceResponse(BaseModel):
    """Response model for voice operations."""

    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class TranscribeRequest(BaseModel):
    """Request model for audio transcription."""

    provider: str = Field(default="openai_whisper", description="STT provider")
    language: str | None = Field(None, description="Language code (e.g., 'en', 'es')")
    agent_id: str | None = Field(None, description="Agent ID for usage tracking")


class SynthesizeRequest(BaseModel):
    """Request model for text-to-speech synthesis."""

    text: str = Field(..., description="Text to convert to speech")
    provider: str = Field(default="openai_tts", description="TTS provider")
    voice_id: str | None = Field(None, description="Voice identifier")
    language: str | None = Field(None, description="Language code")
    agent_id: str | None = Field(None, description="Agent ID for usage tracking")
    config: dict[str, Any] | None = Field(None, description="Provider-specific configuration")


class SaveApiKeyRequest(BaseModel):
    """Request model for saving voice API key."""

    provider: str = Field(..., description="Provider name (openai_whisper, openai_tts, elevenlabs)")
    api_key: str = Field(..., description="API key to encrypt and store")


# Endpoints


@voice_router.post("/transcribe", response_model=VoiceResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    provider: str = "openai_whisper",
    language: str | None = None,
    agent_id: str | None = None,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Transcribe audio file to text.

    SECURITY: Validates file type, size, and content before processing.

    Args:
        file: Audio file (mp3, wav, webm, etc.)
        provider: STT provider to use
        language: Optional language code
        agent_id: Optional agent ID for tracking
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Transcription result with text and metadata
    """
    try:
        # Read audio file
        audio_data = await file.read()

        if not audio_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file")

        # SECURITY: Validate audio file before processing
        _validate_audio_file(file, audio_data)

        # Initialize voice service
        voice_service = VoiceService(db=db, tenant_id=tenant_id)

        # Convert agent_id to UUID if provided
        agent_uuid = None
        if agent_id:
            try:
                agent_uuid = uuid.UUID(agent_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Transcribe
        result = await voice_service.transcribe(
            audio_data=audio_data, provider=provider, language=language, agent_id=agent_uuid
        )

        return VoiceResponse(success=True, message="Audio transcribed successfully", data=result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcription failed")


@voice_router.post("/synthesize")
async def synthesize_speech(
    request: SynthesizeRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Synthesize text to speech.

    Args:
        request: Synthesis request
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Audio file as binary response
    """
    try:
        # Initialize voice service
        voice_service = VoiceService(db=db, tenant_id=tenant_id)

        # Convert agent_id to UUID if provided
        agent_uuid = None
        if request.agent_id:
            try:
                agent_uuid = uuid.UUID(request.agent_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Synthesize
        audio_data = await voice_service.synthesize(
            text=request.text,
            provider=request.provider,
            voice_id=request.voice_id,
            language=request.language,
            agent_id=agent_uuid,
            config=request.config,
        )

        # Determine content type based on provider
        content_type_map = {
            "openai_tts": "audio/mpeg",  # mp3
            "elevenlabs": "audio/mpeg",  # mp3
        }
        content_type = content_type_map.get(request.provider, "audio/mpeg")

        return Response(
            content=audio_data,
            media_type=content_type,
            headers={"Content-Disposition": "attachment; filename=speech.mp3"},
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Synthesis error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Synthesis failed")


@voice_router.get("/voices", response_model=VoiceResponse)
async def list_voices(
    provider: str = "openai_tts",
    language: str | None = None,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List available voices for a TTS provider.

    Args:
        provider: TTS provider
        language: Optional language filter
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        List of available voices
    """
    try:
        # Initialize voice service
        voice_service = VoiceService(db=db, tenant_id=tenant_id)

        # Get voices
        voices = await voice_service.get_voices(provider=provider, language=language)

        return VoiceResponse(success=True, message=f"Found {len(voices)} voices", data={"voices": voices})

    except Exception as e:
        logger.error(f"Error listing voices: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list voices"
        )


@voice_router.get("/providers", response_model=VoiceResponse)
async def list_providers(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    List all supported voice providers.

    Args:
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        List of STT and TTS providers
    """
    try:
        # Initialize voice service
        voice_service = VoiceService(db=db, tenant_id=tenant_id)

        # Get providers
        providers = await voice_service.get_supported_providers()

        return VoiceResponse(success=True, message="Retrieved supported providers", data=providers)

    except Exception as e:
        logger.error(f"Error listing providers: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list providers")


@voice_router.post("/api-keys", response_model=VoiceResponse, status_code=status.HTTP_201_CREATED)
async def save_api_key(
    request: SaveApiKeyRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Save an encrypted API key for a voice provider.

    Args:
        request: API key save request
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        # Map provider string to enum
        provider_map = {
            "openai_whisper": VoiceProvider.OPENAI_WHISPER,
            "openai_tts": VoiceProvider.OPENAI_TTS,
            "elevenlabs": VoiceProvider.ELEVENLABS,
        }

        provider_enum = provider_map.get(request.provider.lower())
        if not provider_enum:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown provider: {request.provider}")

        # Check if key already exists
        result = await db.execute(
            select(VoiceApiKey).where(VoiceApiKey.tenant_id == tenant_id, VoiceApiKey.provider == provider_enum)
        )
        existing_key = result.scalar_one_or_none()

        if existing_key:
            # Update existing key
            existing_key.api_key_encrypted = encrypt_value(request.api_key)
            existing_key.is_active = True
            message = f"API key for {request.provider} updated successfully"
        else:
            # Create new key
            new_key = VoiceApiKey(
                tenant_id=tenant_id,
                provider=provider_enum,
                api_key_encrypted=encrypt_value(request.api_key),
                is_active=True,
            )
            db.add(new_key)
            message = f"API key for {request.provider} saved successfully"

        await db.commit()

        return VoiceResponse(success=True, message=message, data={"provider": request.provider})

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving API key: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save API key")


@voice_router.get("/api-keys", response_model=VoiceResponse)
async def list_api_keys(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    List all configured API keys (without exposing the actual keys).

    Args:
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        List of API key metadata
    """
    try:
        result = await db.execute(select(VoiceApiKey).where(VoiceApiKey.tenant_id == tenant_id))
        api_keys = result.scalars().all()

        keys_list = []
        for key in api_keys:
            keys_list.append(
                {
                    "id": str(key.id),
                    "provider": key.provider,
                    "is_active": key.is_active,
                    "created_at": key.created_at.isoformat(),
                    "updated_at": key.updated_at.isoformat(),
                }
            )

        return VoiceResponse(success=True, message=f"Found {len(keys_list)} API keys", data={"api_keys": keys_list})

    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list API keys")


@voice_router.delete("/api-keys/{key_id}", response_model=VoiceResponse)
async def delete_api_key(
    key_id: str, tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    Delete an API key.

    Args:
        key_id: UUID of the API key
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        # Convert string to UUID
        try:
            key_uuid = uuid.UUID(key_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key ID format")

        # Find and delete the key
        result = await db.execute(
            select(VoiceApiKey).where(VoiceApiKey.id == key_uuid, VoiceApiKey.tenant_id == tenant_id)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

        provider_name = api_key.provider
        await db.delete(api_key)
        await db.commit()

        return VoiceResponse(success=True, message=f"API key for {provider_name} deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting API key: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete API key")


@voice_router.get("/usage", response_model=VoiceResponse)
async def get_usage_stats(
    provider: str | None = None,
    agent_id: str | None = None,
    limit: int = 100,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get voice usage statistics.

    Args:
        provider: Optional provider filter
        agent_id: Optional agent ID filter
        limit: Maximum number of records
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Usage statistics
    """
    try:
        # Build query
        query = select(VoiceUsage).where(VoiceUsage.tenant_id == tenant_id)

        # Apply filters
        if provider:
            provider_map = {
                "openai_whisper": VoiceProvider.OPENAI_WHISPER,
                "openai_tts": VoiceProvider.OPENAI_TTS,
                "elevenlabs": VoiceProvider.ELEVENLABS,
            }
            provider_enum = provider_map.get(provider.lower())
            if provider_enum:
                query = query.where(VoiceUsage.provider == provider_enum)

        if agent_id:
            try:
                agent_uuid = uuid.UUID(agent_id)
                query = query.where(VoiceUsage.agent_id == agent_uuid)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Order by most recent and limit
        query = query.order_by(VoiceUsage.created_at.desc()).limit(limit)

        result = await db.execute(query)
        usage_records = result.scalars().all()

        # Build response
        usage_list = []
        total_cost = 0.0
        total_characters = 0

        for record in usage_records:
            usage_list.append(
                {
                    "id": str(record.id),
                    "provider": record.provider,
                    "operation_type": record.operation_type.value,
                    "characters_processed": record.characters_processed,
                    "duration_seconds": record.duration_seconds,
                    "cost": record.cost,
                    "agent_id": str(record.agent_id) if record.agent_id else None,
                    "created_at": record.created_at.isoformat(),
                }
            )
            total_cost += record.cost or 0.0
            total_characters += record.characters_processed or 0

        return VoiceResponse(
            success=True,
            message=f"Found {len(usage_list)} usage records",
            data={
                "usage": usage_list,
                "summary": {
                    "total_records": len(usage_list),
                    "total_cost": round(total_cost, 4),
                    "total_characters": total_characters,
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get usage statistics")
