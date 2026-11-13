"""
OpenAI voice providers for Whisper (STT) and TTS.
"""

import logging
from io import BytesIO
from typing import Any

import httpx

from .base_provider import BaseSTTProvider, BaseTTSProvider

logger = logging.getLogger(__name__)


class OpenAIWhisperProvider(BaseSTTProvider):
    """OpenAI Whisper speech-to-text provider."""

    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str | None = None, config: dict[str, Any] | None = None):
        super().__init__(api_key, config)
        self.model = config.get("model", "whisper-1") if config else "whisper-1"

    async def transcribe(self, audio_data: bytes, language: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Transcribe audio using OpenAI Whisper API.

        Args:
            audio_data: Audio file bytes
            language: Language code (optional, Whisper auto-detects)
            **kwargs: Additional options (prompt, temperature, filename, content_type)

        Returns:
            Dict with transcription results
        """
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # OpenAI picks its decoder from the file name, so label the upload with what it
                # really is (the browser sends webm, the mobile app sends wav).
                filename = kwargs.get("filename") or "audio.webm"
                content_type = kwargs.get("content_type") or "audio/webm"
                files = {"file": (filename, BytesIO(audio_data), content_type)}

                data = {
                    "model": self.model,
                }

                if language:
                    data["language"] = language

                # Add optional parameters
                if "prompt" in kwargs:
                    data["prompt"] = kwargs["prompt"]
                if "temperature" in kwargs:
                    data["temperature"] = kwargs["temperature"]

                headers = {"Authorization": f"Bearer {self.api_key}"}

                response = await client.post(
                    f"{self.BASE_URL}/audio/transcriptions", headers=headers, files=files, data=data
                )

                response.raise_for_status()
                result = response.json()

                # Format response
                return {
                    "text": result.get("text", ""),
                    "language": result.get("language", language or "unknown"),
                    "confidence": 1.0,  # Whisper doesn't provide confidence scores
                    "duration": result.get("duration", 0),
                    "segments": result.get("segments", []),
                }

        except httpx.HTTPStatusError as e:
            logger.warning(f"OpenAI Whisper API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Transcription failed: {e.response.text}")
        except Exception as e:
            logger.warning(f"OpenAI Whisper transcription error: {str(e)}")
            raise

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        return [
            "en",
            "zh",
            "de",
            "es",
            "ru",
            "ko",
            "fr",
            "ja",
            "pt",
            "tr",
            "pl",
            "ca",
            "nl",
            "ar",
            "sv",
            "it",
            "id",
            "hi",
            "fi",
            "vi",
            "he",
            "uk",
            "el",
            "ms",
            "cs",
            "ro",
            "da",
            "hu",
            "ta",
            "no",
            "th",
            "ur",
            "hr",
            "bg",
            "lt",
            "la",
            "mi",
            "ml",
            "cy",
            "sk",
            "te",
            "fa",
            "lv",
            "bn",
            "sr",
            "az",
            "sl",
            "kn",
            "et",
            "mk",
            "br",
            "eu",
            "is",
            "hy",
            "ne",
            "mn",
            "bs",
            "kk",
            "sq",
            "sw",
            "gl",
            "mr",
            "pa",
            "si",
            "km",
            "sn",
            "yo",
            "so",
            "af",
            "oc",
            "ka",
            "be",
            "tg",
            "sd",
            "gu",
            "am",
            "yi",
            "lo",
            "uz",
            "fo",
            "ht",
            "ps",
            "tk",
            "nn",
            "mt",
            "sa",
            "lb",
            "my",
            "bo",
            "tl",
            "mg",
            "as",
            "tt",
            "haw",
            "ln",
            "ha",
            "ba",
            "jw",
            "su",
        ]

    def get_supported_formats(self) -> list[str]:
        """Get list of supported audio formats."""
        return ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI text-to-speech provider."""

    BASE_URL = "https://api.openai.com/v1"

    # Available voices
    VOICES = {
        "alloy": {"name": "Alloy", "gender": "neutral", "description": "Neutral and balanced"},
        "echo": {"name": "Echo", "gender": "male", "description": "Male voice"},
        "fable": {"name": "Fable", "gender": "neutral", "description": "Expressive and dynamic"},
        "onyx": {"name": "Onyx", "gender": "male", "description": "Deep male voice"},
        "nova": {"name": "Nova", "gender": "female", "description": "Female voice"},
        "shimmer": {"name": "Shimmer", "gender": "female", "description": "Soft female voice"},
    }

    def __init__(self, api_key: str | None = None, config: dict[str, Any] | None = None):
        super().__init__(api_key, config)
        self.model = config.get("model", "tts-1") if config else "tts-1"
        self.output_format = config.get("format", "mp3") if config else "mp3"

    async def synthesize(self, text: str, voice_id: str | None = None, language: str | None = None, **kwargs) -> bytes:
        """
        Synthesize text to speech using OpenAI TTS API.

        Args:
            text: Text to convert to speech
            voice_id: Voice identifier (alloy, echo, fable, onyx, nova, shimmer)
            language: Language code (not used by OpenAI TTS, auto-detected)
            **kwargs: Additional options (speed, etc.)

        Returns:
            Audio data as bytes
        """
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        if not voice_id:
            voice_id = "alloy"  # Default voice

        if voice_id not in self.VOICES:
            raise ValueError(f"Invalid voice_id. Must be one of: {list(self.VOICES.keys())}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                data = {"model": self.model, "input": text, "voice": voice_id, "response_format": self.output_format}

                # Add optional speed parameter
                if "speed" in kwargs:
                    speed = float(kwargs["speed"])
                    if 0.25 <= speed <= 4.0:
                        data["speed"] = speed

                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

                response = await client.post(f"{self.BASE_URL}/audio/speech", headers=headers, json=data)

                response.raise_for_status()
                return response.content

        except httpx.HTTPStatusError as e:
            logger.warning(f"OpenAI TTS API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Speech synthesis failed: {e.response.text}")
        except Exception as e:
            logger.warning(f"OpenAI TTS synthesis error: {str(e)}")
            raise

    async def get_voices(self, language: str | None = None) -> list[dict[str, Any]]:
        """
        Get available voices.

        Args:
            language: Not used for OpenAI TTS (all voices support multiple languages)

        Returns:
            List of voice dictionaries
        """
        voices = []
        for voice_id, info in self.VOICES.items():
            voices.append(
                {
                    "id": voice_id,
                    "name": info["name"],
                    "language": "multi",  # OpenAI voices support multiple languages
                    "gender": info["gender"],
                    "description": info["description"],
                }
            )
        return voices

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        # OpenAI TTS supports many languages, auto-detected from text
        return [
            "en",
            "zh",
            "de",
            "es",
            "ru",
            "ko",
            "fr",
            "ja",
            "pt",
            "tr",
            "pl",
            "ca",
            "nl",
            "ar",
            "sv",
            "it",
            "id",
            "hi",
            "fi",
            "vi",
            "he",
            "uk",
            "el",
            "ms",
            "cs",
            "ro",
            "da",
            "hu",
            "ta",
            "no",
            "th",
            "ur",
            "hr",
            "bg",
            "lt",
        ]

    def get_output_format(self) -> str:
        """Get the output audio format."""
        return self.output_format
