"""
Unit tests for OpenAIWhisperProvider, OpenAITTSProvider, and ElevenLabsProvider.

test_voice_service.py already covers VoiceService (the orchestrator).
This file targets the individual HTTP-level provider implementations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.voice.elevenlabs_provider import ElevenLabsProvider
from src.services.voice.openai_provider import OpenAITTSProvider, OpenAIWhisperProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_httpx_client(json_data=None, content=b"", status_code=200, raise_status=None):
    """Return a mock httpx.AsyncClient context manager."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_data or {}
    mock_response.content = content
    mock_response.status_code = status_code
    if raise_status:
        mock_response.raise_for_status.side_effect = raise_status
    else:
        mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client, mock_response


# ---------------------------------------------------------------------------
# OpenAIWhisperProvider — init
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAIWhisperProviderInit:
    def test_default_model_is_whisper_1(self):
        p = OpenAIWhisperProvider(api_key="k")
        assert p.model == "whisper-1"

    def test_custom_model_from_config(self):
        p = OpenAIWhisperProvider(api_key="k", config={"model": "whisper-2"})
        assert p.model == "whisper-2"

    def test_no_config_still_sets_model(self):
        p = OpenAIWhisperProvider()
        assert p.model == "whisper-1"

    def test_get_supported_languages_includes_english(self):
        assert "en" in OpenAIWhisperProvider().get_supported_languages()

    def test_get_supported_languages_returns_list(self):
        langs = OpenAIWhisperProvider().get_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) > 10

    def test_get_supported_formats(self):
        formats = OpenAIWhisperProvider().get_supported_formats()
        assert "mp3" in formats
        assert "wav" in formats
        assert "webm" in formats


# ---------------------------------------------------------------------------
# OpenAIWhisperProvider — transcribe
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAIWhisperProviderTranscribe:
    async def test_no_api_key_raises(self):
        p = OpenAIWhisperProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.transcribe(b"audio")

    async def test_uploads_with_the_real_filename_and_content_type(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"RIFF....", filename="speech.wav", content_type="audio/wav", prompt="Synkora, Muse")

        call = mock_client.post.call_args
        assert call.kwargs["files"]["file"][0] == "speech.wav"
        assert call.kwargs["files"]["file"][2] == "audio/wav"
        assert call.kwargs["data"]["prompt"] == "Synkora, Muse"

    async def test_defaults_to_webm_for_browser_uploads(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio")

        assert mock_client.post.call_args.kwargs["files"]["file"][0] == "audio.webm"

    async def test_returns_formatted_dict(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "text": "Hello world",
                "language": "en",
                "duration": 2.5,
                "segments": [{"start": 0, "end": 2.5}],
            }
        )
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            result = await p.transcribe(b"audio")

        assert result["text"] == "Hello world"
        assert result["language"] == "en"
        assert result["confidence"] == 1.0
        assert result["duration"] == 2.5
        assert len(result["segments"]) == 1

    async def test_language_included_in_data_when_provided(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "Hola"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio", language="es")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["data"]["language"] == "es"

    async def test_language_omitted_when_not_provided(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio")

        call_kwargs = mock_client.post.call_args
        assert "language" not in call_kwargs.kwargs["data"]

    async def test_prompt_kwarg_forwarded(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio", prompt="technical jargon")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["data"]["prompt"] == "technical jargon"

    async def test_temperature_kwarg_forwarded(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio", temperature=0.2)

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["data"]["temperature"] == 0.2

    async def test_model_sent_in_request_data(self):
        p = OpenAIWhisperProvider(api_key="k", config={"model": "custom-whisper"})
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["data"]["model"] == "custom-whisper"

    async def test_authorization_header_sent(self):
        p = OpenAIWhisperProvider(api_key="sk-abc")
        mock_client, _ = _make_httpx_client(json_data={"text": "hi"})
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.transcribe(b"audio")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-abc"

    async def test_http_status_error_raises_exception(self):
        p = OpenAIWhisperProvider(api_key="k")
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        exc = httpx.HTTPStatusError("401", request=MagicMock(), response=error_response)

        mock_client, _ = _make_httpx_client(raise_status=exc)
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Transcription failed"):
                await p.transcribe(b"audio")

    async def test_missing_fields_default_gracefully(self):
        p = OpenAIWhisperProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={})  # empty response
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            result = await p.transcribe(b"audio", language="en")

        assert result["text"] == ""
        assert result["language"] == "en"
        assert result["segments"] == []


# ---------------------------------------------------------------------------
# OpenAITTSProvider — init
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAITTSProviderInit:
    def test_default_model_is_tts_1(self):
        p = OpenAITTSProvider(api_key="k")
        assert p.model == "tts-1"

    def test_custom_model_from_config(self):
        p = OpenAITTSProvider(api_key="k", config={"model": "tts-1-hd"})
        assert p.model == "tts-1-hd"

    def test_default_output_format_is_mp3(self):
        p = OpenAITTSProvider(api_key="k")
        assert p.output_format == "mp3"

    def test_custom_output_format(self):
        p = OpenAITTSProvider(api_key="k", config={"format": "opus"})
        assert p.output_format == "opus"

    def test_get_output_format_returns_format(self):
        p = OpenAITTSProvider(api_key="k", config={"format": "aac"})
        assert p.get_output_format() == "aac"

    def test_voices_dict_has_six_entries(self):
        assert len(OpenAITTSProvider.VOICES) == 6

    def test_all_voices_have_required_fields(self):
        for _voice_id, info in OpenAITTSProvider.VOICES.items():
            assert "name" in info
            assert "gender" in info
            assert "description" in info


# ---------------------------------------------------------------------------
# OpenAITTSProvider — synthesize
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAITTSProviderSynthesize:
    async def test_no_api_key_raises(self):
        p = OpenAITTSProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.synthesize("hello")

    async def test_invalid_voice_id_raises(self):
        p = OpenAITTSProvider(api_key="k")
        with pytest.raises(ValueError, match="Invalid voice_id"):
            await p.synthesize("hello", voice_id="nonexistent")

    async def test_default_voice_is_alloy(self):
        p = OpenAITTSProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio_bytes")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["voice"] == "alloy"

    async def test_returns_response_content(self):
        p = OpenAITTSProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"pcm_data")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            result = await p.synthesize("hello", voice_id="nova")

        assert result == b"pcm_data"

    async def test_text_sent_in_json_body(self):
        p = OpenAITTSProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"x")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("speak this", voice_id="echo")

        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["input"] == "speak this"

    async def test_speed_included_when_in_valid_range(self):
        p = OpenAITTSProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"x")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", voice_id="alloy", speed=1.5)

        json_body = mock_client.post.call_args.kwargs["json"]
        assert json_body["speed"] == 1.5

    async def test_speed_excluded_when_out_of_range(self):
        p = OpenAITTSProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"x")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", voice_id="alloy", speed=10.0)

        json_body = mock_client.post.call_args.kwargs["json"]
        assert "speed" not in json_body

    async def test_authorization_header_sent(self):
        p = OpenAITTSProvider(api_key="sk-tts")
        mock_client, _ = _make_httpx_client(content=b"x")
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", voice_id="alloy")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-tts"

    async def test_http_status_error_raises_exception(self):
        p = OpenAITTSProvider(api_key="k")
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.text = "Rate limited"
        exc = httpx.HTTPStatusError("429", request=MagicMock(), response=error_response)

        mock_client, _ = _make_httpx_client(raise_status=exc)
        with patch("src.services.voice.openai_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Speech synthesis failed"):
                await p.synthesize("hello", voice_id="alloy")


# ---------------------------------------------------------------------------
# OpenAITTSProvider — get_voices
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAITTSProviderGetVoices:
    async def test_returns_all_six_voices(self):
        p = OpenAITTSProvider(api_key="k")
        voices = await p.get_voices()
        assert len(voices) == 6

    async def test_voice_entry_structure(self):
        p = OpenAITTSProvider(api_key="k")
        voices = await p.get_voices()
        for v in voices:
            assert "id" in v
            assert "name" in v
            assert "language" in v
            assert "gender" in v
            assert "description" in v

    async def test_all_voices_language_is_multi(self):
        p = OpenAITTSProvider(api_key="k")
        voices = await p.get_voices()
        assert all(v["language"] == "multi" for v in voices)

    async def test_voice_ids_match_class_constant(self):
        p = OpenAITTSProvider(api_key="k")
        voices = await p.get_voices()
        ids = {v["id"] for v in voices}
        assert ids == set(OpenAITTSProvider.VOICES.keys())


# ---------------------------------------------------------------------------
# ElevenLabsProvider — init
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderInit:
    def test_default_model_id(self):
        p = ElevenLabsProvider(api_key="k")
        assert p.model_id == "eleven_monolingual_v1"

    def test_custom_model_id_from_config(self):
        p = ElevenLabsProvider(api_key="k", config={"model_id": "eleven_multilingual_v2"})
        assert p.model_id == "eleven_multilingual_v2"

    def test_default_output_format(self):
        p = ElevenLabsProvider(api_key="k")
        assert p.output_format == "mp3_44100_128"

    def test_custom_output_format(self):
        p = ElevenLabsProvider(api_key="k", config={"format": "pcm_16000"})
        assert p.output_format == "pcm_16000"

    def test_get_output_format_extracts_codec(self):
        p = ElevenLabsProvider(api_key="k")
        assert p.get_output_format() == "mp3"

    def test_get_output_format_pcm(self):
        p = ElevenLabsProvider(api_key="k", config={"format": "pcm_16000"})
        assert p.get_output_format() == "pcm"


# ---------------------------------------------------------------------------
# ElevenLabsProvider — synthesize
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderSynthesize:
    async def test_no_api_key_raises(self):
        p = ElevenLabsProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.synthesize("hello")

    async def test_default_voice_id_used_when_none(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        url = mock_client.post.call_args.args[0]
        assert "21m00Tcm4TlvDq8ikWAM" in url

    async def test_custom_voice_id_in_url(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", voice_id="CUSTOMVOICE")

        url = mock_client.post.call_args.args[0]
        assert "CUSTOMVOICE" in url

    async def test_xi_api_key_header_sent(self):
        p = ElevenLabsProvider(api_key="el-key-123")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["xi-api-key"] == "el-key-123"

    async def test_returns_response_content(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"el_audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            result = await p.synthesize("hello")

        assert result == b"el_audio"

    async def test_default_voice_settings(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        body = mock_client.post.call_args.kwargs["json"]
        assert body["voice_settings"]["stability"] == 0.5
        assert body["voice_settings"]["similarity_boost"] == 0.75

    async def test_custom_stability_and_similarity_boost(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", stability=0.8, similarity_boost=0.9)

        body = mock_client.post.call_args.kwargs["json"]
        assert body["voice_settings"]["stability"] == 0.8
        assert body["voice_settings"]["similarity_boost"] == 0.9

    async def test_style_kwarg_included_when_present(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", style=0.6)

        body = mock_client.post.call_args.kwargs["json"]
        assert body["voice_settings"]["style"] == 0.6

    async def test_style_kwarg_absent_when_not_provided(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        body = mock_client.post.call_args.kwargs["json"]
        assert "style" not in body["voice_settings"]

    async def test_use_speaker_boost_included_when_present(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello", use_speaker_boost=True)

        body = mock_client.post.call_args.kwargs["json"]
        assert body["voice_settings"]["use_speaker_boost"] is True

    async def test_output_format_sent_as_query_param(self):
        p = ElevenLabsProvider(api_key="k", config={"format": "pcm_22050"})
        mock_client, _ = _make_httpx_client(content=b"audio")
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            await p.synthesize("hello")

        params = mock_client.post.call_args.kwargs["params"]
        assert params["output_format"] == "pcm_22050"

    async def test_http_status_error_raises_exception(self):
        p = ElevenLabsProvider(api_key="k")
        error_response = MagicMock()
        error_response.status_code = 422
        error_response.text = "Unprocessable"
        exc = httpx.HTTPStatusError("422", request=MagicMock(), response=error_response)

        mock_client, _ = _make_httpx_client(raise_status=exc)
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Speech synthesis failed"):
                await p.synthesize("hello")


# ---------------------------------------------------------------------------
# ElevenLabsProvider — get_voices
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderGetVoices:
    async def test_no_api_key_raises(self):
        p = ElevenLabsProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.get_voices()

    async def test_returns_voice_list(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "voices": [
                    {
                        "voice_id": "v1",
                        "name": "Rachel",
                        "labels": {"language": "en", "gender": "female"},
                        "description": "Calm",
                        "category": "premade",
                        "preview_url": "http://ex.com/preview",
                    }
                ]
            }
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            voices = await p.get_voices()

        assert len(voices) == 1
        v = voices[0]
        assert v["id"] == "v1"
        assert v["name"] == "Rachel"
        assert v["language"] == "en"
        assert v["gender"] == "female"

    async def test_language_filter_includes_matching(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "voices": [
                    {
                        "voice_id": "v1",
                        "name": "A",
                        "labels": {"language": "en"},
                        "description": "",
                        "category": "premade",
                    },
                    {
                        "voice_id": "v2",
                        "name": "B",
                        "labels": {"language": "fr"},
                        "description": "",
                        "category": "premade",
                    },
                ]
            }
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            voices = await p.get_voices(language="en")

        ids = [v["id"] for v in voices]
        assert "v1" in ids
        assert "v2" not in ids

    async def test_language_filter_includes_multi_voices(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "voices": [
                    {
                        "voice_id": "vm",
                        "name": "Multi",
                        "labels": {"language": "multi"},
                        "description": "",
                        "category": "premade",
                    },
                ]
            }
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            voices = await p.get_voices(language="de")

        assert len(voices) == 1

    async def test_no_language_filter_returns_all(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "voices": [
                    {
                        "voice_id": "v1",
                        "name": "A",
                        "labels": {"language": "en"},
                        "description": "",
                        "category": "premade",
                    },
                    {
                        "voice_id": "v2",
                        "name": "B",
                        "labels": {"language": "fr"},
                        "description": "",
                        "category": "premade",
                    },
                ]
            }
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            voices = await p.get_voices()

        assert len(voices) == 2

    async def test_http_status_error_raises_exception(self):
        p = ElevenLabsProvider(api_key="k")
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        exc = httpx.HTTPStatusError("401", request=MagicMock(), response=error_response)

        mock_client, _ = _make_httpx_client(raise_status=exc)
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Failed to fetch voices"):
                await p.get_voices()


# ---------------------------------------------------------------------------
# ElevenLabsProvider — get_models
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderGetModels:
    async def test_no_api_key_raises(self):
        p = ElevenLabsProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.get_models()

    async def test_returns_formatted_model_list(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data=[
                {
                    "model_id": "eleven_monolingual_v1",
                    "name": "Eleven English v1",
                    "description": "TTS model",
                    "languages": ["en"],
                    "can_do_text_to_speech": True,
                    "can_do_voice_conversion": False,
                }
            ]
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            models = await p.get_models()

        assert len(models) == 1
        m = models[0]
        assert m["id"] == "eleven_monolingual_v1"
        assert m["can_do_text_to_speech"] is True
        assert m["can_do_voice_conversion"] is False


# ---------------------------------------------------------------------------
# ElevenLabsProvider — get_user_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderGetUserInfo:
    async def test_no_api_key_raises(self):
        p = ElevenLabsProvider(api_key=None)
        with pytest.raises(ValueError, match="API key"):
            await p.get_user_info()

    async def test_returns_subscription_fields(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(
            json_data={
                "subscription": {
                    "character_count": 1000,
                    "character_limit": 10000,
                    "can_extend_character_limit": True,
                    "tier": "starter",
                    "status": "active",
                }
            }
        )
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            info = await p.get_user_info()

        assert info["character_count"] == 1000
        assert info["character_limit"] == 10000
        assert info["can_extend_character_limit"] is True
        assert info["tier"] == "starter"
        assert info["status"] == "active"

    async def test_missing_subscription_defaults_to_zeros(self):
        p = ElevenLabsProvider(api_key="k")
        mock_client, _ = _make_httpx_client(json_data={})
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            info = await p.get_user_info()

        assert info["character_count"] == 0
        assert info["character_limit"] == 0
        assert info["tier"] == "free"

    async def test_http_status_error_raises_exception(self):
        p = ElevenLabsProvider(api_key="k")
        error_response = MagicMock()
        error_response.status_code = 403
        error_response.text = "Forbidden"
        exc = httpx.HTTPStatusError("403", request=MagicMock(), response=error_response)

        mock_client, _ = _make_httpx_client(raise_status=exc)
        with patch("src.services.voice.elevenlabs_provider.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Failed to fetch user info"):
                await p.get_user_info()


# ---------------------------------------------------------------------------
# ElevenLabsProvider — get_supported_languages
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestElevenLabsProviderSupportedLanguages:
    def test_includes_common_languages(self):
        langs = ElevenLabsProvider().get_supported_languages()
        for lang in ("en", "es", "fr", "de", "ja"):
            assert lang in langs

    def test_returns_list(self):
        assert isinstance(ElevenLabsProvider().get_supported_languages(), list)
