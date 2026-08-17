"""
LLM Provider Presets


Predefined configurations for various LLM providers to simplify setup.
"""

from dataclasses import dataclass, field
from functools import cache, lru_cache
from typing import Any


@dataclass
class ModelPreset:
    """Preset configuration for a specific model."""

    name: str
    model_name: str
    description: str
    default_temperature: float = 0.7
    default_max_tokens: int | None = None
    default_top_p: float | None = None
    additional_params: dict[str, Any] | None = None
    max_input_tokens: int | None = None  # Context window (input tokens)
    max_output_tokens: int | None = None  # Max tokens the model can generate
    # Comparison metadata (populated via MODEL_COMPARISON_DATA lookup)
    cost_input_per_1m: float | None = None  # USD per 1M input tokens
    cost_output_per_1m: float | None = None  # USD per 1M output tokens
    is_open_source: bool = False
    quality_score: float | None = None  # 0–10 benchmark-based score
    speed_tier: str | None = None  # "fast" | "medium" | "slow"
    tags: list[str] = field(default_factory=list)


@dataclass
class ProviderPreset:
    """Preset configuration for an LLM provider."""

    provider_id: str
    provider_name: str
    description: str
    requires_api_key: bool = True
    requires_api_base: bool = False
    default_api_base: str | None = None
    models: list[ModelPreset] | None = None
    setup_instructions: str | None = None
    documentation_url: str | None = None


# Commercial Providers
OPENAI_PRESET = ProviderPreset(
    provider_id="openai",
    provider_name="OpenAI",
    description="Industry-leading models including GPT-4 and GPT-3.5",
    requires_api_key=True,
    documentation_url="https://platform.openai.com/docs",
    models=[
        # GPT-5 Series
        ModelPreset(
            name="GPT-5.5 Pro",
            model_name="gpt-5.5-pro",
            description="Most powerful GPT-5.5 model with maximum capabilities",
            default_max_tokens=32768,
        ),
        ModelPreset(name="GPT-5.5", model_name="gpt-5.5", description="Latest GPT-5.5 model", default_max_tokens=32768),
        ModelPreset(
            name="GPT-5.4 Pro",
            model_name="gpt-5.4-pro",
            description="GPT-5.4 Pro with enhanced reasoning",
            default_max_tokens=32768,
        ),
        ModelPreset(name="GPT-5.4", model_name="gpt-5.4", description="GPT-5.4 model", default_max_tokens=32768),
        ModelPreset(
            name="GPT-5.3 Instant",
            model_name="gpt-5.3-instant",
            description="Fast GPT-5.3 variant for quick responses",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-5.3 Instant Mini",
            model_name="gpt-5.3-instant-mini",
            description="Compact fast GPT-5.3 for lightweight tasks",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-5.3 Codex",
            model_name="gpt-5.3-codex",
            description="GPT-5.3 specialized for code generation",
            default_max_tokens=32768,
        ),
        ModelPreset(name="GPT-5.3", model_name="gpt-5.3", description="GPT-5.3 base model", default_max_tokens=32768),
        ModelPreset(
            name="GPT-5.2 Pro",
            model_name="gpt-5.2-pro",
            description="Most advanced GPT-5 model with enhanced capabilities",
            default_max_tokens=32768,
        ),
        ModelPreset(name="GPT-5.2", model_name="gpt-5.2", description="Latest GPT-5.2 model", default_max_tokens=32768),
        ModelPreset(
            name="GPT-5.1 Thinking",
            model_name="gpt-5.1-thinking",
            description="GPT-5.1 with advanced reasoning capabilities",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.1 Instant",
            model_name="gpt-5.1-instant",
            description="Fast GPT-5.1 variant for quick responses",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-5.1 Codex",
            model_name="gpt-5.1-codex",
            description="GPT-5.1 specialized for code generation",
            default_max_tokens=32768,
        ),
        ModelPreset(name="GPT-5.1", model_name="gpt-5.1", description="GPT-5.1 base model", default_max_tokens=32768),
        ModelPreset(
            name="GPT-5 Codex",
            model_name="gpt-5-codex",
            description="GPT-5 specialized for coding tasks",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5 nano",
            model_name="gpt-5-nano",
            description="Compact GPT-5 model for efficient processing",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-5 mini",
            model_name="gpt-5-mini",
            description="Smaller GPT-5 model for lightweight tasks",
            default_max_tokens=16384,
        ),
        ModelPreset(name="GPT-5", model_name="gpt-5", description="Base GPT-5 model", default_max_tokens=32768),
        # GPT-4.5 Series
        ModelPreset(
            name="GPT-4.5", model_name="gpt-4.5", description="Enhanced GPT-4.5 model", default_max_tokens=16384
        ),
        # GPT-4.1 Series
        ModelPreset(
            name="GPT-4.1 nano",
            model_name="gpt-4.1-nano",
            description="Compact GPT-4.1 variant",
            default_max_tokens=8192,
            default_temperature=1,
        ),
        ModelPreset(
            name="GPT-4.1 mini",
            model_name="gpt-4.1-mini",
            description="Smaller GPT-4.1 model",
            default_max_tokens=16384,
            default_temperature=1,
        ),
        ModelPreset(
            name="GPT-4.1",
            model_name="gpt-4.1",
            description="GPT-4.1 base model",
            default_max_tokens=16384,
            default_temperature=1,
        ),
        # GPT-4o Series
        ModelPreset(
            name="GPT-4o (Latest)",
            model_name="gpt-4o",
            description="High-intelligence flagship model for complex, multi-step tasks",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
            default_temperature=1,
        ),
        ModelPreset(
            name="GPT-4o Mini",
            model_name="gpt-4o-mini",
            description="Affordable and intelligent small model for fast, lightweight tasks",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
            default_temperature=1,
        ),
        # GPT-4 Series
        ModelPreset(
            name="GPT-4 Turbo",
            model_name="gpt-4-turbo",
            description="GPT-4 Turbo with 128K context window",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="GPT-4 Turbo Preview",
            model_name="gpt-4-turbo-preview",
            description="Latest GPT-4 Turbo preview model",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="GPT-4",
            model_name="gpt-4",
            description="Original GPT-4 model with 8K context",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GPT-4 32K",
            model_name="gpt-4-32k",
            description="GPT-4 with extended 32K context window",
            default_max_tokens=32768,
            max_input_tokens=32768,
            max_output_tokens=32768,
        ),
        # GPT-3.5 Series
        ModelPreset(
            name="GPT-3.5 Turbo",
            model_name="gpt-3.5-turbo",
            description="Fast and cost-effective model with 16K context",
            default_max_tokens=4096,
            max_input_tokens=16385,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="GPT-3.5 Turbo 16K",
            model_name="gpt-3.5-turbo-16k",
            description="Extended context version of GPT-3.5 Turbo",
            default_max_tokens=4096,
            max_input_tokens=16385,
            max_output_tokens=4096,
        ),
        # O-Series (Reasoning Models)
        ModelPreset(
            name="O4 Mini",
            model_name="o4-mini",
            description="Compact O4 reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=65536,
        ),
        ModelPreset(
            name="O3 Pro",
            model_name="o3-pro",
            description="Professional O3 reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="O3 Mini",
            model_name="o3-mini",
            description="Efficient O3 reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=65536,
        ),
        ModelPreset(
            name="O3",
            model_name="o3",
            description="Advanced O3 reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="O1 Pro",
            model_name="o1-pro",
            description="Professional O1 reasoning model",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="O1 Preview",
            model_name="o1-preview",
            description="Advanced reasoning model for complex problem solving",
            default_max_tokens=32768,
            max_input_tokens=128000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="O1 Mini",
            model_name="o1-mini",
            description="Faster and cheaper reasoning model",
            default_max_tokens=65536,
            max_input_tokens=128000,
            max_output_tokens=65536,
        ),
        ModelPreset(
            name="O1",
            model_name="o1",
            description="Base O1 reasoning model",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        # GPT OSS Series
        ModelPreset(
            name="GPT OSS 120B",
            model_name="gpt-oss-120b",
            description="Open-source GPT 120B parameter model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT OSS 20B",
            model_name="gpt-oss-20b",
            description="Open-source GPT 20B parameter model",
            default_max_tokens=8192,
        ),
        # ── Image Generation Models ───────────────────────────────────────────
        ModelPreset(
            name="GPT Image 2",
            model_name="gpt-image-2",
            description="OpenAI's latest image generation model. Supports square (1024x1024), portrait (1024x1536), and landscape (1536x1024).",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="DALL-E 3",
            model_name="dall-e-3",
            description="OpenAI DALL-E 3 image generation. High-quality photorealistic images with prompt rewriting.",
            tags=["image_generation"],
        ),
    ],
    setup_instructions="Get your API key from https://platform.openai.com/api-keys",
)


ANTHROPIC_PRESET = ProviderPreset(
    provider_id="anthropic",
    provider_name="Anthropic",
    description="Claude models known for safety and nuanced understanding",
    requires_api_key=True,
    documentation_url="https://docs.anthropic.com",
    models=[
        # Claude 5 Series
        ModelPreset(
            name="Claude Opus 5",
            model_name="claude-opus-5",
            description="Anthropic's next-generation flagship model — frontier reasoning, coding, and agentic capabilities",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 5",
            model_name="claude-sonnet-5",
            description="Balanced Claude 5 model for enterprise workloads",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 5",
            model_name="claude-haiku-5",
            description="Fast and efficient Claude 5 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 4.7 Series
        ModelPreset(
            name="Claude Opus 4.7",
            model_name="claude-opus-4-7",
            description="Latest and most powerful Claude model with state-of-the-art capabilities",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 4.7",
            model_name="claude-sonnet-4-7",
            description="Balanced Claude 4.7 model for enterprise workloads",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.7",
            model_name="claude-haiku-4-7",
            description="Fast and efficient Claude 4.7 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 4.6 Series
        ModelPreset(
            name="Claude Opus 4.6",
            model_name="claude-opus-4-6",
            description="Most powerful Claude 4.6 model with state-of-the-art capabilities",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 4.6",
            model_name="claude-sonnet-4-6",
            description="Balanced Claude 4.6 model for enterprise workloads",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.6",
            model_name="claude-haiku-4-6",
            description="Fast and efficient Claude 4.6 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 4.5 Series
        ModelPreset(
            name="Claude Opus 4.5",
            model_name="claude-opus-4-5",
            description="Most powerful Claude 4.5 model with enhanced capabilities",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 4.5",
            model_name="claude-sonnet-4-5",
            description="Balanced Claude 4.5 model for enterprise workloads",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.5",
            model_name="claude-haiku-4-5",
            description="Fast and efficient Claude 4.5 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 4.1 Series
        ModelPreset(
            name="Claude Opus 4.1",
            model_name="claude-opus-4-1",
            description="Advanced Claude 4.1 Opus model",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 4.1",
            model_name="claude-sonnet-4-1",
            description="Balanced Claude 4.1 model for enterprise workloads",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.1",
            model_name="claude-haiku-4-1",
            description="Fast and efficient Claude 4.1 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 4 Series
        ModelPreset(
            name="Claude Opus 4",
            model_name="claude-opus-4",
            description="Next-generation Claude 4 Opus model",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=32000,
        ),
        ModelPreset(
            name="Claude Sonnet 4",
            model_name="claude-sonnet-4",
            description="Balanced Claude 4 Sonnet model",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4",
            model_name="claude-haiku-4",
            description="Fast and efficient Claude 4 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 3.7 Series
        ModelPreset(
            name="Claude 3.7 Sonnet",
            model_name="claude-3.7-sonnet",
            description="Enhanced Claude 3.7 Sonnet with improved performance",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        # Claude 3.5 Series
        ModelPreset(
            name="Claude 3.5 Sonnet (Latest)",
            model_name="claude-3-5-sonnet-20241022",
            description="Most intelligent Claude 3.5 model, combining top-tier performance with improved speed",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet (June 2024)",
            model_name="claude-3-5-sonnet-20240620",
            description="Previous version of Claude 3.5 Sonnet",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet",
            model_name="claude-3.5-sonnet",
            description="Claude 3.5 Sonnet base model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku (Latest)",
            model_name="claude-3-5-haiku-20241022",
            description="Fastest and most compact Claude 3.5 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku",
            model_name="claude-3.5-haiku",
            description="Claude 3.5 Haiku base model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Claude 3 Series
        ModelPreset(
            name="Claude 3 Opus",
            model_name="claude-3-opus-20240229",
            description="Most powerful Claude 3 model for highly complex tasks",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Sonnet",
            model_name="claude-3-sonnet-20240229",
            description="Balanced Claude 3 model for enterprise workloads",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Haiku",
            model_name="claude-3-haiku-20240307",
            description="Fastest and most compact Claude 3 model",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        # Claude 2 Series
        ModelPreset(
            name="Claude 2.1",
            model_name="claude-2.1",
            description="Updated Claude 2 with improved accuracy",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Claude 2.0",
            model_name="claude-2.0",
            description="Original Claude 2 model",
            default_max_tokens=4096,
            max_input_tokens=100000,
            max_output_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://console.anthropic.com/settings/keys",
)


GEMINI_PRESET = ProviderPreset(
    provider_id="gemini",
    provider_name="Google Gemini",
    description="Google's multimodal AI models",
    requires_api_key=True,
    documentation_url="https://ai.google.dev/docs",
    models=[
        # Gemini 3.1 Series (Latest)
        ModelPreset(
            name="Gemini 3.1 Pro Preview",
            model_name="gemini-3.1-pro-preview",
            description="Google's current flagship reasoning model, optimized for complex agentic workflows and coding",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 3.1 Flash-Lite Preview",
            model_name="gemini-3.1-flash-lite-preview",
            description="Most cost-efficient Gemini 3.1 model for high-volume, low-latency tasks",
            default_max_tokens=16384,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        # Gemini 3 Series
        ModelPreset(
            name="Gemini 3 Flash",
            model_name="gemini-3-flash",
            description="Fast multimodal model for complex agentic problems with strong reasoning",
            default_max_tokens=16384,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 3 Pro",
            model_name="gemini-3-pro",
            description="Next-generation Gemini 3 Pro model",
            default_max_tokens=32768,
        ),
        # Gemini 2.5 Series
        ModelPreset(
            name="Gemini 2.5 Pro Preview 06-05",
            model_name="gemini-2.5-pro-preview-06-05",
            description="Preview version of Gemini 2.5 Pro",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 2.5 Pro",
            model_name="gemini-2.5-pro",
            description="Advanced Gemini 2.5 Pro model",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash-Lite",
            model_name="gemini-2.5-flash-lite",
            description="Lightweight Gemini 2.5 Flash variant",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash",
            model_name="gemini-2.5-flash",
            description="Fast Gemini 2.5 model",
            default_max_tokens=16384,
        ),
        # Gemini 2.0 Series
        ModelPreset(
            name="Gemini 2.0 Flash Thinking",
            model_name="gemini-2.0-flash-thinking",
            description="Gemini 2.0 Flash with enhanced reasoning capabilities",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash-Lite",
            model_name="gemini-2.0-flash-lite",
            description="Lightweight Gemini 2.0 Flash model",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash",
            model_name="gemini-2.0-flash",
            description="Gemini 2.0 Flash with multimodal capabilities",
            default_max_tokens=16384,
        ),
        # Gemini 1.5 Series
        ModelPreset(
            name="Gemini 1.5 Pro",
            model_name="gemini-1.5-pro",
            description="Most capable Gemini model with long context",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 1.5 Flash 8B",
            model_name="gemini-1.5-flash-8b",
            description="Compact 8B parameter Gemini Flash model",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 1.5 Flash",
            model_name="gemini-1.5-flash",
            description="Fast and efficient Gemini model",
            default_max_tokens=16384,
        ),
        # Gemini 1.0 Series
        ModelPreset(
            name="Gemini 1.0 Pro",
            model_name="gemini-1.0-pro",
            description="Original Gemini Pro model",
            default_max_tokens=32760,
        ),
        # Gemma 4 Series (Google's Open Models — built from Gemini 3 research)
        ModelPreset(
            name="Gemma 4 31B",
            model_name="gemma-4-31b-it",
            description="Most intelligent Gemma 4 model, instruction-tuned, 31B parameters",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 4 26B",
            model_name="gemma-4-26b-a4b-it",
            description="Efficient Gemma 4 model with MoE architecture, 4B active parameters",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        # Gemma 3 Series (Google's Open Models)
        ModelPreset(
            name="Gemma 3 27B",
            model_name="gemma-3-27b",
            description="Large 27B parameter Gemma 3 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 12B",
            model_name="gemma-3-12b",
            description="Medium 12B parameter Gemma 3 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 4B",
            model_name="gemma-3-4b",
            description="Compact 4B parameter Gemma 3 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 1B",
            model_name="gemma-3-1b",
            description="Ultra-compact 1B parameter Gemma 3 model",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Gemma 3n E4B Instructed LiteRT Preview",
            model_name="gemma-3n-e4b-instruct-litert-preview",
            description="Instruction-tuned Gemma 3n E4B with LiteRT preview",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3n E4B Instructed",
            model_name="gemma-3n-e4b-instruct",
            description="Instruction-tuned Gemma 3n E4B model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3n E4B",
            model_name="gemma-3n-e4b",
            description="Gemma 3n E4B base model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3n E2B Instructed LiteRT (Preview)",
            model_name="gemma-3n-e2b-instruct-litert-preview",
            description="Instruction-tuned Gemma 3n E2B with LiteRT preview",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3n E2B Instructed",
            model_name="gemma-3n-e2b-instruct",
            description="Instruction-tuned Gemma 3n E2B model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3n E2B",
            model_name="gemma-3n-e2b",
            description="Gemma 3n E2B base model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 2 27B",
            model_name="gemma-2-27b",
            description="Large 27B parameter Gemma 2 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 2 9B",
            model_name="gemma-2-9b",
            description="Medium 9B parameter Gemma 2 model",
            default_max_tokens=8192,
        ),
        # Specialized Models
        ModelPreset(
            name="MedGemma 4B IT",
            model_name="medgemma-4b-it",
            description="Medical domain-specialized Gemma model (4B instructed)",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemini Diffusion",
            model_name="gemini-diffusion",
            description="Gemini model specialized for diffusion tasks",
            default_max_tokens=8192,
        ),
        # ── Image Generation Models ───────────────────────────────────────────
        ModelPreset(
            name="Imagen 3",
            model_name="imagen-3.0-generate-002",
            description="Google Imagen 3 — state-of-the-art image generation. Requires a Google AI Studio or Vertex AI API key.",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="Imagen 3 Fast",
            model_name="imagen-3.0-fast-generate-001",
            description="Google Imagen 3 Fast — faster, lower-cost image generation.",
            tags=["image_generation"],
        ),
    ],
    setup_instructions="Get your API key from https://makersuite.google.com/app/apikey",
)


DEEPSEEK_PRESET = ProviderPreset(
    provider_id="deepseek",
    provider_name="DeepSeek",
    description="DeepSeek's official API with OpenAI-compatible chat and reasoning models",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.deepseek.com",
    documentation_url="https://api-docs.deepseek.com/",
    models=[
        ModelPreset(
            name="DeepSeek V4 Flash",
            model_name="deepseek-v4-flash",
            description="Current fast official DeepSeek model with 1M context and support for thinking or non-thinking modes",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=384000,
        ),
        ModelPreset(
            name="DeepSeek V4 Pro",
            model_name="deepseek-v4-pro",
            description="Current flagship DeepSeek model for high-end reasoning, coding, and agentic workflows",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=384000,
        ),
        ModelPreset(
            name="DeepSeek Chat",
            model_name="deepseek-chat",
            description="Compatibility alias currently mapped to DeepSeek-V4-Flash non-thinking mode; deprecated on 2026-07-24 15:59 UTC",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=384000,
        ),
        ModelPreset(
            name="DeepSeek Reasoner",
            model_name="deepseek-reasoner",
            description="Compatibility alias currently mapped to DeepSeek-V4-Flash thinking mode; deprecated on 2026-07-24 15:59 UTC",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=384000,
        ),
    ],
    setup_instructions="Create an API key in the DeepSeek console. The default API base is https://api.deepseek.com.",
)


# Cloud Provider Services
AWS_BEDROCK_PRESET = ProviderPreset(
    provider_id="bedrock",
    provider_name="AWS Bedrock",
    description="Access to multiple foundation models through AWS",
    requires_api_key=False,
    documentation_url="https://docs.aws.amazon.com/bedrock/",
    models=[
        # Anthropic Claude on Bedrock
        ModelPreset(
            name="Claude Opus 5 (Bedrock)",
            model_name="anthropic.claude-opus-5-v1:0",
            description="Anthropic's next-generation flagship model via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 5 (Bedrock)",
            model_name="anthropic.claude-sonnet-5-v1:0",
            description="Claude Sonnet 5 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 5 (Bedrock)",
            model_name="anthropic.claude-haiku-5-v1:0",
            description="Claude Haiku 5 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude Opus 4.7 (Bedrock)",
            model_name="anthropic.claude-opus-4-7-v1:0",
            description="Latest Claude Opus 4.7 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.7 (Bedrock)",
            model_name="anthropic.claude-sonnet-4-7-v1:0",
            description="Claude Sonnet 4.7 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4.7 (Bedrock)",
            model_name="anthropic.claude-haiku-4-7-v1:0",
            description="Claude Haiku 4.7 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude Opus 4.6 (Bedrock)",
            model_name="anthropic.claude-opus-4-6-v1:0",
            description="Claude Opus 4.6 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.6 (Bedrock)",
            model_name="anthropic.claude-sonnet-4-6-v1:0",
            description="Claude Sonnet 4.6 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.5 (Bedrock)",
            model_name="anthropic.claude-sonnet-4-5-20250514-v1:0",
            description="Latest Claude Sonnet 4.5 via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude 3.7 Sonnet (Bedrock)",
            model_name="anthropic.claude-3-7-sonnet-20250219-v1:0",
            description="Claude 3.7 Sonnet with extended thinking via Bedrock",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet v2 (Bedrock)",
            model_name="anthropic.claude-3-5-sonnet-20241022-v2:0",
            description="Claude 3.5 Sonnet v2 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku (Bedrock)",
            model_name="anthropic.claude-3-5-haiku-20241022-v1:0",
            description="Fast Claude 3.5 Haiku via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet (Bedrock)",
            model_name="anthropic.claude-3-5-sonnet-20240620-v1:0",
            description="Claude 3.5 Sonnet v1 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3 Opus (Bedrock)",
            model_name="anthropic.claude-3-opus-20240229-v1:0",
            description="Claude 3 Opus via Bedrock",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Haiku (Bedrock)",
            model_name="anthropic.claude-3-haiku-20240307-v1:0",
            description="Fast Claude 3 Haiku via Bedrock",
            default_max_tokens=4096,
        ),
        # Amazon Nova Series
        ModelPreset(
            name="Amazon Nova Premier",
            model_name="amazon.nova-premier-v1:0",
            description="Amazon's most capable Nova model for complex tasks",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Amazon Nova Pro",
            model_name="amazon.nova-pro-v1:0",
            description="Amazon Nova Pro — highly capable multimodal model",
            default_max_tokens=5120,
        ),
        ModelPreset(
            name="Amazon Nova Lite",
            model_name="amazon.nova-lite-v1:0",
            description="Amazon Nova Lite — fast, low-cost multimodal model",
            default_max_tokens=5120,
        ),
        ModelPreset(
            name="Amazon Nova Micro",
            model_name="amazon.nova-micro-v1:0",
            description="Amazon Nova Micro — text-only, lowest latency",
            default_max_tokens=5120,
        ),
        # Meta Llama 4
        ModelPreset(
            name="Llama 4 Maverick (Bedrock)",
            model_name="meta.llama4-maverick-17b-128e-instruct-v1:0",
            description="Meta Llama 4 Maverick 17B MoE via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 4 Scout (Bedrock)",
            model_name="meta.llama4-scout-17b-16e-instruct-v1:0",
            description="Meta Llama 4 Scout 17B MoE via Bedrock",
            default_max_tokens=8192,
        ),
        # Meta Llama 3.3
        ModelPreset(
            name="Llama 3.3 70B (Bedrock)",
            model_name="meta.llama3-3-70b-instruct-v1:0",
            description="Meta Llama 3.3 70B via Bedrock",
            default_max_tokens=8192,
        ),
        # Meta Llama 3.2
        ModelPreset(
            name="Llama 3.2 90B (Bedrock)",
            model_name="meta.llama3-2-90b-instruct-v1:0",
            description="Meta Llama 3.2 90B vision model via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.2 11B (Bedrock)",
            model_name="meta.llama3-2-11b-instruct-v1:0",
            description="Meta Llama 3.2 11B vision model via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.2 3B (Bedrock)",
            model_name="meta.llama3-2-3b-instruct-v1:0",
            description="Meta Llama 3.2 3B via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.2 1B (Bedrock)",
            model_name="meta.llama3-2-1b-instruct-v1:0",
            description="Meta Llama 3.2 1B — ultra-efficient via Bedrock",
            default_max_tokens=8192,
        ),
        # Meta Llama 3.1
        ModelPreset(
            name="Llama 3.1 405B (Bedrock)",
            model_name="meta.llama3-1-405b-instruct-v1:0",
            description="Meta Llama 3.1 405B — largest Llama 3.1 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 70B (Bedrock)",
            model_name="meta.llama3-1-70b-instruct-v1:0",
            description="Meta Llama 3.1 70B via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 8B (Bedrock)",
            model_name="meta.llama3-1-8b-instruct-v1:0",
            description="Meta Llama 3.1 8B via Bedrock",
            default_max_tokens=8192,
        ),
        # Mistral
        ModelPreset(
            name="Mistral Large 2 (Bedrock)",
            model_name="mistral.mistral-large-2407-v1:0",
            description="Mistral Large 2 via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Mistral Small (Bedrock)",
            model_name="mistral.mistral-small-2402-v1:0",
            description="Mistral Small via Bedrock",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Mixtral 8x7B (Bedrock)",
            model_name="mistral.mixtral-8x7b-instruct-v0:1",
            description="Mistral Mixtral 8x7B MoE via Bedrock",
            default_max_tokens=4096,
        ),
        # Cohere
        ModelPreset(
            name="Command R+ (Bedrock)",
            model_name="cohere.command-r-plus-v1:0",
            description="Cohere Command R+ via Bedrock",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Command R (Bedrock)",
            model_name="cohere.command-r-v1:0",
            description="Cohere Command R via Bedrock",
            default_max_tokens=4096,
        ),
        # DeepSeek
        ModelPreset(
            name="DeepSeek V4 Pro (Bedrock)",
            model_name="deepseek.v4-pro-v1:0",
            description="DeepSeek V4 Pro flagship model via Bedrock Marketplace",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="DeepSeek R1 (Bedrock)",
            model_name="deepseek.r1-v1:0",
            description="DeepSeek R1 reasoning model via Bedrock Marketplace",
            default_max_tokens=16384,
        ),
    ],
    setup_instructions="Configure AWS credentials: aws_access_key_id, aws_secret_access_key, aws_region in additional_params",
)


VERTEX_AI_PRESET = ProviderPreset(
    provider_id="vertex_ai",
    provider_name="Google Vertex AI",
    description="Google Cloud's unified AI platform",
    requires_api_key=False,
    documentation_url="https://cloud.google.com/vertex-ai/docs",
    models=[
        # Gemini 3.x Series
        ModelPreset(
            name="Gemini 3.1 Pro Preview (Vertex)",
            model_name="gemini-3.1-pro-preview",
            description="Google Gemini 3.1 Pro preview via Vertex AI",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 3 Pro (Vertex)",
            model_name="gemini-3-pro",
            description="Google Gemini 3 Pro via Vertex AI",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 3 Flash (Vertex)",
            model_name="gemini-3-flash",
            description="Google Gemini 3 Flash via Vertex AI",
            default_max_tokens=16384,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        # Gemini 2.5 Series
        ModelPreset(
            name="Gemini 2.5 Pro (Vertex)",
            model_name="gemini-2.5-pro",
            description="Most capable Gemini 2.5 Pro via Vertex AI",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash (Vertex)",
            model_name="gemini-2.5-flash",
            description="Fast Gemini 2.5 Flash via Vertex AI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash-Lite (Vertex)",
            model_name="gemini-2.5-flash-lite",
            description="Lightweight Gemini 2.5 Flash variant via Vertex AI",
            default_max_tokens=16384,
        ),
        # Gemini 2.0 Series
        ModelPreset(
            name="Gemini 2.0 Flash (Vertex)",
            model_name="gemini-2.0-flash",
            description="Gemini 2.0 Flash with multimodal capabilities via Vertex AI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash-Lite (Vertex)",
            model_name="gemini-2.0-flash-lite",
            description="Lightweight Gemini 2.0 Flash via Vertex AI",
            default_max_tokens=16384,
        ),
        # Gemini 1.5 Series
        ModelPreset(
            name="Gemini 1.5 Pro (Vertex)",
            model_name="gemini-1.5-pro",
            description="Gemini 1.5 Pro via Vertex AI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemini 1.5 Flash (Vertex)",
            model_name="gemini-1.5-flash",
            description="Fast Gemini 1.5 Flash via Vertex AI",
            default_max_tokens=8192,
        ),
        # Claude on Vertex AI
        ModelPreset(
            name="Claude Opus 5 (Vertex)",
            model_name="claude-opus-5@20260601",
            description="Anthropic's next-generation flagship model via Vertex AI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 5 (Vertex)",
            model_name="claude-sonnet-5@20260601",
            description="Claude Sonnet 5 via Vertex AI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 5 (Vertex)",
            model_name="claude-haiku-5@20260601",
            description="Claude Haiku 5 via Vertex AI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.7 Sonnet (Vertex)",
            model_name="claude-3-7-sonnet@20250219",
            description="Claude 3.7 Sonnet via Vertex AI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet v2 (Vertex)",
            model_name="claude-3-5-sonnet-v2@20241022",
            description="Claude 3.5 Sonnet v2 via Vertex AI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku (Vertex)",
            model_name="claude-3-5-haiku@20241022",
            description="Fast Claude 3.5 Haiku via Vertex AI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3 Opus (Vertex)",
            model_name="claude-3-opus@20240229",
            description="Claude 3 Opus via Vertex AI",
            default_max_tokens=4096,
        ),
        # Llama on Vertex AI (via Model Garden)
        ModelPreset(
            name="Llama 3.3 70B (Vertex)",
            model_name="meta/llama-3.3-70b-instruct-maas",
            description="Meta Llama 3.3 70B via Vertex AI Model Garden",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 405B (Vertex)",
            model_name="meta/llama3-405b-instruct-maas",
            description="Meta Llama 3.1 405B via Vertex AI Model Garden",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 70B (Vertex)",
            model_name="meta/llama3-70b-instruct-maas",
            description="Meta Llama 3.1 70B via Vertex AI Model Garden",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 8B (Vertex)",
            model_name="meta/llama3-8b-instruct-maas",
            description="Meta Llama 3.1 8B via Vertex AI Model Garden",
            default_max_tokens=8192,
        ),
        # Mistral on Vertex AI
        ModelPreset(
            name="Mistral Large (Vertex)",
            model_name="mistral-large@2411",
            description="Mistral Large via Vertex AI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Mistral Nemo (Vertex)",
            model_name="mistral-nemo@2407",
            description="Mistral Nemo 12B via Vertex AI",
            default_max_tokens=8192,
        ),
    ],
    setup_instructions="Configure GCP credentials: vertex_project, vertex_location, service_account_json in additional_params",
)


AZURE_OPENAI_PRESET = ProviderPreset(
    provider_id="azure_openai",
    provider_name="Azure OpenAI",
    description="OpenAI models hosted on Azure",
    requires_api_key=True,
    requires_api_base=True,
    documentation_url="https://learn.microsoft.com/azure/ai-services/openai/",
    models=[
        ModelPreset(
            name="GPT-4.1 (Azure)",
            model_name="gpt-4.1",
            description="GPT-4.1 via Azure OpenAI",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-4.1 mini (Azure)",
            model_name="gpt-4.1-mini",
            description="GPT-4.1 mini via Azure OpenAI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4.1 nano (Azure)",
            model_name="gpt-4.1-nano",
            description="GPT-4.1 nano — fastest, most efficient via Azure OpenAI",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-4o (Azure)",
            model_name="gpt-4o",
            description="GPT-4o multimodal model via Azure OpenAI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4o mini (Azure)",
            model_name="gpt-4o-mini",
            description="GPT-4o mini via Azure OpenAI",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="O3 (Azure)",
            model_name="o3",
            description="OpenAI O3 reasoning model via Azure OpenAI",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="O3 mini (Azure)",
            model_name="o3-mini",
            description="OpenAI O3 mini via Azure OpenAI",
            default_max_tokens=65536,
        ),
        ModelPreset(
            name="O4 mini (Azure)",
            model_name="o4-mini",
            description="OpenAI O4 mini reasoning model via Azure OpenAI",
            default_max_tokens=65536,
        ),
        ModelPreset(
            name="GPT-4 Turbo (Azure)",
            model_name="gpt-4-turbo",
            description="GPT-4 Turbo via Azure OpenAI",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="GPT-4 (Azure)", model_name="gpt-4", description="GPT-4 via Azure OpenAI", default_max_tokens=8192
        ),
        ModelPreset(
            name="GPT-3.5 Turbo (Azure)",
            model_name="gpt-3.5-turbo",
            description="GPT-3.5 Turbo via Azure OpenAI",
            default_max_tokens=4096,
        ),
    ],
    setup_instructions="Set api_base to your Azure endpoint and configure deployment_name, api_version in additional_params",
)


# Open Source / Self-Hosted
OLLAMA_PRESET = ProviderPreset(
    provider_id="ollama",
    provider_name="Ollama",
    description="Run open-source models locally",
    requires_api_key=False,
    requires_api_base=True,
    default_api_base="http://localhost:11434",
    documentation_url="https://ollama.ai/",
    models=[
        # Llama 4 Series (Meta, MoE architecture)
        ModelPreset(
            name="Llama 4 Maverick",
            model_name="llama4:maverick",
            description="Meta's most powerful open model — 17B active / 400B total params, 128 experts, 1M context, beats GPT-4o on benchmarks",
            default_max_tokens=8192,
            max_input_tokens=1000000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Llama 4 Scout",
            model_name="llama4:scout",
            description="Efficient Llama 4 — 17B active / 16 experts, 10M context, fits on single H100, best in class for its size",
            default_max_tokens=8192,
            max_input_tokens=10000000,
            max_output_tokens=8192,
        ),
        # Mistral New Models
        ModelPreset(
            name="Mistral Small 4",
            model_name="mistral-small4:latest",
            description="Unified reasoning + vision + coding model, 119B/6.5B active MoE, Apache 2.0, 256K context",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Mistral Large 3",
            model_name="mistral-large3:latest",
            description="Mistral's flagship open-weight model released December 2025",
            default_max_tokens=32768,
            max_input_tokens=128000,
            max_output_tokens=32768,
        ),
        # DeepSeek V3.2 Series
        ModelPreset(
            name="DeepSeek-V3.2-Speciale",
            model_name="deepseek-v3.2-speciale",
            description="Specialized DeepSeek V3.2 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek-V3.2-Exp",
            model_name="deepseek-v3.2-exp",
            description="Experimental DeepSeek V3.2 model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek-V3.2 (Thinking)",
            model_name="deepseek-v3.2-thinking",
            description="DeepSeek V3.2 with enhanced reasoning capabilities",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek-V3.2 (Non-thinking)",
            model_name="deepseek-v3.2",
            description="Standard DeepSeek V3.2 model",
            default_max_tokens=8192,
        ),
        # DeepSeek V3 Series
        ModelPreset(
            name="DeepSeek-V3.1", model_name="deepseek-v3.1", description="DeepSeek V3.1 model", default_max_tokens=8192
        ),
        ModelPreset(
            name="DeepSeek-V3 0324",
            model_name="deepseek-v3-0324",
            description="DeepSeek V3 version from March 2024",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek-V3", model_name="deepseek-v3", description="DeepSeek V3 base model", default_max_tokens=8192
        ),
        # DeepSeek V2 Series
        ModelPreset(
            name="DeepSeek-V2.5", model_name="deepseek-v2.5", description="DeepSeek V2.5 model", default_max_tokens=8192
        ),
        # DeepSeek R1 Series
        ModelPreset(
            name="DeepSeek-R1-0528",
            model_name="deepseek-r1-0528",
            description="DeepSeek R1 version from May 2028",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek-R1",
            model_name="deepseek-r1",
            description="DeepSeek R1 reasoning model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Zero",
            model_name="deepseek-r1-zero",
            description="DeepSeek R1 Zero base model",
            default_max_tokens=8192,
        ),
        # DeepSeek R1 Distill Series
        ModelPreset(
            name="DeepSeek R1 Distill Llama 70B",
            model_name="deepseek-r1-distill-llama-70b",
            description="DeepSeek R1 distilled into Llama 70B",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Llama 8B",
            model_name="deepseek-r1-distill-llama-8b",
            description="DeepSeek R1 distilled into Llama 8B",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 32B",
            model_name="deepseek-r1-distill-qwen-32b",
            description="DeepSeek R1 distilled into Qwen 32B",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 14B",
            model_name="deepseek-r1-distill-qwen-14b",
            description="DeepSeek R1 distilled into Qwen 14B",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 7B",
            model_name="deepseek-r1-distill-qwen-7b",
            description="DeepSeek R1 distilled into Qwen 7B",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 1.5B",
            model_name="deepseek-r1-distill-qwen-1.5b",
            description="DeepSeek R1 distilled into Qwen 1.5B",
            default_max_tokens=8192,
        ),
        # DeepSeek VL Series (Vision-Language)
        ModelPreset(
            name="DeepSeek VL2",
            model_name="deepseek-vl2",
            description="DeepSeek Vision-Language model v2",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek VL2 Small",
            model_name="deepseek-vl2-small",
            description="Compact DeepSeek Vision-Language model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek VL2 Tiny",
            model_name="deepseek-vl2-tiny",
            description="Ultra-compact DeepSeek Vision-Language model",
            default_max_tokens=8192,
        ),
        # Llama Series
        ModelPreset(
            name="Llama 3 70B", model_name="llama3:70b", description="Meta's Llama 3 70B model", default_max_tokens=2048
        ),
        ModelPreset(
            name="Llama 3 8B", model_name="llama3:8b", description="Meta's Llama 3 8B model", default_max_tokens=2048
        ),
        # Mistral Series
        ModelPreset(
            name="Mistral", model_name="mistral:latest", description="Mistral 7B model", default_max_tokens=8192
        ),
        ModelPreset(
            name="Mixtral 8x7B",
            model_name="mixtral:8x7b",
            description="Mixture of experts model",
            default_max_tokens=4096,
        ),
        # Code Models
        ModelPreset(
            name="Code Llama",
            model_name="codellama:34b",
            description="Code-specialized Llama model",
            default_max_tokens=4096,
        ),
        # Microsoft Models
        ModelPreset(
            name="Phi-3 Mini", model_name="phi3:mini", description="Microsoft's compact model", default_max_tokens=2048
        ),
    ],
    setup_instructions="Install Ollama and pull models: ollama pull deepseek-v3.2 or ollama pull llama3:70b",
)


HUGGINGFACE_PRESET = ProviderPreset(
    provider_id="huggingface",
    provider_name="Hugging Face",
    description="Access thousands of open-source models",
    requires_api_key=True,
    documentation_url="https://huggingface.co/docs/api-inference/",
    models=[
        ModelPreset(
            name="Mistral 7B Instruct",
            model_name="mistralai/Mistral-7B-Instruct-v0.2",
            description="Mistral AI's instruction-tuned model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Zephyr 7B",
            model_name="HuggingFaceH4/zephyr-7b-beta",
            description="Fine-tuned Mistral model",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Llama 2 70B Chat",
            model_name="meta-llama/Llama-2-70b-chat-hf",
            description="Meta's Llama 2 70B chat model",
            default_max_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://huggingface.co/settings/tokens",
)


LM_STUDIO_PRESET = ProviderPreset(
    provider_id="lm_studio",
    provider_name="LM Studio",
    description="Run models locally with LM Studio",
    requires_api_key=False,
    requires_api_base=True,
    default_api_base="http://localhost:1234/v1",
    documentation_url="https://lmstudio.ai/",
    models=[
        ModelPreset(
            name="Local Model",
            model_name="local-model",
            description="Model loaded in LM Studio (use actual model name)",
            default_max_tokens=2048,
        ),
    ],
    setup_instructions="Start LM Studio local server and load a model",
)


TOGETHER_AI_PRESET = ProviderPreset(
    provider_id="together_ai",
    provider_name="Together AI",
    description="Fast and affordable inference for open-source models",
    requires_api_key=True,
    documentation_url="https://docs.together.ai/",
    models=[
        # Meta Llama 4
        ModelPreset(
            name="Llama 4 Maverick",
            model_name="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            description="Meta's Llama 4 Maverick 17B MoE — 128 experts, 1M context",
            default_max_tokens=16384,
            max_input_tokens=524288,
        ),
        ModelPreset(
            name="Llama 4 Scout",
            model_name="meta-llama/Llama-4-Scout-17B-16E-Instruct",
            description="Meta's Llama 4 Scout — efficient 17B MoE, 10M context",
            default_max_tokens=16384,
            max_input_tokens=10485760,
        ),
        # Meta Llama 3.x
        ModelPreset(
            name="Llama 3.3 70B Turbo",
            model_name="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            description="Meta's Llama 3.3 70B — fast Turbo variant",
            default_max_tokens=32768,
            max_input_tokens=131072,
        ),
        ModelPreset(
            name="Llama 3.1 405B Instruct Turbo",
            model_name="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            description="Meta's largest open model — 405B",
            default_max_tokens=4096,
            max_input_tokens=130815,
        ),
        ModelPreset(
            name="Llama 3.1 70B Instruct Turbo",
            model_name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            description="Meta's Llama 3.1 70B — fast Turbo variant",
            default_max_tokens=8192,
            max_input_tokens=131072,
        ),
        ModelPreset(
            name="Llama 3.1 8B Instruct Turbo",
            model_name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            description="Meta's Llama 3.1 8B — ultra-fast and lightweight",
            default_max_tokens=8192,
            max_input_tokens=131072,
        ),
        # DeepSeek
        ModelPreset(
            name="DeepSeek V4 Pro",
            model_name="deepseek-ai/DeepSeek-V4-Pro",
            description="DeepSeek V4 Pro — current flagship open-source reasoning, coding, and agentic model",
            default_max_tokens=8192,
            max_input_tokens=1000000,
        ),
        ModelPreset(
            name="DeepSeek V4 Flash",
            model_name="deepseek-ai/DeepSeek-V4-Flash",
            description="DeepSeek V4 Flash — fast open-source model with thinking/non-thinking modes",
            default_max_tokens=8192,
            max_input_tokens=1000000,
        ),
        ModelPreset(
            name="DeepSeek V3",
            model_name="deepseek-ai/DeepSeek-V3",
            description="DeepSeek V3 — strong open-source reasoning and coding model",
            default_max_tokens=8192,
            max_input_tokens=65536,
        ),
        ModelPreset(
            name="DeepSeek R1",
            model_name="deepseek-ai/DeepSeek-R1",
            description="DeepSeek R1 — open-source reasoning model",
            default_max_tokens=16384,
            max_input_tokens=65536,
        ),
        # Qwen
        ModelPreset(
            name="Qwen3 235B A22B",
            model_name="Qwen/Qwen3-235B-A22B",
            description="Qwen3 largest MoE model with hybrid thinking",
            default_max_tokens=8192,
            max_input_tokens=40960,
        ),
        ModelPreset(
            name="Qwen2.5 72B Instruct Turbo",
            model_name="Qwen/Qwen2.5-72B-Instruct-Turbo",
            description="Qwen2.5 72B — fast Turbo variant",
            default_max_tokens=8192,
            max_input_tokens=32768,
        ),
        ModelPreset(
            name="Qwen2.5 7B Instruct Turbo",
            model_name="Qwen/Qwen2.5-7B-Instruct-Turbo",
            description="Qwen2.5 7B — fast compact model",
            default_max_tokens=8192,
            max_input_tokens=32768,
        ),
        # Mistral
        ModelPreset(
            name="Mistral 7B Instruct v0.3",
            model_name="mistralai/Mistral-7B-Instruct-v0.3",
            description="Mistral 7B — latest v0.3 release",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Mixtral 8x7B Instruct",
            model_name="mistralai/Mixtral-8x7B-Instruct-v0.1",
            description="Mistral's Mixtral 8x7B MoE",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Mixtral 8x22B Instruct",
            model_name="mistralai/Mixtral-8x22B-Instruct-v0.1",
            description="Mistral's largest open MoE model",
            default_max_tokens=65536,
        ),
        # Google
        ModelPreset(
            name="Gemma 2 27B",
            model_name="google/gemma-2-27b-it",
            description="Google's Gemma 2 27B instruction-tuned",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 2 9B",
            model_name="google/gemma-2-9b-it",
            description="Google's Gemma 2 9B instruction-tuned",
            default_max_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://api.together.xyz/settings/api-keys",
)


REPLICATE_PRESET = ProviderPreset(
    provider_id="replicate",
    provider_name="Replicate",
    description="Run open-source models in the cloud",
    requires_api_key=True,
    documentation_url="https://replicate.com/docs",
    models=[
        ModelPreset(
            name="Llama 3 70B",
            model_name="meta/llama-3-70b-instruct",
            description="Meta's Llama 3 70B",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Mixtral 8x7B",
            model_name="mistralai/mixtral-8x7b-instruct-v0.1",
            description="Mistral's mixture of experts",
            default_max_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://replicate.com/account/api-tokens",
)


MINIMAX_PRESET = ProviderPreset(
    provider_id="minimax",
    provider_name="MiniMax",
    description="Advanced AI models from MiniMax with strong multilingual capabilities",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.minimax.chat/v1",
    documentation_url="https://www.minimax.chat/document/",
    models=[
        ModelPreset(
            name="MiniMax M2.5",
            model_name="minimax-m2.5",
            description="MiniMax's latest flagship model with enhanced reasoning and capabilities",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="MiniMax-Text-01",
            model_name="MiniMax-Text-01",
            description="MiniMax's text model with 4M context window",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="abab6.5s-chat",
            model_name="abab6.5s-chat",
            description="Fast and efficient chat model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="abab6.5-chat",
            model_name="abab6.5-chat",
            description="Balanced chat model with strong reasoning",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="abab6-chat",
            model_name="abab6-chat",
            description="Capable general-purpose chat model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="abab5.5s-chat",
            model_name="abab5.5s-chat",
            description="Lightweight fast chat model",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="abab5.5-chat",
            model_name="abab5.5-chat",
            description="Previous generation chat model",
            default_max_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://www.minimax.chat/",
)


QWEN_PRESET = ProviderPreset(
    provider_id="qwen",
    provider_name="Qwen (Alibaba Cloud)",
    description="Alibaba Cloud's Qwen/Tongyi models — leading Chinese open-source LLMs with strong multilingual and reasoning capabilities",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    documentation_url="https://help.aliyun.com/zh/dashscope/",
    models=[
        # Qwen3 Series
        ModelPreset(
            name="Qwen3 235B A22B",
            model_name="qwen3-235b-a22b",
            description="Qwen3's largest MoE model — 235B total / 22B active params, hybrid thinking mode, top-tier reasoning",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 72B",
            model_name="qwen3-72b",
            description="Qwen3 72B dense model — strong coding and instruction following",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 32B",
            model_name="qwen3-32b",
            description="Qwen3 32B — excellent balance of quality and speed",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 14B",
            model_name="qwen3-14b",
            description="Qwen3 14B — efficient mid-size model",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 8B",
            model_name="qwen3-8b",
            description="Qwen3 8B — fast and capable",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 4B",
            model_name="qwen3-4b",
            description="Qwen3 4B — lightweight model for edge and mobile",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen3 1.7B",
            model_name="qwen3-1.7b",
            description="Qwen3 1.7B — ultra-compact model",
            default_max_tokens=4096,
            max_input_tokens=32768,
            max_output_tokens=4096,
            is_open_source=True,
        ),
        # QwQ (Reasoning)
        ModelPreset(
            name="QwQ 32B",
            model_name="qwq-32b",
            description="QwQ-32B — Qwen's advanced reasoning model, strong on math and logic",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        # Qwen2.5 Series
        ModelPreset(
            name="Qwen2.5 72B Instruct",
            model_name="qwen2.5-72b-instruct",
            description="Qwen2.5 72B — flagship instruction model",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen2.5 32B Instruct",
            model_name="qwen2.5-32b-instruct",
            description="Qwen2.5 32B instruction-tuned",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen2.5 14B Instruct",
            model_name="qwen2.5-14b-instruct",
            description="Qwen2.5 14B instruction-tuned",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen2.5 7B Instruct",
            model_name="qwen2.5-7b-instruct",
            description="Qwen2.5 7B instruction-tuned",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        # Qwen2.5 Coder Series
        ModelPreset(
            name="Qwen2.5 Coder 32B Instruct",
            model_name="qwen2.5-coder-32b-instruct",
            description="Qwen2.5 Coder 32B — state-of-the-art code model",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Qwen2.5 Coder 7B Instruct",
            model_name="qwen2.5-coder-7b-instruct",
            description="Qwen2.5 Coder 7B — efficient coding model",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        # Qwen Long
        ModelPreset(
            name="Qwen Long",
            model_name="qwen-long",
            description="Qwen Long — 10M token context window for processing entire codebases and documents",
            default_max_tokens=8192,
            max_input_tokens=10000000,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://dashscope.aliyun.com/. The default API base is compatible with OpenAI SDK.",
)


MISTRAL_PRESET = ProviderPreset(
    provider_id="mistral",
    provider_name="Mistral AI",
    description="Mistral AI's frontier open-weight and proprietary models — strong at coding, reasoning, and multilingual tasks",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.mistral.ai/v1",
    documentation_url="https://docs.mistral.ai/",
    models=[
        ModelPreset(
            name="Mistral Large Latest",
            model_name="mistral-large-latest",
            description="Mistral's most powerful model — top-tier reasoning and instruction following",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Mistral Small Latest",
            model_name="mistral-small-latest",
            description="Efficient Mistral model — great quality-to-cost ratio",
            default_max_tokens=32768,
            max_input_tokens=32768,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Mistral Medium Latest",
            model_name="mistral-medium-latest",
            description="Balanced Mistral model for general tasks",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Codestral Latest",
            model_name="codestral-latest",
            description="Mistral's coding-specialist model — 32K fill-in-the-middle, strong at code completion",
            default_max_tokens=32768,
            max_input_tokens=256000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Devstral Latest",
            model_name="devstral-latest",
            description="Mistral's agentic coding model — optimized for multi-file code editing and software engineering tasks",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Pixtral Large Latest",
            model_name="pixtral-large-latest",
            description="Mistral's frontier multimodal model — strong vision + text reasoning",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Pixtral 12B",
            model_name="pixtral-12b-latest",
            description="Mistral's efficient vision model — 12B multimodal",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Mistral Nemo",
            model_name="open-mistral-nemo",
            description="Mistral Nemo 12B — long context, multilingual, open-weight",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
            is_open_source=True,
        ),
        ModelPreset(
            name="Mistral 7B Instruct",
            model_name="open-mistral-7b",
            description="Mistral 7B — fast and efficient open model",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
            is_open_source=True,
        ),
        ModelPreset(
            name="Mixtral 8x7B Instruct",
            model_name="open-mixtral-8x7b",
            description="Mixtral 8x7B MoE — strong multilingual and code model",
            default_max_tokens=32768,
            max_input_tokens=32768,
            max_output_tokens=32768,
            is_open_source=True,
        ),
        ModelPreset(
            name="Mixtral 8x22B Instruct",
            model_name="open-mixtral-8x22b",
            description="Mixtral 8x22B MoE — Mistral's largest open model",
            default_max_tokens=65536,
            max_input_tokens=65536,
            max_output_tokens=65536,
            is_open_source=True,
        ),
    ],
    setup_instructions="Get your API key from https://console.mistral.ai/api-keys/",
)


XAI_PRESET = ProviderPreset(
    provider_id="xai",
    provider_name="xAI (Grok)",
    description="xAI's Grok models — powerful reasoning and coding models with real-time knowledge",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.x.ai/v1",
    documentation_url="https://docs.x.ai/",
    models=[
        ModelPreset(
            name="Grok 4",
            model_name="grok-4-0709",
            description="xAI's flagship reasoning model — state-of-the-art performance across math, coding, and reasoning benchmarks",
            default_max_tokens=131072,
            max_input_tokens=256000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 4.1 Fast (Reasoning)",
            model_name="grok-4.1-fast-reasoning",
            description="Grok 4.1 Fast — improved reasoning and instruction-following with a 2M token context window",
            default_max_tokens=131072,
            max_input_tokens=2000000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 4.1 Fast (Non-Reasoning)",
            model_name="grok-4.1-fast-non-reasoning",
            description="Grok 4.1 Fast — low-latency mode without extended reasoning, 2M token context window",
            default_max_tokens=131072,
            max_input_tokens=2000000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 4 Fast (Reasoning)",
            model_name="grok-4-fast-reasoning",
            description="Grok 4 Fast — extended reasoning mode with a 2M token context window",
            default_max_tokens=131072,
            max_input_tokens=2000000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 4 Fast (Non-Reasoning)",
            model_name="grok-4-fast-non-reasoning",
            description="Grok 4 Fast — low-latency mode without extended reasoning, 2M token context window",
            default_max_tokens=131072,
            max_input_tokens=2000000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok Code Fast 1",
            model_name="grok-code-fast-1",
            description="Grok Code Fast — purpose-built for agentic coding workflows",
            default_max_tokens=131072,
            max_input_tokens=256000,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 3",
            model_name="grok-3-beta",
            description="xAI's flagship model — frontier reasoning, coding, and analysis",
            default_max_tokens=131072,
            max_input_tokens=131072,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 3 Mini",
            model_name="grok-3-mini-beta",
            description="Grok 3 Mini — fast and efficient reasoning model",
            default_max_tokens=131072,
            max_input_tokens=131072,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 3 Fast",
            model_name="grok-3-fast-beta",
            description="Grok 3 Fast — optimized for low latency",
            default_max_tokens=131072,
            max_input_tokens=131072,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 3 Mini Fast",
            model_name="grok-3-mini-fast-beta",
            description="Grok 3 Mini Fast — smallest and fastest Grok 3",
            default_max_tokens=131072,
            max_input_tokens=131072,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 2",
            model_name="grok-2-1212",
            description="Grok 2 — previous generation flagship",
            default_max_tokens=131072,
            max_input_tokens=131072,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok 2 Vision",
            model_name="grok-2-vision-1212",
            description="Grok 2 Vision — multimodal model with image understanding",
            default_max_tokens=131072,
            max_input_tokens=32768,
            max_output_tokens=131072,
        ),
        ModelPreset(
            name="Grok Vision Beta",
            model_name="grok-vision-beta",
            description="Grok Vision Beta — early vision-capable Grok model",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://console.x.ai/",
)


COHERE_PRESET = ProviderPreset(
    provider_id="cohere",
    provider_name="Cohere",
    description="Cohere's Command models — enterprise-grade RAG and tool-use models",
    requires_api_key=True,
    requires_api_base=False,
    documentation_url="https://docs.cohere.com/",
    models=[
        ModelPreset(
            name="Command A",
            model_name="command-a-03-2025",
            description="Cohere's most capable model — 256K context, strong at RAG and agentic tasks",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Command R+ (Aug 2024)",
            model_name="command-r-plus-08-2024",
            description="Command R+ — latest version, optimized for RAG and multi-step tasks",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Command R+ (Apr 2024)",
            model_name="command-r-plus-04-2024",
            description="Command R+ — original release with strong RAG capability",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Command R (Aug 2024)",
            model_name="command-r-08-2024",
            description="Command R — efficient retrieval-augmented generation model",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Command R7B",
            model_name="command-r7b-12-2024",
            description="Command R7B — compact 7B model for fast inference",
            default_max_tokens=4096,
            max_input_tokens=128000,
            max_output_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://dashboard.cohere.com/api-keys",
)


PERPLEXITY_PRESET = ProviderPreset(
    provider_id="perplexity",
    provider_name="Perplexity AI",
    description="Perplexity's Sonar models — web-search-grounded models with real-time internet access",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.perplexity.ai",
    documentation_url="https://docs.perplexity.ai/",
    models=[
        ModelPreset(
            name="Sonar Pro",
            model_name="sonar-pro",
            description="Sonar Pro — most capable Perplexity model with deep web research",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Sonar",
            model_name="sonar",
            description="Sonar — fast web-grounded model for real-time queries",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Sonar Reasoning Pro",
            model_name="sonar-reasoning-pro",
            description="Sonar Reasoning Pro — deep research with chain-of-thought reasoning",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Sonar Reasoning",
            model_name="sonar-reasoning",
            description="Sonar Reasoning — fast reasoning with web grounding",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Sonar Deep Research",
            model_name="sonar-deep-research",
            description="Sonar Deep Research — multi-step research agent with extensive web search",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://www.perplexity.ai/settings/api",
)


ZHIPU_PRESET = ProviderPreset(
    provider_id="zhipu",
    provider_name="Zhipu AI (GLM)",
    description="Zhipu AI's GLM series — leading Chinese open-source models with strong bilingual and reasoning capabilities",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://open.bigmodel.cn/api/paas/v4",
    documentation_url="https://open.bigmodel.cn/dev/api/",
    models=[
        ModelPreset(
            name="GLM-5.2",
            model_name="glm-5.2",
            description="Zhipu's newest flagship — GLM-5 generation refresh with stronger reasoning, coding, and agentic tool-use",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-5.1",
            model_name="glm-5.1",
            description="GLM-5.1 — incremental GLM-5 release with improved long-context stability",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-5",
            model_name="glm-5",
            description="GLM-5 — Zhipu's next-generation flagship model, successor to GLM-4.6",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-5-Air",
            model_name="glm-5-air",
            description="GLM-5-Air — lightweight, cost-efficient GLM-5 variant for high-throughput workloads",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.6",
            model_name="glm-4.6",
            description="Zhipu's latest flagship model — improved reasoning, coding, and agentic tool-use over GLM-4.5",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.6V",
            model_name="glm-4.6v",
            description="GLM-4.6V — multimodal vision-language flagship model",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5",
            model_name="glm-4.5",
            description="GLM-4.5 — unified reasoning, coding, and agentic model with a hybrid thinking mode",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5-Air",
            model_name="glm-4.5-air",
            description="GLM-4.5 Air — lightweight version optimized for cost and speed",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5-Flash",
            model_name="glm-4.5-flash",
            description="GLM-4.5 Flash — fastest and most cost-efficient GLM-4.5 variant",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5V",
            model_name="glm-4.5v",
            description="GLM-4.5V — multimodal vision-language model built on GLM-4.5",
            default_max_tokens=8192,
            max_input_tokens=64000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4-Plus",
            model_name="glm-4-plus",
            description="Zhipu's most powerful model — enhanced long-context and instruction following",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4-0520",
            model_name="glm-4-0520",
            description="GLM-4 May 2024 release — best at complex reasoning",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4",
            model_name="glm-4",
            description="GLM-4 base — stable general-purpose model",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4-Air",
            model_name="glm-4-air",
            description="GLM-4 Air — high performance at lower cost",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4-AirX",
            model_name="glm-4-airx",
            description="GLM-4 AirX — ultra-fast inference",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4-Flash",
            model_name="glm-4-flash",
            description="GLM-4 Flash — fastest and most cost-efficient GLM model",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-Z1",
            model_name="glm-z1",
            description="GLM-Z1 — Zhipu's deep reasoning model for math and logic",
            default_max_tokens=16384,
            max_input_tokens=32768,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-Z1-Air",
            model_name="glm-z1-air",
            description="GLM-Z1 Air — efficient reasoning model",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-Z1-Flash",
            model_name="glm-z1-flash",
            description="GLM-Z1 Flash — fast reasoning model",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4V",
            model_name="glm-4v",
            description="GLM-4V — multimodal vision-language model",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4V-Plus",
            model_name="glm-4v-plus",
            description="GLM-4V Plus — enhanced vision model with better image understanding",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys",
)


MOONSHOT_PRESET = ProviderPreset(
    provider_id="moonshot",
    provider_name="Moonshot AI (Kimi)",
    description="Moonshot AI's Kimi models — ultra-long context and advanced reasoning, built for enterprise tasks",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.moonshot.cn/v1",
    documentation_url="https://platform.moonshot.cn/docs/",
    models=[
        ModelPreset(
            name="Kimi K2",
            model_name="kimi-k2",
            description="Kimi K2 — Moonshot's latest flagship reasoning model",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Kimi K1.5 Long",
            model_name="kimi-k1-5-64k",
            description="Kimi K1.5 — advanced reasoning model with 64K context",
            default_max_tokens=16384,
            max_input_tokens=65536,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Kimi K1.5",
            model_name="kimi-k1-5-8k",
            description="Kimi K1.5 — reasoning model, 8K context",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Moonshot V1 128K",
            model_name="moonshot-v1-128k",
            description="Moonshot V1 — 128K context window, strong at long document analysis",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Moonshot V1 32K",
            model_name="moonshot-v1-32k",
            description="Moonshot V1 — 32K context, balanced speed and capability",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Moonshot V1 8K",
            model_name="moonshot-v1-8k",
            description="Moonshot V1 — 8K context, fastest Kimi model",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://platform.moonshot.cn/console/api-keys",
)


YI_PRESET = ProviderPreset(
    provider_id="yi",
    provider_name="Yi (零一万物)",
    description="01.AI's Yi models — high-capability bilingual models with strong long-context performance",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.lingyiwanwu.com/v1",
    documentation_url="https://platform.lingyiwanwu.com/docs",
    models=[
        ModelPreset(
            name="Yi Lightning",
            model_name="yi-lightning",
            description="Yi Lightning — 01.AI's fastest and most cost-efficient model",
            default_max_tokens=16384,
            max_input_tokens=16384,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Yi Large",
            model_name="yi-large",
            description="Yi Large — most capable Yi model for complex reasoning",
            default_max_tokens=16384,
            max_input_tokens=32768,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Yi Large Turbo",
            model_name="yi-large-turbo",
            description="Yi Large Turbo — high-quality model optimized for speed",
            default_max_tokens=16384,
            max_input_tokens=16384,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Yi Medium",
            model_name="yi-medium",
            description="Yi Medium — balanced performance and cost",
            default_max_tokens=16384,
            max_input_tokens=16384,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Yi Medium 200K",
            model_name="yi-medium-200k",
            description="Yi Medium with 200K context — ideal for long documents",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Yi Spark",
            model_name="yi-spark",
            description="Yi Spark — lightweight model for high-volume tasks",
            default_max_tokens=8192,
            max_input_tokens=16384,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Yi Vision",
            model_name="yi-vision",
            description="Yi Vision — multimodal model with image understanding",
            default_max_tokens=4096,
            max_input_tokens=4096,
            max_output_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://platform.lingyiwanwu.com/apikeys",
)


BAICHUAN_PRESET = ProviderPreset(
    provider_id="baichuan",
    provider_name="Baichuan Intelligence (百川)",
    description="Baichuan's enterprise-grade Chinese LLMs with strong domain knowledge",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://api.baichuan-ai.com/v1",
    documentation_url="https://platform.baichuan-ai.com/docs/api",
    models=[
        ModelPreset(
            name="Baichuan4 Turbo",
            model_name="Baichuan4-Turbo",
            description="Baichuan4 Turbo — flagship model with strong reasoning and domain knowledge",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Baichuan4 Air",
            model_name="Baichuan4-Air",
            description="Baichuan4 Air — lightweight, fast, and cost-efficient",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Baichuan4",
            model_name="Baichuan4",
            description="Baichuan4 — Baichuan's base flagship model",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Baichuan3 Turbo 128K",
            model_name="Baichuan3-Turbo-128k",
            description="Baichuan3 Turbo with 128K context window",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Baichuan3 Turbo",
            model_name="Baichuan3-Turbo",
            description="Baichuan3 Turbo — efficient previous-generation model",
            default_max_tokens=8192,
            max_input_tokens=32768,
            max_output_tokens=8192,
        ),
    ],
    setup_instructions="Get your API key from https://platform.baichuan-ai.com/console/apikey",
)


GROQ_PRESET = ProviderPreset(
    provider_id="groq",
    provider_name="Groq",
    description="Ultra-fast inference for open-source models using custom LPU hardware. Fastest tokens/sec available.",
    requires_api_key=True,
    default_api_base="https://api.groq.com/openai/v1",
    documentation_url="https://console.groq.com/docs",
    setup_instructions="Get your free API key from https://console.groq.com/keys",
    models=[
        # Llama 4 Series
        ModelPreset(
            name="Llama 4 Maverick",
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
            description="Meta's Llama 4 Maverick 17B MoE — 128 experts, 1M context, best open model on benchmarks",
            default_max_tokens=8192,
            max_input_tokens=1048576,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        ModelPreset(
            name="Llama 4 Scout",
            model_name="meta-llama/llama-4-scout-17b-16e-instruct",
            description="Meta's Llama 4 Scout — 17B MoE, 10M context, fits single GPU",
            default_max_tokens=8192,
            max_input_tokens=10485760,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        # Llama 3.x Series
        ModelPreset(
            name="Llama 3.3 70B",
            model_name="llama-3.3-70b-versatile",
            description="Meta's Llama 3.3 70B — best quality Groq model, great for complex tasks",
            default_max_tokens=32768,
            max_input_tokens=128000,
            max_output_tokens=32768,
            is_open_source=True,
            speed_tier="fast",
        ),
        ModelPreset(
            name="Llama 3.1 8B Instant",
            model_name="llama-3.1-8b-instant",
            description="Llama 3.1 8B — extremely fast, ideal for simple tasks and high-throughput use cases",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        ModelPreset(
            name="Llama 3 70B",
            model_name="llama3-70b-8192",
            description="Meta's Llama 3 70B — strong reasoning and instruction following",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        ModelPreset(
            name="Llama 3 8B",
            model_name="llama3-8b-8192",
            description="Meta's Llama 3 8B — lightweight and blazing fast",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        # Qwen Series
        ModelPreset(
            name="QwQ 32B",
            model_name="qwen-qwq-32b",
            description="Alibaba QwQ-32B — advanced reasoning model, strong at math and coding",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
            is_open_source=True,
            speed_tier="medium",
        ),
        ModelPreset(
            name="Qwen 3 32B",
            model_name="qwen/qwen3-32b",
            description="Alibaba Qwen3 32B — hybrid thinking model, strong reasoning",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
            is_open_source=True,
            speed_tier="medium",
        ),
        # Mistral Series
        ModelPreset(
            name="Mistral Saba 24B",
            model_name="mistral-saba-24b",
            description="Mistral's Arabic and Middle-Eastern optimized 24B model",
            default_max_tokens=32768,
            max_input_tokens=32768,
            max_output_tokens=32768,
            is_open_source=True,
            speed_tier="fast",
        ),
        ModelPreset(
            name="Mixtral 8x7B",
            model_name="mixtral-8x7b-32768",
            description="Mistral's Mixtral 8x7B MoE model — strong multilingual and code capabilities",
            default_max_tokens=32768,
            max_input_tokens=32768,
            max_output_tokens=32768,
            is_open_source=True,
            speed_tier="fast",
        ),
        # Google Series
        ModelPreset(
            name="Gemma 2 9B",
            model_name="gemma2-9b-it",
            description="Google's Gemma 2 9B instruction-tuned — efficient and capable",
            default_max_tokens=8192,
            max_input_tokens=8192,
            max_output_tokens=8192,
            is_open_source=True,
            speed_tier="fast",
        ),
        # DeepSeek Series
        ModelPreset(
            name="DeepSeek R1 Distill Llama 70B",
            model_name="deepseek-r1-distill-llama-70b",
            description="DeepSeek R1 reasoning model distilled to Llama 70B — strong at math and code",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
            is_open_source=True,
            speed_tier="medium",
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 32B",
            model_name="deepseek-r1-distill-qwen-32b",
            description="DeepSeek R1 distilled to Qwen 32B — compact reasoning model",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
            is_open_source=True,
            speed_tier="medium",
        ),
    ],
)


OPENROUTER_PRESET = ProviderPreset(
    provider_id="openrouter",
    provider_name="OpenRouter",
    description="Unified API for 100+ models from OpenAI, Anthropic, Google, Meta and more",
    requires_api_key=True,
    requires_api_base=False,
    default_api_base="https://openrouter.ai/api/v1",
    documentation_url="https://openrouter.ai/docs",
    models=[
        # OpenAI Models
        ModelPreset(
            name="GPT-4o",
            model_name="openai/gpt-4o",
            description="OpenAI's flagship multimodal model",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4o Mini",
            model_name="openai/gpt-4o-mini",
            description="Affordable and fast GPT-4o variant",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4 Turbo",
            model_name="openai/gpt-4-turbo",
            description="GPT-4 Turbo with 128K context",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="O1 Preview",
            model_name="openai/o1-preview",
            description="OpenAI's reasoning model",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="O1 Mini",
            model_name="openai/o1-mini",
            description="Faster, cheaper O1 variant",
            default_max_tokens=65536,
        ),
        # Anthropic Models — Claude 5 (latest)
        ModelPreset(
            name="Claude Opus 5",
            model_name="anthropic/claude-opus-5",
            description="Anthropic's next-generation flagship model — highest intelligence",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 5",
            model_name="anthropic/claude-sonnet-5",
            description="Best balance of intelligence and speed — Claude 5",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 5",
            model_name="anthropic/claude-haiku-5",
            description="Claude Haiku 5 — fastest Claude model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude Opus 4.7",
            model_name="anthropic/claude-opus-4-7",
            description="Anthropic's most powerful model — highest intelligence",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 4.7",
            model_name="anthropic/claude-sonnet-4-7",
            description="Best balance of intelligence and speed — Claude 4.7",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.7",
            model_name="anthropic/claude-haiku-4-7",
            description="Claude Haiku 4.7 — fastest Claude model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Anthropic Models — Claude 4.6
        ModelPreset(
            name="Claude Opus 4.6",
            model_name="anthropic/claude-opus-4-6",
            description="Anthropic Claude Opus 4.6 — powerful and capable",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 4.6",
            model_name="anthropic/claude-sonnet-4-6",
            description="Claude Sonnet 4.6 — fast and intelligent",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.6",
            model_name="anthropic/claude-haiku-4-6",
            description="Claude Haiku 4.6 — fast and efficient",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Anthropic Models — Claude 4.5
        ModelPreset(
            name="Claude Opus 4.5",
            model_name="anthropic/claude-opus-4-5",
            description="Anthropic's Claude Opus 4.5 — powerful and capable",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 4.5",
            model_name="anthropic/claude-sonnet-4-5",
            description="Claude Sonnet 4.5 — fast and intelligent",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=64000,
        ),
        ModelPreset(
            name="Claude Haiku 4.5",
            model_name="anthropic/claude-haiku-4-5",
            description="Claude Haiku 4.5 — fastest Claude model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Anthropic Models — Claude 4.1
        ModelPreset(
            name="Claude Opus 4.1",
            model_name="anthropic/claude-opus-4-1",
            description="Claude Opus 4.1 — advanced reasoning",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 4.1",
            model_name="anthropic/claude-sonnet-4-1",
            description="Claude Sonnet 4.1 — balanced intelligence",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4.1",
            model_name="anthropic/claude-haiku-4-1",
            description="Claude Haiku 4.1 — fast and efficient",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Anthropic Models — Claude 4
        ModelPreset(
            name="Claude Opus 4",
            model_name="anthropic/claude-opus-4",
            description="Claude Opus 4 — next-generation flagship",
            default_max_tokens=32768,
            max_input_tokens=200000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Claude Sonnet 4",
            model_name="anthropic/claude-sonnet-4",
            description="Claude Sonnet 4 — balanced model",
            default_max_tokens=16384,
            max_input_tokens=200000,
            max_output_tokens=128000,
        ),
        ModelPreset(
            name="Claude Haiku 4",
            model_name="anthropic/claude-haiku-4",
            description="Claude Haiku 4 — fast and efficient",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Anthropic Models — Claude 3.x
        ModelPreset(
            name="Claude 3.7 Sonnet",
            model_name="anthropic/claude-3.7-sonnet",
            description="Claude 3.7 Sonnet with extended thinking",
            default_max_tokens=16000,
            max_input_tokens=200000,
            max_output_tokens=64000,
        ),
        ModelPreset(
            name="Claude 3.5 Sonnet",
            model_name="anthropic/claude-3.5-sonnet",
            description="Claude 3.5 Sonnet — high intelligence",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku",
            model_name="anthropic/claude-3.5-haiku",
            description="Fast and efficient Claude 3.5 model",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3 Opus",
            model_name="anthropic/claude-3-opus",
            description="Most powerful Claude 3 model",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Haiku",
            model_name="anthropic/claude-3-haiku",
            description="Fastest Claude 3 model",
            default_max_tokens=4096,
            max_input_tokens=200000,
            max_output_tokens=4096,
        ),
        # OpenAI Models — GPT-5.x (latest)
        ModelPreset(
            name="GPT-5.5 Pro",
            model_name="openai/gpt-5.5-pro",
            description="OpenAI's most powerful GPT-5.5 model",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.5",
            model_name="openai/gpt-5.5",
            description="OpenAI GPT-5.5",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.4 Pro",
            model_name="openai/gpt-5.4-pro",
            description="OpenAI GPT-5.4 Pro",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.4",
            model_name="openai/gpt-5.4",
            description="OpenAI GPT-5.4",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.3 Instant",
            model_name="openai/gpt-5.3-instant",
            description="OpenAI GPT-5.3 Instant — fast responses",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-5.2 Pro",
            model_name="openai/gpt-5.2-pro",
            description="OpenAI GPT-5.2 Pro",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.2",
            model_name="openai/gpt-5.2",
            description="OpenAI GPT-5.2",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5",
            model_name="openai/gpt-5",
            description="OpenAI GPT-5 base model",
            default_max_tokens=32768,
        ),
        # OpenAI Models — GPT-4.x
        ModelPreset(
            name="GPT-4.1",
            model_name="openai/gpt-4.1",
            description="OpenAI GPT-4.1 — latest flagship",
            default_max_tokens=32768,
            max_input_tokens=1047576,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="GPT-4.1 Mini",
            model_name="openai/gpt-4.1-mini",
            description="Affordable and fast GPT-4.1 variant",
            default_max_tokens=16384,
            max_input_tokens=1047576,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4.1 Nano",
            model_name="openai/gpt-4.1-nano",
            description="Fastest GPT-4.1 variant",
            default_max_tokens=8192,
            max_input_tokens=1047576,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="O4 Mini",
            model_name="openai/o4-mini",
            description="OpenAI's fast reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="O3",
            model_name="openai/o3",
            description="OpenAI's most powerful reasoning model",
            default_max_tokens=100000,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="O3 Mini",
            model_name="openai/o3-mini",
            description="Fast and efficient reasoning model",
            default_max_tokens=65536,
            max_input_tokens=200000,
            max_output_tokens=100000,
        ),
        ModelPreset(
            name="GPT-4o",
            model_name="openai/gpt-4o",
            description="OpenAI's flagship multimodal model",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4o Mini",
            model_name="openai/gpt-4o-mini",
            description="Affordable and fast GPT-4o variant",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
        ),
        # Google Models — Gemini 3.x (latest)
        ModelPreset(
            name="Gemini 3.1 Pro Preview",
            model_name="google/gemini-3.1-pro-preview",
            description="Google's latest Gemini 3.1 Pro preview",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 3 Pro",
            model_name="google/gemini-3-pro",
            description="Google Gemini 3 Pro — next-generation flagship",
            default_max_tokens=32768,
            max_input_tokens=1000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 3 Flash",
            model_name="google/gemini-3-flash",
            description="Google Gemini 3 Flash — fast multimodal model",
            default_max_tokens=16384,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        # Google Models — Gemini 2.x
        ModelPreset(
            name="Gemini 2.5 Pro",
            model_name="google/gemini-2.5-pro-preview",
            description="Google's most capable Gemini model with deep thinking",
            default_max_tokens=16384,
            max_input_tokens=1048576,
            max_output_tokens=65536,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash",
            model_name="google/gemini-2.5-flash-preview",
            description="Google Gemini 2.5 Flash — fast and capable",
            default_max_tokens=16384,
            max_input_tokens=1048576,
            max_output_tokens=65536,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash",
            model_name="google/gemini-2.0-flash-001",
            description="Google's fast multimodal model",
            default_max_tokens=8192,
            max_input_tokens=1048576,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash Thinking",
            model_name="google/gemini-2.0-flash-thinking-exp:free",
            description="Gemini 2.0 Flash with thinking/reasoning",
            default_max_tokens=8192,
            max_input_tokens=1048576,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Gemini 1.5 Pro",
            model_name="google/gemini-pro-1.5",
            description="Google's Gemini 1.5 Pro",
            default_max_tokens=8192,
            max_input_tokens=2097152,
            max_output_tokens=8192,
        ),
        # xAI Grok Models
        ModelPreset(
            name="Grok 4",
            model_name="x-ai/grok-4",
            description="xAI's Grok 4 — flagship reasoning model",
            default_max_tokens=32768,
            max_input_tokens=256000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Grok 4 Fast",
            model_name="x-ai/grok-4-fast",
            description="xAI's Grok 4 Fast — low-latency model with a 2M token context window",
            default_max_tokens=32768,
            max_input_tokens=2000000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Grok Code Fast 1",
            model_name="x-ai/grok-code-fast-1",
            description="xAI's Grok Code Fast — purpose-built for agentic coding workflows",
            default_max_tokens=32768,
            max_input_tokens=256000,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Grok 3",
            model_name="x-ai/grok-3-beta",
            description="xAI's Grok 3 — frontier reasoning model",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Grok 3 Mini",
            model_name="x-ai/grok-3-mini-beta",
            description="xAI's fast and efficient Grok 3 Mini",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Grok 2",
            model_name="x-ai/grok-2-1212",
            description="xAI's Grok 2 model",
            default_max_tokens=16384,
            max_input_tokens=131072,
            max_output_tokens=16384,
        ),
        # Meta Llama Models — latest
        ModelPreset(
            name="Llama 4 Scout",
            model_name="meta-llama/llama-4-scout",
            description="Meta's Llama 4 Scout — efficient multimodal model",
            default_max_tokens=16384,
            max_input_tokens=10000000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Llama 4 Maverick",
            model_name="meta-llama/llama-4-maverick",
            description="Meta's Llama 4 Maverick — powerful multimodal model",
            default_max_tokens=16384,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Llama 3.3 70B",
            model_name="meta-llama/llama-3.3-70b-instruct",
            description="Meta's Llama 3.3 70B — latest generation",
            default_max_tokens=8192,
            max_input_tokens=131072,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Llama 3.1 405B",
            model_name="meta-llama/llama-3.1-405b-instruct",
            description="Meta's largest open model",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Llama 3.1 70B",
            model_name="meta-llama/llama-3.1-70b-instruct",
            description="Meta's Llama 3.1 70B",
            default_max_tokens=4096,
        ),
        # Mistral Models — latest
        ModelPreset(
            name="Mistral Large 2",
            model_name="mistralai/mistral-large-2411",
            description="Mistral's most capable model",
            default_max_tokens=32768,
            max_input_tokens=131072,
            max_output_tokens=32768,
        ),
        ModelPreset(
            name="Mistral Small 3.1",
            model_name="mistralai/mistral-small-3.1-24b-instruct",
            description="Mistral Small 3.1 — efficient and fast",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Devstral",
            model_name="mistralai/devstral-small-2505",
            description="Mistral's coding-optimized model",
            default_max_tokens=16384,
            max_input_tokens=128000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Mixtral 8x22B",
            model_name="mistralai/mixtral-8x22b-instruct",
            description="Large mixture of experts",
            default_max_tokens=65536,
        ),
        # DeepSeek Models — latest
        ModelPreset(
            name="DeepSeek V4 Pro",
            model_name="deepseek/deepseek-v4-pro",
            description="DeepSeek V4 Pro — current flagship DeepSeek model",
            default_max_tokens=8192,
            max_input_tokens=1000000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="DeepSeek V4 Flash",
            model_name="deepseek/deepseek-v4-flash",
            description="DeepSeek V4 Flash — current fast DeepSeek model with thinking/non-thinking modes",
            default_max_tokens=8192,
            max_input_tokens=1000000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek V3",
            model_name="deepseek/deepseek-chat-v3-5",
            description="DeepSeek V3 — latest version",
            default_max_tokens=8192,
            max_input_tokens=163840,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1",
            model_name="deepseek/deepseek-r1",
            description="DeepSeek's reasoning model",
            default_max_tokens=8192,
            max_input_tokens=163840,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="DeepSeek R1 Distill Qwen 32B",
            model_name="deepseek/deepseek-r1-distill-qwen-32b",
            description="DeepSeek R1 distilled into Qwen 32B",
            default_max_tokens=8192,
        ),
        # Qwen Models — latest
        ModelPreset(
            name="Qwen3 235B",
            model_name="qwen/qwen3-235b-a22b",
            description="Qwen3's largest model with hybrid thinking",
            default_max_tokens=8192,
            max_input_tokens=40960,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Qwen3 30B",
            model_name="qwen/qwen3-30b-a3b",
            description="Qwen3 30B efficient MoE model",
            default_max_tokens=8192,
            max_input_tokens=40960,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Qwen 2.5 72B",
            model_name="qwen/qwen-2.5-72b-instruct",
            description="Alibaba's Qwen 2.5 72B",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Qwen 2.5 Coder 32B",
            model_name="qwen/qwen-2.5-coder-32b-instruct",
            description="Qwen optimized for coding",
            default_max_tokens=8192,
        ),
        # Cohere Models
        ModelPreset(
            name="Command A",
            model_name="cohere/command-a-03-2025",
            description="Cohere's latest flagship model",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Command R+",
            model_name="cohere/command-r-plus",
            description="Cohere's most capable model",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Command R",
            model_name="cohere/command-r",
            description="Balanced Cohere model",
            default_max_tokens=4096,
        ),
        # Perplexity Models — latest
        ModelPreset(
            name="Perplexity Sonar Pro",
            model_name="perplexity/sonar-pro",
            description="Perplexity's advanced model with web search",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Perplexity Sonar",
            model_name="perplexity/sonar",
            description="Perplexity's fast model with web search",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="Perplexity Sonar Reasoning",
            model_name="perplexity/sonar-reasoning-pro",
            description="Perplexity's reasoning model with web search",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        # Microsoft Phi Models
        ModelPreset(
            name="Phi-4",
            model_name="microsoft/phi-4",
            description="Microsoft's Phi-4 — powerful small model",
            default_max_tokens=16384,
            max_input_tokens=16384,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="Phi-4 Mini",
            model_name="microsoft/phi-4-mini-instruct",
            description="Microsoft's compact Phi-4 model",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        # MiniMax Models
        ModelPreset(
            name="MiniMax M2.5",
            model_name="minimax/minimax-m2.5",
            description="MiniMax's latest flagship model",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="MiniMax-Text-01",
            model_name="minimax/minimax-text-01",
            description="MiniMax's text model with 4M context window",
            default_max_tokens=4096,
        ),
    ],
    setup_instructions="Get your API key from https://openrouter.ai/keys",
)


VLLM_PRESET = ProviderPreset(
    provider_id="vllm",
    provider_name="vLLM",
    description="High-throughput inference server",
    requires_api_key=False,
    requires_api_base=True,
    documentation_url="https://docs.vllm.ai/",
    models=[
        ModelPreset(
            name="Custom vLLM Model",
            model_name="deployed-model",
            description="Model deployed on vLLM server (use actual model name)",
            default_max_tokens=2048,
        ),
    ],
    setup_instructions="Deploy vLLM server and use its OpenAI-compatible endpoint",
)


LITELLM_PRESET = ProviderPreset(
    provider_id="litellm",
    provider_name="LiteLLM",
    description="Unified API for 100+ LLM providers",
    requires_api_key=True,
    requires_api_base=True,
    documentation_url="https://docs.litellm.ai/",
    models=[
        # OpenAI Models via LiteLLM - GPT-5 Series
        ModelPreset(
            name="GPT-5.5 Pro",
            model_name="gpt-5.5-pro",
            description="OpenAI GPT-5.5 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.5", model_name="gpt-5.5", description="OpenAI GPT-5.5 via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="GPT-5.4 Pro",
            model_name="gpt-5.4-pro",
            description="OpenAI GPT-5.4 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.4", model_name="gpt-5.4", description="OpenAI GPT-5.4 via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="GPT-5.3 Instant",
            model_name="gpt-5.3-instant",
            description="OpenAI GPT-5.3 Instant via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-5.3 Instant Mini",
            model_name="gpt-5.3-instant-mini",
            description="OpenAI GPT-5.3 Instant Mini via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-5.3 Codex",
            model_name="gpt-5.3-codex",
            description="OpenAI GPT-5.3 Codex via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.3", model_name="gpt-5.3", description="OpenAI GPT-5.3 via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="GPT-5.2 Pro",
            model_name="gpt-5.2-pro",
            description="OpenAI GPT-5.2 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.2", model_name="gpt-5.2", description="OpenAI GPT-5.2 via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="GPT-5.1 Thinking",
            model_name="gpt-5.1-thinking",
            description="OpenAI GPT-5.1 Thinking via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.1 Instant",
            model_name="gpt-5.1-instant",
            description="OpenAI GPT-5.1 Instant via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-5.1 Codex",
            model_name="gpt-5.1-codex",
            description="OpenAI GPT-5.1 Codex via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5.1", model_name="gpt-5.1", description="OpenAI GPT-5.1 via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="GPT-5 Codex",
            model_name="gpt-5-codex",
            description="OpenAI GPT-5 Codex via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="GPT-5 nano",
            model_name="gpt-5-nano",
            description="OpenAI GPT-5 nano via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-5 mini",
            model_name="gpt-5-mini",
            description="OpenAI GPT-5 mini via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(name="GPT-5", model_name="gpt-5", description="OpenAI GPT-5 via LiteLLM", default_max_tokens=32768),
        # OpenAI - GPT-4 Series
        ModelPreset(
            name="GPT-4.5", model_name="gpt-4.5", description="OpenAI GPT-4.5 via LiteLLM", default_max_tokens=16384
        ),
        ModelPreset(
            name="GPT-4.1 nano",
            model_name="gpt-4.1-nano",
            description="OpenAI GPT-4.1 nano via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="GPT-4.1 mini",
            model_name="gpt-4.1-mini",
            description="OpenAI GPT-4.1 mini via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4.1", model_name="gpt-4.1", description="OpenAI GPT-4.1 via LiteLLM", default_max_tokens=16384
        ),
        ModelPreset(
            name="GPT-4o", model_name="gpt-4o", description="OpenAI GPT-4o via LiteLLM", default_max_tokens=16384
        ),
        ModelPreset(
            name="GPT-4o Mini",
            model_name="gpt-4o-mini",
            description="OpenAI GPT-4o Mini via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="GPT-4 Turbo",
            model_name="gpt-4-turbo",
            description="OpenAI GPT-4 Turbo via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="GPT-4 Turbo Preview",
            model_name="gpt-4-turbo-preview",
            description="OpenAI GPT-4 Turbo Preview via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(name="GPT-4", model_name="gpt-4", description="OpenAI GPT-4 via LiteLLM", default_max_tokens=8192),
        ModelPreset(
            name="GPT-4 32K",
            model_name="gpt-4-32k",
            description="OpenAI GPT-4 32K via LiteLLM",
            default_max_tokens=32768,
        ),
        # OpenAI - GPT-3.5 Series
        ModelPreset(
            name="GPT-3.5 Turbo",
            model_name="gpt-3.5-turbo",
            description="OpenAI GPT-3.5 Turbo via LiteLLM",
            default_max_tokens=16385,
        ),
        ModelPreset(
            name="GPT-3.5 Turbo 16K",
            model_name="gpt-3.5-turbo-16k",
            description="OpenAI GPT-3.5 Turbo 16K via LiteLLM",
            default_max_tokens=16385,
        ),
        # OpenAI - O-Series
        ModelPreset(
            name="O4 Mini", model_name="o4-mini", description="OpenAI O4 Mini via LiteLLM", default_max_tokens=65536
        ),
        ModelPreset(
            name="O3 Pro", model_name="o3-pro", description="OpenAI O3 Pro via LiteLLM", default_max_tokens=65536
        ),
        ModelPreset(
            name="O3 Mini", model_name="o3-mini", description="OpenAI O3 Mini via LiteLLM", default_max_tokens=65536
        ),
        ModelPreset(name="O3", model_name="o3", description="OpenAI O3 via LiteLLM", default_max_tokens=65536),
        ModelPreset(
            name="O1 Pro", model_name="o1-pro", description="OpenAI O1 Pro via LiteLLM", default_max_tokens=32768
        ),
        ModelPreset(
            name="O1 Preview",
            model_name="o1-preview",
            description="OpenAI O1 Preview via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="O1 Mini", model_name="o1-mini", description="OpenAI O1 Mini via LiteLLM", default_max_tokens=65536
        ),
        ModelPreset(name="O1", model_name="o1", description="OpenAI O1 via LiteLLM", default_max_tokens=32768),
        # Anthropic Claude Models via LiteLLM - Claude 5 Series
        ModelPreset(
            name="Claude Opus 5",
            model_name="claude-opus-5",
            description="Anthropic's next-generation flagship model via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 5",
            model_name="claude-sonnet-5",
            description="Anthropic Claude Sonnet 5 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 5",
            model_name="claude-haiku-5",
            description="Anthropic Claude Haiku 5 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic Claude Models via LiteLLM - Claude 4.7 Series
        ModelPreset(
            name="Claude Opus 4.7",
            model_name="claude-opus-4-7",
            description="Anthropic Claude Opus 4.7 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.7",
            model_name="claude-sonnet-4-7",
            description="Anthropic Claude Sonnet 4.7 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4.7",
            model_name="claude-haiku-4-7",
            description="Anthropic Claude Haiku 4.7 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 4.6 Series
        ModelPreset(
            name="Claude Opus 4.6",
            model_name="claude-opus-4-6",
            description="Anthropic Claude Opus 4.6 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.6",
            model_name="claude-sonnet-4-6",
            description="Anthropic Claude Sonnet 4.6 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4.6",
            model_name="claude-haiku-4-6",
            description="Anthropic Claude Haiku 4.6 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 4.5 Series
        ModelPreset(
            name="Claude Opus 4.5",
            model_name="claude-opus-4-5",
            description="Anthropic Claude Opus 4.5 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.5",
            model_name="claude-sonnet-4-5",
            description="Anthropic Claude Sonnet 4.5 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4.5",
            model_name="claude-haiku-4-5",
            description="Anthropic Claude Haiku 4.5 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 4.1 Series
        ModelPreset(
            name="Claude Opus 4.1",
            model_name="claude-opus-4-1",
            description="Anthropic Claude Opus 4.1 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4.1",
            model_name="claude-sonnet-4-1",
            description="Anthropic Claude Sonnet 4.1 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4.1",
            model_name="claude-haiku-4-1",
            description="Anthropic Claude Haiku 4.1 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 4 Series
        ModelPreset(
            name="Claude Opus 4",
            model_name="claude-opus-4",
            description="Anthropic Claude Opus 4 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Sonnet 4",
            model_name="claude-sonnet-4",
            description="Anthropic Claude Sonnet 4 via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Claude Haiku 4",
            model_name="claude-haiku-4",
            description="Anthropic Claude Haiku 4 via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 3.7 Series
        ModelPreset(
            name="Claude 3.7 Sonnet (Latest)",
            model_name="claude-3-7-sonnet-latest",
            description="Anthropic Claude 3.7 Sonnet Latest via LiteLLM (Recommended)",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 3.5 Series
        ModelPreset(
            name="Claude 3.5 Sonnet (Latest)",
            model_name="claude-3-5-sonnet-latest",
            description="Anthropic Claude 3.5 Sonnet Latest via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Claude 3.5 Haiku (Latest)",
            model_name="claude-3-5-haiku-latest",
            description="Anthropic Claude 3.5 Haiku Latest via LiteLLM",
            default_max_tokens=8192,
        ),
        # Anthropic - Claude 3 Series
        ModelPreset(
            name="Claude 3 Opus",
            model_name="claude-3-opus-20240229",
            description="Anthropic Claude 3 Opus via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Sonnet",
            model_name="claude-3-sonnet-20240229",
            description="Anthropic Claude 3 Sonnet via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Claude 3 Haiku",
            model_name="claude-3-haiku-20240307",
            description="Anthropic Claude 3 Haiku via LiteLLM",
            default_max_tokens=4096,
        ),
        # Anthropic - Claude 2 Series
        ModelPreset(
            name="Claude 2.1",
            model_name="claude-2.1",
            description="Anthropic Claude 2.1 via LiteLLM",
            default_max_tokens=200000,
        ),
        ModelPreset(
            name="Claude 2.0",
            model_name="claude-2.0",
            description="Anthropic Claude 2.0 via LiteLLM",
            default_max_tokens=100000,
        ),
        # Google Gemini Models via LiteLLM - Gemini 3 Series
        ModelPreset(
            name="Gemini 3 Pro",
            model_name="gemini-3-pro",
            description="Google Gemini 3 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        # Google - Gemini 2.5 Series
        ModelPreset(
            name="Gemini 2.5 Pro Preview",
            model_name="gemini-2.5-pro-preview-06-05",
            description="Google Gemini 2.5 Pro Preview via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 2.5 Pro",
            model_name="gemini-2.5-pro",
            description="Google Gemini 2.5 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash-Lite",
            model_name="gemini-2.5-flash-lite",
            description="Google Gemini 2.5 Flash-Lite via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.5 Flash",
            model_name="gemini-2.5-flash",
            description="Google Gemini 2.5 Flash via LiteLLM",
            default_max_tokens=16384,
        ),
        # Google - Gemini 2.0 Series
        ModelPreset(
            name="Gemini 2.0 Flash Thinking",
            model_name="gemini-2.0-flash-thinking",
            description="Google Gemini 2.0 Flash Thinking via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash-Lite",
            model_name="gemini-2.0-flash-lite",
            description="Google Gemini 2.0 Flash-Lite via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 2.0 Flash",
            model_name="gemini-2.0-flash",
            description="Google Gemini 2.0 Flash via LiteLLM",
            default_max_tokens=16384,
        ),
        # Google - Gemini 1.5 Series
        ModelPreset(
            name="Gemini 1.5 Pro",
            model_name="gemini-1.5-pro",
            description="Google Gemini 1.5 Pro via LiteLLM",
            default_max_tokens=32768,
        ),
        ModelPreset(
            name="Gemini 1.5 Flash 8B",
            model_name="gemini-1.5-flash-8b",
            description="Google Gemini 1.5 Flash 8B via LiteLLM",
            default_max_tokens=16384,
        ),
        ModelPreset(
            name="Gemini 1.5 Flash",
            model_name="gemini-1.5-flash",
            description="Google Gemini 1.5 Flash via LiteLLM",
            default_max_tokens=16384,
        ),
        # Google - Gemini 1.0 Series
        ModelPreset(
            name="Gemini 1.0 Pro",
            model_name="gemini-1.0-pro",
            description="Google Gemini 1.0 Pro via LiteLLM",
            default_max_tokens=32760,
        ),
        # Google - Gemma Series
        ModelPreset(
            name="Gemma 3 27B",
            model_name="gemma-3-27b",
            description="Google Gemma 3 27B via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 12B",
            model_name="gemma-3-12b",
            description="Google Gemma 3 12B via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 4B",
            model_name="gemma-3-4b",
            description="Google Gemma 3 4B via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 3 1B",
            model_name="gemma-3-1b",
            description="Google Gemma 3 1B via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Gemma 2 27B",
            model_name="gemma-2-27b",
            description="Google Gemma 2 27B via LiteLLM",
            default_max_tokens=8192,
        ),
        ModelPreset(
            name="Gemma 2 9B",
            model_name="gemma-2-9b",
            description="Google Gemma 2 9B via LiteLLM",
            default_max_tokens=8192,
        ),
        # DeepSeek Models via LiteLLM
        ModelPreset(
            name="DeepSeek V4 Pro",
            model_name="deepseek/deepseek-v4-pro",
            description="DeepSeek V4 Pro flagship model via LiteLLM",
            default_max_tokens=32768,
            max_input_tokens=1000000,
        ),
        ModelPreset(
            name="DeepSeek V4 Flash",
            model_name="deepseek/deepseek-chat",
            description="DeepSeek V4 Flash (chat alias) via LiteLLM",
            default_max_tokens=32768,
            max_input_tokens=1000000,
        ),
        ModelPreset(
            name="DeepSeek Reasoner",
            model_name="deepseek/deepseek-reasoner",
            description="DeepSeek Reasoner (R1 alias) via LiteLLM",
            default_max_tokens=32768,
            max_input_tokens=1000000,
        ),
        ModelPreset(
            name="DeepSeek R1",
            model_name="deepseek/deepseek-r1",
            description="DeepSeek R1 reasoning model via LiteLLM",
            default_max_tokens=32768,
            max_input_tokens=163840,
        ),
        ModelPreset(
            name="DeepSeek V3",
            model_name="deepseek/deepseek-chat-v3-5",
            description="DeepSeek V3 latest via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=163840,
        ),
        # Zhipu GLM Models via LiteLLM
        ModelPreset(
            name="GLM-5.2",
            model_name="glm-5.2",
            description="Zhipu's newest flagship GLM-5.2 via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-5",
            model_name="glm-5",
            description="Zhipu GLM-5 flagship model via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=256000,
            max_output_tokens=16384,
        ),
        ModelPreset(
            name="GLM-4.6",
            model_name="glm-4.6",
            description="Zhipu GLM-4.6 via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=200000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5",
            model_name="glm-4.5",
            description="Zhipu GLM-4.5 via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        ModelPreset(
            name="GLM-4.5-Air",
            model_name="glm-4.5-air",
            description="Zhipu GLM-4.5 Air (cost-efficient) via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=128000,
            max_output_tokens=8192,
        ),
        # xAI Grok Models via LiteLLM
        ModelPreset(
            name="Grok 4",
            model_name="grok-4-0709",
            description="xAI Grok 4 flagship model via LiteLLM",
            default_max_tokens=16384,
            max_input_tokens=256000,
        ),
        ModelPreset(
            name="Grok 4.1 Fast Reasoning",
            model_name="grok-4.1-fast-reasoning",
            description="xAI Grok 4.1 Fast (reasoning) via LiteLLM",
            default_max_tokens=16384,
            max_input_tokens=2000000,
        ),
        ModelPreset(
            name="Grok Code Fast 1",
            model_name="grok-code-fast-1",
            description="xAI Grok Code Fast 1 via LiteLLM",
            default_max_tokens=16384,
            max_input_tokens=256000,
        ),
        ModelPreset(
            name="Grok 3",
            model_name="grok-3-beta",
            description="xAI Grok 3 via LiteLLM",
            default_max_tokens=8192,
            max_input_tokens=131072,
        ),
        # Other Popular Models
        ModelPreset(
            name="Llama 3 70B",
            model_name="together_ai/meta-llama/Llama-3-70b-chat-hf",
            description="Meta Llama 3 70B via LiteLLM",
            default_max_tokens=4096,
        ),
        ModelPreset(
            name="Mixtral 8x7B",
            model_name="together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1",
            description="Mistral Mixtral 8x7B via LiteLLM",
            default_max_tokens=32768,
        ),
        # ── Image Generation Models ───────────────────────────────────────────
        ModelPreset(
            name="GPT Image 1",
            model_name="gpt-image-1",
            description="OpenAI GPT Image 1 via LiteLLM proxy. Supports prompt-based image generation through the OpenAI Images API.",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="GPT Image 2",
            model_name="gpt-image-2",
            description="OpenAI GPT Image 2 via LiteLLM proxy. Supports square (1024x1024), portrait (1024x1536), landscape (1536x1024).",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="DALL-E 3",
            model_name="dall-e-3",
            description="OpenAI DALL-E 3 via LiteLLM proxy. High-quality photorealistic image generation.",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="Grok 2 Image",
            model_name="grok-2-image",
            description="xAI Grok 2 Image (Aurora) via LiteLLM proxy. Creative and photorealistic image generation.",
            tags=["image_generation"],
        ),
        ModelPreset(
            name="Imagen 3",
            model_name="imagen-3.0-generate-002",
            description="Google Imagen 3 via LiteLLM proxy. State-of-the-art image generation.",
            tags=["image_generation"],
        ),
        # ── Video Generation Models ───────────────────────────────────────────
        ModelPreset(
            name="Veo 3",
            model_name="vertex_ai/veo-3.0-generate-001",
            description="Google Veo 3 via LiteLLM proxy on Vertex AI. High-fidelity text-to-video generation.",
            tags=["video_generation"],
        ),
        ModelPreset(
            name="Veo 3 Fast",
            model_name="vertex_ai/veo-3.0-fast-generate-001",
            description="Google Veo 3 Fast via LiteLLM proxy on Vertex AI. Faster text-to-video generation.",
            tags=["video_generation"],
        ),
        ModelPreset(
            name="Veo 2",
            model_name="vertex_ai/veo-2.0-generate-001",
            description="Google Veo 2 via LiteLLM proxy on Vertex AI. Text-to-video and image-to-video generation.",
            tags=["video_generation"],
        ),
    ],
    setup_instructions="Configure LiteLLM proxy and set appropriate model names. LiteLLM supports 100+ providers through a unified API.",
)


# All provider presets
ALL_PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    # Western commercial providers
    "openai": OPENAI_PRESET,
    "anthropic": ANTHROPIC_PRESET,
    "gemini": GEMINI_PRESET,
    "mistral": MISTRAL_PRESET,
    "xai": XAI_PRESET,
    "cohere": COHERE_PRESET,
    "perplexity": PERPLEXITY_PRESET,
    # Chinese providers
    "deepseek": DEEPSEEK_PRESET,
    "qwen": QWEN_PRESET,
    "zhipu": ZHIPU_PRESET,
    "moonshot": MOONSHOT_PRESET,
    "yi": YI_PRESET,
    "baichuan": BAICHUAN_PRESET,
    "minimax": MINIMAX_PRESET,
    # Aggregators / routers
    "openrouter": OPENROUTER_PRESET,
    "groq": GROQ_PRESET,
    # Cloud platforms
    "bedrock": AWS_BEDROCK_PRESET,
    "vertex_ai": VERTEX_AI_PRESET,
    "azure_openai": AZURE_OPENAI_PRESET,
    # Self-hosted / local
    "ollama": OLLAMA_PRESET,
    "lm_studio": LM_STUDIO_PRESET,
    "vllm": VLLM_PRESET,
    "litellm": LITELLM_PRESET,
    # Other hosted inference
    "together_ai": TOGETHER_AI_PRESET,
    "replicate": REPLICATE_PRESET,
    "huggingface": HUGGINGFACE_PRESET,
}


@cache
def _get_model_comparison_data() -> dict[str, dict[str, Any]]:
    """Load the comparison metadata only when model enrichment is requested."""
    from .llm_provider_comparison_data import MODEL_COMPARISON_DATA

    return MODEL_COMPARISON_DATA


def enrich_model_with_comparison(model: ModelPreset) -> ModelPreset:
    """Return a copy of a ModelPreset enriched with comparison metadata if available."""
    data = _get_model_comparison_data().get(model.model_name)
    if not data:
        return model
    return ModelPreset(
        name=model.name,
        model_name=model.model_name,
        description=model.description,
        default_temperature=model.default_temperature,
        default_max_tokens=model.default_max_tokens,
        default_top_p=model.default_top_p,
        additional_params=model.additional_params,
        max_input_tokens=model.max_input_tokens,
        max_output_tokens=model.max_output_tokens,
        cost_input_per_1m=data.get("cost_input_per_1m"),
        cost_output_per_1m=data.get("cost_output_per_1m"),
        is_open_source=data.get("is_open_source", False),
        quality_score=data.get("quality_score"),
        speed_tier=data.get("speed_tier"),
        tags=data.get("tags", []),
    )


@lru_cache(maxsize=1)
def _get_all_models_for_comparison_cached() -> tuple[dict[str, Any], ...]:
    """Build and cache the comparison dataset."""
    result = []
    for provider in ALL_PROVIDER_PRESETS.values():
        for model in provider.models or []:
            enriched = enrich_model_with_comparison(model)
            result.append(
                {
                    "provider_id": provider.provider_id,
                    "provider_name": provider.provider_name,
                    "name": enriched.name,
                    "model_name": enriched.model_name,
                    "description": enriched.description,
                    "max_input_tokens": enriched.max_input_tokens,
                    "max_output_tokens": enriched.max_output_tokens,
                    "default_max_tokens": enriched.default_max_tokens,
                    "cost_input_per_1m": enriched.cost_input_per_1m,
                    "cost_output_per_1m": enriched.cost_output_per_1m,
                    "is_open_source": enriched.is_open_source,
                    "quality_score": enriched.quality_score,
                    "speed_tier": enriched.speed_tier,
                    "tags": enriched.tags,
                    "requires_api_key": provider.requires_api_key,
                }
            )
    return tuple(result)


def get_all_models_for_comparison() -> list[dict[str, Any]]:
    """Return a flat list of all models across all providers, enriched with comparison metadata."""
    return list(_get_all_models_for_comparison_cached())


@lru_cache(maxsize=1)
def _get_all_providers_cached() -> tuple[ProviderPreset, ...]:
    return tuple(ALL_PROVIDER_PRESETS.values())


def get_provider_preset(provider_id: str) -> ProviderPreset | None:
    """Get provider preset by ID."""
    return ALL_PROVIDER_PRESETS.get(provider_id)


def get_all_providers() -> list[ProviderPreset]:
    """Get all available provider presets."""
    return list(_get_all_providers_cached())


@cache
def _get_provider_models_cached(provider_id: str) -> tuple[ModelPreset, ...]:
    preset = get_provider_preset(provider_id)
    return tuple(preset.models or ()) if preset else ()


def get_provider_models(provider_id: str) -> list[ModelPreset]:
    """Get all models for a specific provider."""
    return list(_get_provider_models_cached(provider_id))


def get_model_preset(provider_id: str, model_name: str) -> ModelPreset | None:
    """Get specific model preset."""
    models = get_provider_models(provider_id)
    for model in models:
        if model.model_name == model_name:
            return model
    return None


def create_config_from_preset(
    provider_id: str,
    model_name: str,
    name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Create a configuration dictionary from a preset.

    Args:
        provider_id: Provider identifier
        model_name: Model name
        name: Display name for the configuration
        api_key: API key (if required)
        api_base: API base URL (if required)
        **kwargs: Additional parameters to override defaults

    Returns:
        Configuration dictionary ready for AgentLLMConfig creation
    """
    provider_preset = get_provider_preset(provider_id)
    model_preset = get_model_preset(provider_id, model_name)

    if not provider_preset:
        raise ValueError(f"Unknown provider: {provider_id}")

    config = {
        "name": name or f"{provider_preset.provider_name} - {model_name}",
        "provider": provider_id,
        "model_name": model_name,
        "api_key": api_key or "not-required",
        "temperature": kwargs.get("temperature", model_preset.default_temperature if model_preset else 0.7),
    }

    # Add optional parameters
    if api_base or provider_preset.default_api_base:
        config["api_base"] = api_base or provider_preset.default_api_base

    if model_preset:
        if model_preset.default_max_tokens:
            config["max_tokens"] = kwargs.get("max_tokens", model_preset.default_max_tokens)
        if model_preset.default_top_p:
            config["top_p"] = kwargs.get("top_p", model_preset.default_top_p)
        if model_preset.additional_params:
            config["additional_params"] = {**model_preset.additional_params, **kwargs.get("additional_params", {})}

    # Add any additional kwargs
    for key, value in kwargs.items():
        if key not in config and key not in ["temperature", "max_tokens", "top_p", "additional_params"]:
            config[key] = value

    return config
