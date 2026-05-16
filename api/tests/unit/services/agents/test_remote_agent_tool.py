from src.config import settings
from src.services.agents.internal_tools.remote_agent_tool import (
    _is_url_safe,
    _rewrite_app_base_to_internal,
)


def test_app_base_trust_requires_exact_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_base_url", "https://app.synkora.test")

    assert _is_url_safe("https://app.synkora.test/api/a2a/agents/agent_1")
    assert not _is_url_safe("https://app.synkora.test@127.0.0.1:5001/api/a2a/agents/agent_1")
    assert not _is_url_safe("https://app.synkora.test.evil.example/api/a2a/agents/agent_1")


def test_app_base_internal_rewrite_preserves_only_path_query(monkeypatch):
    app_base = "https://app.synkora.test"
    monkeypatch.setattr(settings, "app_base_url", app_base)

    assert (
        _rewrite_app_base_to_internal(
            "https://app.synkora.test/api/a2a/agents/agent_1?x=1",
            app_base,
        )
        == "http://synkora-api:5001/api/a2a/agents/agent_1?x=1"
    )

    malicious = "https://app.synkora.test@127.0.0.1:5001/api/a2a/agents/agent_1"
    assert _rewrite_app_base_to_internal(malicious, app_base) == malicious
