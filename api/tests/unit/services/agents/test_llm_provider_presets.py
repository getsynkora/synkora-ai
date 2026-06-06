from src.services.agents.llm_provider_presets import get_all_providers, get_provider_models, get_provider_preset


def test_deepseek_provider_is_exported():
    provider = get_provider_preset("deepseek")

    assert provider is not None
    assert provider.provider_name == "DeepSeek"
    assert provider.default_api_base == "https://api.deepseek.com"


def test_deepseek_provider_exposes_latest_official_models():
    model_names = {model.model_name for model in get_provider_models("deepseek")}

    assert "deepseek-v4-flash" in model_names
    assert "deepseek-v4-pro" in model_names
    assert "deepseek-chat" in model_names
    assert "deepseek-reasoner" in model_names


def test_deepseek_provider_is_returned_in_provider_list():
    provider_ids = {provider.provider_id for provider in get_all_providers()}

    assert "deepseek" in provider_ids
