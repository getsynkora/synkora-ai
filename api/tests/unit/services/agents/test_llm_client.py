import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.config import ModelConfig
from src.services.agents.llm_client import MultiProviderLLMClient


# Disable LOAD_TEST_MODE for all tests in this file to prevent provider override to "mock"
@patch.dict(os.environ, {"LOAD_TEST_MODE": ""})
class TestMultiProviderLLMClient:
    @pytest.fixture
    def mock_config(self):
        return ModelConfig(provider="OPENAI", model_name="gpt-4", api_key="test-key", temperature=0.7, max_tokens=100)

    @pytest.fixture
    def mock_langfuse(self):
        with patch("src.services.agents.llm_client.LangfuseService") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.should_trace.return_value = False
            mock_cls.for_agent.return_value = mock_instance
            yield mock_instance

    def test_init_openai(self, mock_config):
        with patch("openai.AsyncOpenAI") as MockClient:
            client = MultiProviderLLMClient(mock_config)
            assert client.provider == "openai"  # Provider is normalized to lowercase
            MockClient.assert_called_once_with(api_key="test-key")

    def test_init_deepseek(self, mock_config):
        mock_config.provider = "deepseek"
        mock_config.model_name = "deepseek-v4-flash"
        mock_config.api_base = None
        with patch("openai.AsyncOpenAI") as MockClient:
            client = MultiProviderLLMClient(mock_config)
            assert client.provider == "deepseek"
            MockClient.assert_called_once_with(api_key="test-key", base_url="https://api.deepseek.com")

    def test_init_anthropic(self, mock_config):
        mock_config.provider = "anthropic"
        with patch("anthropic.AsyncAnthropic") as MockClient:
            client = MultiProviderLLMClient(mock_config)
            assert client.provider == "anthropic"
            MockClient.assert_called_once_with(api_key="test-key")

    def test_init_google(self, mock_config):
        mock_config.provider = "google"
        from google import genai

        with patch.object(genai, "Client") as MockClient:
            client = MultiProviderLLMClient(mock_config)
            assert client.provider == "google"
            MockClient.assert_called_once_with(api_key="test-key")

    def test_init_litellm(self, mock_config):
        mock_config.provider = "LITELLM"
        mock_config.api_base = "http://localhost:11434"
        with patch.dict(sys.modules, {"litellm": MagicMock()}):
            import litellm

            client = MultiProviderLLMClient(mock_config)
            assert client.provider == "litellm"  # Provider is normalized to lowercase
            # api_base is stored on the client config and passed per-call, not set globally
            assert client._client is litellm

    def test_init_unsupported(self, mock_config):
        mock_config.provider = "unknown"
        with pytest.raises(ValueError, match="Unsupported provider"):
            MultiProviderLLMClient(mock_config)

    @pytest.mark.asyncio
    async def test_generate_content_openai(self, mock_config, mock_langfuse):
        client = None
        with patch("openai.AsyncOpenAI") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            client = MultiProviderLLMClient(mock_config)
            response = await client.generate_content("Prompt")

            assert response == "Response"
            mock_instance.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_anthropic(self, mock_config, mock_langfuse):
        mock_config.provider = "anthropic"
        client = None
        with patch("anthropic.AsyncAnthropic") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = MagicMock()
            mock_response.content[0].text = "Response"
            mock_instance.messages.create = AsyncMock(return_value=mock_response)

            client = MultiProviderLLMClient(mock_config)
            response = await client.generate_content("Prompt")

            assert response == "Response"
            mock_instance.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_google(self, mock_config, mock_langfuse):
        mock_config.provider = "google"
        from google import genai

        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_client_instance.models.generate_content.return_value = mock_response

        with patch.object(genai, "Client", return_value=mock_client_instance):
            client = MultiProviderLLMClient(mock_config)
            response = await client.generate_content("Prompt")

            assert response == "Response"
            mock_client_instance.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_litellm(self, mock_config, mock_langfuse):
        mock_config.provider = "LITELLM"
        with patch.dict(sys.modules, {"litellm": MagicMock()}):
            import litellm

            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            litellm.acompletion = AsyncMock(return_value=mock_response)

            client = MultiProviderLLMClient(mock_config)
            response = await client.generate_content("Prompt")

            assert response == "Response"
            litellm.acompletion.assert_called_once()

    @pytest.mark.asyncio
    async def test_tracing(self, mock_config, mock_langfuse):
        mock_langfuse.should_trace.return_value = True
        mock_langfuse.create_generation.return_value = "gen-id"

        with patch("openai.AsyncOpenAI") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

            client = MultiProviderLLMClient(mock_config, observability_config={"enabled": True})
            await client.generate_content("Prompt")

            mock_langfuse.create_generation.assert_called_once()
            mock_langfuse.update_generation.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_error_tracing(self, mock_config, mock_langfuse):
        mock_langfuse.should_trace.return_value = True
        mock_langfuse.create_generation.return_value = "gen-id"

        with patch("openai.AsyncOpenAI") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            client = MultiProviderLLMClient(mock_config, observability_config={"enabled": True})

            with pytest.raises(Exception):
                await client.generate_content("Prompt")

            mock_langfuse.create_generation.assert_called_once()
            # Verify update called with error
            assert mock_langfuse.update_generation.call_args[1]["output_data"]["error"] == "API Error"

    @pytest.mark.asyncio
    async def test_generate_stream_openai(self, mock_config):
        with patch("openai.AsyncOpenAI") as MockClient:
            mock_instance = MockClient.return_value

            # Mock async generator
            async def mock_stream(*args, **kwargs):
                chunk1 = MagicMock()
                chunk1.choices[0].delta.content = "Hello"
                yield chunk1
                chunk2 = MagicMock()
                chunk2.choices[0].delta.content = " World"
                yield chunk2

            mock_instance.chat.completions.create = AsyncMock(side_effect=mock_stream)

            client = MultiProviderLLMClient(mock_config)
            chunks = []
            async for chunk in client.generate_content_stream("Prompt"):
                chunks.append(chunk)

            assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_generate_stream_anthropic(self, mock_config):
        mock_config.provider = "anthropic"
        with patch("anthropic.AsyncAnthropic") as MockClient:
            mock_instance = MockClient.return_value

            # Mock stream context manager
            mock_stream_manager = MagicMock()

            async def mock_text_stream():
                yield "Hello"
                yield " World"

            mock_stream_manager.__aenter__.return_value.text_stream = mock_text_stream()
            mock_stream_manager.__aexit__ = AsyncMock()

            mock_instance.messages.stream.return_value = mock_stream_manager

            client = MultiProviderLLMClient(mock_config)
            chunks = []
            async for chunk in client.generate_content_stream("Prompt"):
                chunks.append(chunk)

            assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_generate_stream_with_messages_openai(self, mock_config):
        with patch("openai.AsyncOpenAI") as MockClient:
            mock_instance = MockClient.return_value

            async def mock_stream(*args, **kwargs):
                chunk = MagicMock()
                chunk.choices[0].delta.content = "Response"
                yield chunk

            mock_instance.chat.completions.create = AsyncMock(side_effect=mock_stream)

            client = MultiProviderLLMClient(mock_config)
            messages = [{"role": "user", "content": "Hi"}]

            chunks = []
            async for chunk in client.generate_content_stream_with_messages(messages):
                chunks.append(chunk)

            assert chunks == ["Response"]
            mock_instance.chat.completions.create.assert_called_once()
            assert mock_instance.chat.completions.create.call_args[1]["messages"] == messages
