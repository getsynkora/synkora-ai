"""Unit tests for AgentRegistry."""

from unittest.mock import MagicMock, patch

import pytest

import src.services.agents.registry as registry_mod
from src.services.agents.registry import AgentRegistry, get_registry


def _make_agent(name: str) -> MagicMock:
    agent = MagicMock()
    agent.config.name = name
    agent.config.description = f"Agent {name}"
    agent.config.system_prompt = None
    agent.get_stats.return_value = {"requests": 0}
    return agent


@pytest.mark.unit
class TestAgentRegistryRegister:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register_adds_agent(self):
        agent = _make_agent("agent-a")
        self.registry.register(agent)
        assert "agent-a" in self.registry

    def test_register_duplicate_raises_value_error(self):
        agent = _make_agent("dup")
        self.registry.register(agent)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(agent)

    def test_register_different_agents_both_stored(self):
        self.registry.register(_make_agent("a"))
        self.registry.register(_make_agent("b"))
        assert len(self.registry) == 2

    def test_register_syncs_to_redis_when_available(self):
        mock_redis = MagicMock()
        with patch("src.services.agents.registry._get_redis_registry", return_value=mock_redis):
            self.registry.register(_make_agent("synced-agent"))
        mock_redis.register_runtime.assert_called_once()
        _, kwargs = mock_redis.register_runtime.call_args
        assert kwargs["tenant_id"] == ""
        assert kwargs["agent_name"] == "synced-agent"
        assert kwargs["runtime_id"] == registry_mod.DEFAULT_RUNTIME_ID

    def test_register_tolerates_redis_failure(self):
        mock_redis = MagicMock()
        mock_redis.register_runtime.side_effect = RuntimeError("Redis down")
        with patch("src.services.agents.registry._get_redis_registry", return_value=mock_redis):
            # Should not raise
            self.registry.register(_make_agent("tolerant"))
        assert "tolerant" in self.registry

    def test_register_works_without_redis(self):
        with patch("src.services.agents.registry._get_redis_registry", return_value=None):
            self.registry.register(_make_agent("no-redis"))
        assert "no-redis" in self.registry


@pytest.mark.unit
class TestAgentRegistryUnregister:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_unregister_removes_agent(self):
        self.registry.register(_make_agent("to-remove"))
        self.registry.unregister("to-remove")
        assert "to-remove" not in self.registry

    def test_unregister_missing_raises_key_error(self):
        with pytest.raises(KeyError, match="not found"):
            self.registry.unregister("ghost")

    def test_unregister_calls_redis_unregister(self):
        self.registry.register(_make_agent("redis-agent"))
        mock_redis = MagicMock()
        with patch("src.services.agents.registry._get_redis_registry", return_value=mock_redis):
            self.registry.unregister("redis-agent")
        mock_redis.unregister_runtime.assert_called_once_with(
            tenant_id="",
            agent_name="redis-agent",
            runtime_id=registry_mod.DEFAULT_RUNTIME_ID,
        )

    def test_unregister_tolerates_redis_failure(self):
        self.registry.register(_make_agent("fragile"))
        mock_redis = MagicMock()
        mock_redis.unregister_runtime.side_effect = RuntimeError("boom")
        with patch("src.services.agents.registry._get_redis_registry", return_value=mock_redis):
            self.registry.unregister("fragile")
        assert "fragile" not in self.registry


@pytest.mark.unit
class TestAgentRegistryGet:
    def setup_method(self):
        self.registry = AgentRegistry()
        self.agent = _make_agent("finder")
        self.registry.register(self.agent)

    def test_get_returns_registered_agent(self):
        result = self.registry.get("finder")
        assert result is self.agent

    def test_get_returns_none_for_unknown(self):
        assert self.registry.get("nobody") is None

    def test_get_config_returns_config(self):
        result = self.registry.get_config("finder")
        assert result is self.agent.config

    def test_get_config_returns_none_for_unknown(self):
        assert self.registry.get_config("nobody") is None


@pytest.mark.unit
class TestAgentRegistryListAndStats:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_list_agents_empty(self):
        assert self.registry.list_agents() == []

    def test_list_agents_returns_names(self):
        self.registry.register(_make_agent("x"))
        self.registry.register(_make_agent("y"))
        assert set(self.registry.list_agents()) == {"x", "y"}

    def test_get_all_stats_calls_get_stats(self):
        agent = _make_agent("stat-agent")
        self.registry.register(agent)
        stats = self.registry.get_all_stats()
        assert "stat-agent" in stats
        agent.get_stats.assert_called_once()

    def test_get_all_stats_includes_runtime_label_for_non_default_runtime(self):
        agent = _make_agent("stat-agent")
        self.registry.register(agent, tenant_id="tenant-1", runtime_id="config-2")
        stats = self.registry.get_all_stats()
        assert "tenant-1:stat-agent:config-2" in stats
        agent.get_stats.assert_called_once()

    def test_get_all_stats_empty_registry(self):
        assert self.registry.get_all_stats() == {}


@pytest.mark.unit
class TestAgentRegistryBulkOps:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_reset_all_calls_reset_on_each(self):
        agent_a = _make_agent("a")
        agent_b = _make_agent("b")
        self.registry.register(agent_a)
        self.registry.register(agent_b)
        self.registry.reset_all()
        agent_a.reset.assert_called_once()
        agent_b.reset.assert_called_once()

    def test_clear_empties_registry(self):
        self.registry.register(_make_agent("x"))
        self.registry.clear()
        assert len(self.registry) == 0

    def test_clear_removes_both_agents_and_configs(self):
        self.registry.register(_make_agent("c"))
        self.registry.clear()
        assert self.registry.get("c") is None
        assert self.registry.get_config("c") is None


@pytest.mark.unit
class TestAgentRegistryDunderMethods:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_len_reflects_agent_count(self):
        assert len(self.registry) == 0
        self.registry.register(_make_agent("a"))
        assert len(self.registry) == 1
        self.registry.register(_make_agent("b"))
        assert len(self.registry) == 2

    def test_contains_true_for_registered(self):
        self.registry.register(_make_agent("here"))
        assert "here" in self.registry

    def test_contains_false_for_unregistered(self):
        assert "absent" not in self.registry

    def test_repr_includes_count(self):
        self.registry.register(_make_agent("r"))
        assert "1" in repr(self.registry)


@pytest.mark.unit
class TestGetRegistrySingleton:
    def test_returns_same_instance(self):
        registry_mod._global_registry = None
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2
        registry_mod._global_registry = None

    def test_returns_agent_registry_instance(self):
        registry_mod._global_registry = None
        r = get_registry()
        assert isinstance(r, AgentRegistry)
        registry_mod._global_registry = None
