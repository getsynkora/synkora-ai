"""Tests for agents/index.py controller."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


@pytest.fixture
def mock_db():
    """Create mock async database session."""
    db = AsyncMock()
    db.add = Mock()
    db.delete = AsyncMock()  # Must be AsyncMock since controller uses await db.delete()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


def setup_db_execute_mock(mock_db, return_value):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


@pytest.fixture
def mock_tenant_id():
    """Create mock tenant ID."""
    return uuid4()


@pytest.fixture
def sample_agent(mock_tenant_id):
    """Create a sample agent mock whose tenant_id matches the test tenant."""
    agent = Mock()
    agent.id = uuid4()
    agent.tenant_id = mock_tenant_id
    agent.agent_name = "test-agent"
    agent.slug = "test-agent"
    agent.agent_type = "llm"
    agent.description = "Test agent description"
    agent.avatar = "s3://bucket/avatar.png"
    agent.system_prompt = "You are a helpful assistant"
    # Use real dicts instead of Mock objects for dict-like attributes
    agent.llm_config = {"provider": "openai", "model": "gpt-4", "api_key": "test-key"}
    agent.tools_config = {"tools": []}
    agent.observability_config = {}
    agent.agent_metadata = {}
    agent.suggestion_prompts = ["Hello", "Help me"]
    agent.status = "ACTIVE"
    agent.is_public = False
    agent.category = "productivity"
    agent.tags = ["test", "demo"]
    agent.voice_enabled = False
    agent.voice_config = {}
    agent.workflow_type = None
    agent.workflow_config = None
    agent.execution_count = 100
    agent.success_count = 95
    agent.likes_count = 50
    agent.dislikes_count = 5
    agent.usage_count = 200
    agent.created_at = datetime.now(UTC)
    agent.updated_at = datetime.now(UTC)
    return agent


@pytest.fixture
def sample_create_request():
    """Create sample agent creation request."""
    request = Mock()
    request.agent_type = "llm"
    request.api_key = "test-api-key"
    request.is_public = False
    request.category = "productivity"
    request.tags = ["test"]
    # These must be None or valid UUID strings, not Mock objects
    request.role_id = None
    request.human_contact_id = None

    config = Mock()
    config.name = "new-agent"
    config.description = "New agent"
    config.avatar = None
    config.system_prompt = "You are helpful"
    config.suggestion_prompts = []
    config.tools = []

    llm_config = Mock()
    llm_config.model_dump = Mock(return_value={"provider": "openai", "model": "gpt-4"})
    config.llm_config = llm_config

    request.config = config
    return request


class TestConvertS3UriToPresignedUrl:
    """Tests for convert_s3_uri_to_presigned_url helper."""

    def test_returns_none_for_none_input(self):
        """Test None input returns None."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        assert convert_s3_uri_to_presigned_url(None) is None

    def test_returns_empty_for_empty_input(self):
        """Test empty string input returns empty string."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        assert convert_s3_uri_to_presigned_url("") == ""

    def test_returns_http_url_unchanged(self):
        """Test HTTP URLs pass through unchanged."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        http_url = "http://example.com/image.png"
        assert convert_s3_uri_to_presigned_url(http_url) == http_url

    def test_returns_https_url_unchanged(self):
        """Test HTTPS URLs pass through unchanged."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        https_url = "https://example.com/image.png"
        assert convert_s3_uri_to_presigned_url(https_url) == https_url

    @patch("src.controllers.agents.index.S3StorageService")
    def test_converts_s3_uri_to_presigned_url(self, mock_storage):
        """Test S3 URI is converted to presigned URL."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        mock_service = Mock()
        mock_service.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned"
        mock_storage.return_value = mock_service

        result = convert_s3_uri_to_presigned_url("s3://bucket/key.png")

        assert result == "https://s3.amazonaws.com/presigned"
        mock_service.generate_presigned_url.assert_called_once()

    @patch("src.controllers.agents.index.S3StorageService")
    def test_converts_path_to_presigned_url(self, mock_storage):
        """Test key path is converted to presigned URL."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        mock_service = Mock()
        mock_service.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned"
        mock_storage.return_value = mock_service

        result = convert_s3_uri_to_presigned_url("uploads/avatar.png")

        assert result == "https://s3.amazonaws.com/presigned"

    @patch("src.controllers.agents.index._storage_service", None)
    @patch("src.controllers.agents.index.S3StorageService")
    def test_returns_original_on_exception(self, mock_storage):
        """Test original URI returned on S3 exception."""
        from src.controllers.agents.index import convert_s3_uri_to_presigned_url

        mock_storage.side_effect = Exception("S3 error")

        s3_uri = "s3://bucket/key.png"
        result = convert_s3_uri_to_presigned_url(s3_uri)

        assert result == s3_uri


class TestCreateAgent:
    """Tests for create_agent endpoint."""

    @pytest.mark.asyncio
    async def test_create_agent_success(self, mock_db, mock_tenant_id, sample_create_request):
        """Test successful agent creation."""
        from src.controllers.agents.index import create_agent

        with (
            patch("src.controllers.agents.index.agent_manager") as mock_manager,
            patch("src.services.billing.PlanRestrictionService") as mock_restriction,
            patch("src.services.billing.PlanRestrictionError", Exception),
            patch("src.controllers.agents.index.Agent") as mock_agent_class,
            patch("src.controllers.agents.index.get_agent_cache") as mock_cache,
        ):
            mock_manager.create_agent = AsyncMock(return_value=Mock())
            mock_restriction.return_value.enforce_agent_limit = AsyncMock(return_value=None)

            mock_cache_instance = MagicMock()
            mock_cache_instance.invalidate_agents_list = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            mock_agent_instance = Mock()
            mock_agent_instance.id = uuid4()
            mock_agent_class.return_value = mock_agent_instance

            mock_account = Mock()
            mock_account.id = uuid4()

            result = await create_agent(
                request=sample_create_request,
                tenant_id=mock_tenant_id,
                current_account=mock_account,
                db=mock_db,
            )

            assert result.success is True
            assert "created successfully" in result.message
            # add() is called twice: once for Agent, once for AgentLLMConfig
            assert mock_db.add.call_count >= 1
            # commit() is called twice: once for Agent, once for AgentLLMConfig
            assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_create_agent_unknown_type(self, mock_db, mock_tenant_id, sample_create_request):
        """Test agent creation with unknown type."""
        sample_create_request.agent_type = "unknown"

        # Import billing module and patch it
        import src.services.billing as billing_module

        original_service = getattr(billing_module, "PlanRestrictionService", None)
        original_error = getattr(billing_module, "PlanRestrictionError", None)

        try:
            mock_restriction = Mock()
            mock_restriction.enforce_agent_limit = AsyncMock()
            billing_module.PlanRestrictionService = Mock(return_value=mock_restriction)
            billing_module.PlanRestrictionError = Exception

            from src.controllers.agents.index import create_agent

            with pytest.raises(HTTPException) as exc_info:
                await create_agent(request=sample_create_request, tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 400
            assert "Unknown agent type" in exc_info.value.detail
        finally:
            if original_service:
                billing_module.PlanRestrictionService = original_service
            if original_error:
                billing_module.PlanRestrictionError = original_error

    @pytest.mark.asyncio
    async def test_create_agent_plan_restriction(self, mock_db, mock_tenant_id, sample_create_request):
        """Test agent creation blocked by plan restriction."""

        # Create a custom exception class for PlanRestrictionError
        class MockPlanRestrictionError(Exception):
            pass

        # Import billing module and patch it
        import src.services.billing as billing_module

        original_service = getattr(billing_module, "PlanRestrictionService", None)
        original_error = getattr(billing_module, "PlanRestrictionError", None)

        try:
            billing_module.PlanRestrictionError = MockPlanRestrictionError
            mock_restriction_instance = Mock()
            mock_restriction_instance.enforce_agent_limit = AsyncMock(
                side_effect=MockPlanRestrictionError("Agent limit reached")
            )
            billing_module.PlanRestrictionService = Mock(return_value=mock_restriction_instance)

            from src.controllers.agents.index import create_agent

            with pytest.raises(HTTPException) as exc_info:
                await create_agent(request=sample_create_request, tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 403
        finally:
            if original_service:
                billing_module.PlanRestrictionService = original_service
            if original_error:
                billing_module.PlanRestrictionError = original_error


class TestExecuteAgent:
    """Tests for execute_agent endpoint."""

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_agent_success(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent execution."""
        from src.controllers.agents.index import execute_agent

        mock_manager.execute_agent = AsyncMock(return_value={"status": "success", "output": "Hello!"})

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        request = Mock()
        request.agent_name = "test-agent"
        request.input_data = {"message": "Hi"}

        result = await execute_agent(request, tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True
        assert "executed" in result.message

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_agent_not_found(self, mock_manager, mock_db, mock_tenant_id):
        """Test execution of non-existent agent."""
        from src.controllers.agents.index import execute_agent

        # Mock db.execute to return None (agent not found)
        setup_db_execute_mock(mock_db, None)

        request = Mock()
        request.agent_name = "nonexistent"
        request.input_data = {}

        with pytest.raises(HTTPException) as exc_info:
            await execute_agent(request, tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_agent_exception(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test execution error handling."""
        from src.controllers.agents.index import execute_agent

        mock_manager.execute_agent = AsyncMock(side_effect=Exception("Execution error"))

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        request = Mock()
        request.agent_name = "test-agent"
        request.input_data = {}

        with pytest.raises(HTTPException) as exc_info:
            await execute_agent(request, tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 500


class TestExecuteWorkflow:
    """Tests for execute_workflow endpoint."""

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_workflow_success(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test successful workflow execution."""
        from src.controllers.agents.index import execute_workflow

        mock_manager.execute_workflow = AsyncMock(return_value={"status": "success"})

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        # Create workflow step mock
        step = Mock()
        step.agent_name = "test-agent"

        request = Mock()
        request.workflow_config = Mock()
        request.workflow_config.name = "test-workflow"
        request.workflow_config.steps = [step]
        request.input_data = {}

        result = await execute_workflow(request, tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_workflow_partial_success(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test workflow with partial success."""
        from src.controllers.agents.index import execute_workflow

        mock_manager.execute_workflow = AsyncMock(return_value={"status": "partial_success"})

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        # Create workflow step mock
        step = Mock()
        step.agent_name = "test-agent"

        request = Mock()
        request.workflow_config = Mock()
        request.workflow_config.name = "test-workflow"
        request.workflow_config.steps = [step]
        request.input_data = {}

        result = await execute_workflow(request, tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True  # partial_success is still considered success

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_execute_workflow_exception(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test workflow execution error."""
        from src.controllers.agents.index import execute_workflow

        mock_manager.execute_workflow = AsyncMock(side_effect=Exception("Workflow error"))

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        # Create workflow step mock
        step = Mock()
        step.agent_name = "test-agent"

        request = Mock()
        request.workflow_config = Mock()
        request.workflow_config.name = "test-workflow"
        request.workflow_config.steps = [step]
        request.input_data = {}

        with pytest.raises(HTTPException) as exc_info:
            await execute_workflow(request, tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 500


class TestListAgents:
    """Tests for list_agents endpoint."""

    def _setup_list_agents_mocks(self, mock_db, sample_agents=None):
        """Helper to set up mocks for list_agents endpoint.

        The controller makes multiple db.execute() calls with select():
        1. Count query - returns scalar
        2. Agents query - returns scalars().all()
        3. Sub-agent counts - returns all()
        4. Sub-agents data - returns scalars().all()
        5. Sub-agent IDs - returns all()
        """
        if sample_agents is None:
            sample_agents = []

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1

            # First call: count query
            if call_count[0] == 1:
                mock_result.scalar.return_value = len(sample_agents)
            # Second call: agents list query
            elif call_count[0] == 2:
                mock_result.scalars.return_value.all.return_value = sample_agents
            # Remaining calls: sub-agent queries - return empty
            else:
                mock_result.all.return_value = []
                mock_result.scalars.return_value.all.return_value = []

            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    @pytest.mark.asyncio
    async def test_list_agents_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent listing."""
        from src.controllers.agents.index import list_agents

        with (
            patch("src.controllers.agents.index.agent_manager") as mock_manager,
            patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url", return_value="https://url.com"),
            patch("src.controllers.agents.index.get_agent_cache") as mock_cache,
        ):
            mock_manager.registry = {}
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_agents_list = AsyncMock(return_value=None)
            mock_cache_instance.set_agents_list = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            # Set up mocks for multiple db.execute() calls
            self._setup_list_agents_mocks(mock_db, [sample_agent])

            result = await list_agents(page=1, page_size=10, tenant_id=mock_tenant_id, db=mock_db)

            assert result.success is True
            assert "agents" in result.data
            assert "pagination" in result.data

    @pytest.mark.asyncio
    async def test_list_agents_pagination_normalization(self, mock_db, mock_tenant_id):
        """Test pagination parameter normalization."""
        from src.controllers.agents.index import list_agents

        with (
            patch("src.controllers.agents.index.agent_manager") as mock_manager,
            patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url", return_value="https://url.com"),
            patch("src.controllers.agents.index.get_agent_cache") as mock_cache,
        ):
            mock_manager.registry = {}
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_agents_list = AsyncMock(return_value=None)
            mock_cache_instance.set_agents_list = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            # Set up mocks for multiple db.execute() calls
            self._setup_list_agents_mocks(mock_db, [])

            # Test negative page defaults to 1
            result = await list_agents(page=-1, page_size=10, tenant_id=mock_tenant_id, db=mock_db)
            assert result.data["pagination"]["page"] == 1

            # Reset side_effect for the next call
            self._setup_list_agents_mocks(mock_db, [])

            # Test page_size capped at 100
            result = await list_agents(page=1, page_size=200, tenant_id=mock_tenant_id, db=mock_db)
            assert result.data["pagination"]["page_size"] == 100

    @pytest.mark.asyncio
    async def test_list_agents_exception(self, mock_db, mock_tenant_id):
        """Test listing error handling."""
        from src.controllers.agents.index import list_agents

        with patch("src.controllers.agents.index.get_agent_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_agents_list = AsyncMock(return_value=None)
            mock_cache.return_value = mock_cache_instance

            mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

            with pytest.raises(HTTPException) as exc_info:
                await list_agents(page=1, page_size=10, tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 500


class TestGetAgent:
    """Tests for get_agent endpoint."""

    @pytest.mark.asyncio
    async def test_get_agent_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent retrieval."""
        from src.controllers.agents.index import get_agent

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        with patch("src.controllers.agents.index.agent_manager") as mock_manager:
            mock_manager.registry = MagicMock()
            mock_manager.registry.contains.return_value = False

            with patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url") as mock_convert:
                mock_convert.return_value = "https://presigned-url.com/avatar.png"

                result = await get_agent(agent_slug="test-agent", tenant_id=mock_tenant_id, db=mock_db)

                assert result.success is True
                assert result.data["agent_name"] == "test-agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_db, mock_tenant_id):
        """Test getting non-existent agent."""
        from src.controllers.agents.index import get_agent

        # Mock db.execute to return None
        setup_db_execute_mock(mock_db, None)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent(agent_slug="nonexistent", tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_with_stats(self, mock_db, mock_tenant_id, sample_agent):
        """Test getting agent with runtime stats."""
        from src.controllers.agents.index import get_agent

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        with patch("src.controllers.agents.index.agent_manager") as mock_manager:
            mock_manager.registry = MagicMock()
            mock_manager.registry.contains.return_value = True
            mock_manager.get_agent_stats.return_value = {"executions": 50}

            with patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url"):
                result = await get_agent(agent_slug="test-agent", tenant_id=mock_tenant_id, db=mock_db)

                assert "stats" in result.data


class TestGetAgentStats:
    """Tests for get_agent_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_agent_stats_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful stats retrieval."""
        from src.controllers.agents.index import get_agent_stats

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        # Mock success_rate property
        sample_agent.success_rate = 0.95

        with patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url"):
            result = await get_agent_stats(agent_slug="test-agent", tenant_id=mock_tenant_id, db=mock_db)

            assert result.success is True
            assert result.data["execution_count"] == 100
            assert result.data["successful_executions"] == 95

    @pytest.mark.asyncio
    async def test_get_agent_stats_not_found(self, mock_db, mock_tenant_id):
        """Test stats for non-existent agent."""
        from src.controllers.agents.index import get_agent_stats

        # Mock db.execute to return None
        setup_db_execute_mock(mock_db, None)

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_stats(agent_slug="nonexistent", tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 404


class TestGetAllStats:
    """Tests for get_all_stats endpoint."""

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_get_all_stats_success(self, mock_manager, mock_db, mock_tenant_id):
        """Test successful all stats retrieval."""
        from src.controllers.agents.index import get_all_stats

        mock_manager.get_all_stats.return_value = {"agent1": {"executions": 50}, "agent2": {"executions": 30}}

        # Mock db.execute to return agent names for the tenant
        mock_result = MagicMock()
        mock_result.all.return_value = [("agent1",), ("agent2",)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_all_stats(tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_get_all_stats_exception(self, mock_manager, mock_db, mock_tenant_id):
        """Test all stats error handling."""
        from src.controllers.agents.index import get_all_stats

        # Mock execute to throw an exception
        mock_db.execute = AsyncMock(side_effect=Exception("Stats error"))

        with pytest.raises(HTTPException) as exc_info:
            await get_all_stats(tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 500


class TestUpdateAgent:
    """Tests for update_agent endpoint."""

    @pytest.mark.asyncio
    async def test_update_agent_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent update."""
        from src.controllers.agents.index import update_agent

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        request = Mock()
        request.description = "Updated description"
        request.avatar = None
        request.system_prompt = None
        request.llm_config = None
        request.tools_config = None
        request.observability_config = None
        request.suggestion_prompts = None
        request.status = None
        request.is_public = None
        request.category = None
        request.tags = None
        request.voice_enabled = None
        request.voice_config = None
        request.agent_metadata = None
        request.workflow_type = None
        request.workflow_config = None
        # These must be None or valid UUID strings, not Mock objects
        request.role_id = None
        request.human_contact_id = None
        request.routing_mode = None
        request.routing_config = None
        request.name = None
        request.execution_backend = None
        request.transfer_scope = None

        with (
            patch("src.controllers.agents.index.agent_manager") as mock_manager,
            patch("src.controllers.agents.index.get_agent_cache") as mock_cache,
            patch("src.controllers.agents.index.convert_s3_uri_to_presigned_url", return_value="https://url.com"),
        ):
            mock_manager.registry = MagicMock()
            mock_manager.registry.contains.return_value = False

            mock_cache_instance = Mock()
            mock_cache_instance.invalidate_agent = AsyncMock()
            mock_cache_instance.invalidate_agents_list = AsyncMock()
            mock_cache.return_value = mock_cache_instance

            result = await update_agent(agent_slug="test-agent", request=request, tenant_id=mock_tenant_id, db=mock_db)

            assert result.success is True
            assert "updated successfully" in result.message
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_agent_not_found(self, mock_db, mock_tenant_id):
        """Test updating non-existent agent."""
        from src.controllers.agents.index import update_agent

        # Mock db.execute to return None
        setup_db_execute_mock(mock_db, None)

        request = Mock()
        request.description = "Updated"

        with pytest.raises(HTTPException) as exc_info:
            await update_agent(agent_slug="nonexistent", request=request, tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 404


class TestDeleteAgent:
    """Tests for delete_agent endpoint."""

    @pytest.mark.asyncio
    async def test_delete_agent_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent deletion."""
        from src.controllers.agents.index import delete_agent

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        with patch("src.controllers.agents.index.agent_manager") as mock_manager:
            mock_manager.delete_agent = AsyncMock()

            result = await delete_agent(agent_slug="test-agent", tenant_id=mock_tenant_id, db=mock_db)

            assert result.success is True
            mock_db.delete.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_agent_not_found_in_memory(self, mock_db, mock_tenant_id):
        """Test deletion when agent not in memory."""
        from src.controllers.agents.index import delete_agent

        # Mock db.execute to return None
        setup_db_execute_mock(mock_db, None)

        with patch("src.controllers.agents.index.agent_manager") as mock_manager:
            mock_manager.delete_agent = AsyncMock(side_effect=KeyError("Not found"))

            with pytest.raises(HTTPException) as exc_info:
                await delete_agent(agent_slug="nonexistent", tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 404


class TestResetAgent:
    """Tests for reset_agent endpoint."""

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_reset_agent_success(self, mock_manager, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent reset."""
        from src.controllers.agents.index import reset_agent

        mock_manager.reset_agent = AsyncMock()

        # Mock db.execute to return the sample agent
        setup_db_execute_mock(mock_db, sample_agent)

        result = await reset_agent(agent_slug="test-agent", tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True
        mock_manager.reset_agent.assert_called_once_with("test-agent", str(mock_tenant_id))

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_reset_agent_not_found(self, mock_manager, mock_db, mock_tenant_id):
        """Test resetting non-existent agent."""
        from src.controllers.agents.index import reset_agent

        # Mock db.execute to return None
        setup_db_execute_mock(mock_db, None)

        with pytest.raises(HTTPException) as exc_info:
            await reset_agent(agent_slug="nonexistent", tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 404


class TestResetAllAgents:
    """Tests for reset_all_agents endpoint."""

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_reset_all_agents_success(self, mock_manager, mock_db, mock_tenant_id):
        """Test successful reset of all agents."""
        from src.controllers.agents.index import reset_all_agents

        mock_manager.reset_agent = AsyncMock()

        # Mock db.execute to return list of agent names for the tenant
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [Mock(agent_name="test-agent")]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await reset_all_agents(tenant_id=mock_tenant_id, db=mock_db)

        assert result.success is True

    @pytest.mark.asyncio
    @patch("src.controllers.agents.index.agent_manager")
    async def test_reset_all_agents_exception(self, mock_manager, mock_db, mock_tenant_id):
        """Test reset all error handling."""
        from src.controllers.agents.index import reset_all_agents

        # Mock execute to throw an exception
        mock_db.execute = AsyncMock(side_effect=Exception("Reset error"))

        with pytest.raises(HTTPException) as exc_info:
            await reset_all_agents(tenant_id=mock_tenant_id, db=mock_db)

        assert exc_info.value.status_code == 500


class TestListAgentCategories:
    """Tests for list_agent_categories endpoint."""

    @pytest.mark.asyncio
    async def test_list_categories_success(self, mock_db):
        """Test successful category listing."""
        from src.controllers.agents.index import list_agent_categories

        # Mock db.execute to return categories
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("productivity", 5),
            ("development", 3),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await list_agent_categories(db=mock_db)

        assert result.success is True
        assert len(result.data["categories"]) == 2

    @pytest.mark.asyncio
    async def test_list_categories_empty(self, mock_db):
        """Test listing with no categories."""
        from src.controllers.agents.index import list_agent_categories

        # Mock db.execute to return empty categories
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await list_agent_categories(db=mock_db)

        assert result.success is True
        assert len(result.data["categories"]) == 0

    @pytest.mark.asyncio
    async def test_list_categories_exception(self, mock_db):
        """Test category listing error handling."""
        from src.controllers.agents.index import list_agent_categories

        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(HTTPException) as exc_info:
            await list_agent_categories(db=mock_db)

        assert exc_info.value.status_code == 500


class TestCloneAgent:
    """Tests for clone_agent endpoint."""

    @pytest.mark.asyncio
    async def test_clone_agent_success(self, mock_db, mock_tenant_id, sample_agent):
        """Test successful agent cloning."""
        # Track db.execute calls to return different results
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            # First call: source agent query
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_agent
            # Second call: check existing agent with new name
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = None
            # Third call: LLM configs query
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        request = Mock()
        request.new_name = "cloned-agent"
        request.clone_tools = True
        request.clone_knowledge_bases = False
        request.clone_sub_agents = False
        request.clone_workflows = True
        request.new_api_key = "new-key"

        # Import billing module and patch it
        import src.services.billing as billing_module

        original_service = getattr(billing_module, "PlanRestrictionService", None)
        original_error = getattr(billing_module, "PlanRestrictionError", None)

        try:
            mock_restriction = Mock()
            mock_restriction.enforce_agent_limit = AsyncMock()
            billing_module.PlanRestrictionService = Mock(return_value=mock_restriction)
            billing_module.PlanRestrictionError = Exception

            from src.controllers.agents.index import clone_agent

            # Don't patch Agent class - SQLAlchemy needs the real class for select()
            # Just mock the db operations and let the controller create real Agent instances
            with patch("src.services.agents.security.encrypt_value", return_value="encrypted"):
                result = await clone_agent(
                    agent_slug="test-agent", request=request, tenant_id=mock_tenant_id, db=mock_db
                )

                assert result.success is True
                assert "cloned-agent" in result.message
                mock_db.add.assert_called()
                mock_db.flush.assert_called()
        finally:
            if original_service:
                billing_module.PlanRestrictionService = original_service
            if original_error:
                billing_module.PlanRestrictionError = original_error

    @pytest.mark.asyncio
    async def test_clone_agent_source_not_found(self, mock_db, mock_tenant_id):
        """Test cloning non-existent agent."""
        # Mock db.execute to return None for source agent
        setup_db_execute_mock(mock_db, None)

        request = Mock()
        request.new_name = "cloned-agent"

        # Import billing module and patch it
        import src.services.billing as billing_module

        original_service = getattr(billing_module, "PlanRestrictionService", None)
        original_error = getattr(billing_module, "PlanRestrictionError", None)

        try:
            mock_restriction = Mock()
            mock_restriction.enforce_agent_limit = AsyncMock()
            billing_module.PlanRestrictionService = Mock(return_value=mock_restriction)
            billing_module.PlanRestrictionError = Exception

            from src.controllers.agents.index import clone_agent

            with pytest.raises(HTTPException) as exc_info:
                await clone_agent(agent_slug="nonexistent", request=request, tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 404
        finally:
            if original_service:
                billing_module.PlanRestrictionService = original_service
            if original_error:
                billing_module.PlanRestrictionError = original_error

    @pytest.mark.asyncio
    async def test_clone_agent_name_conflict(self, mock_db, mock_tenant_id, sample_agent):
        """Test cloning with conflicting name."""
        existing_agent = Mock()
        existing_agent.id = uuid4()

        # Track db.execute calls to return different results
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            # First call: source agent query - returns source
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = sample_agent
            # Second call: check existing agent with new name - returns existing
            else:
                mock_result.scalar_one_or_none.return_value = existing_agent
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        request = Mock()
        request.new_name = "existing-name"

        # Import billing module and patch it
        import src.services.billing as billing_module

        original_service = getattr(billing_module, "PlanRestrictionService", None)
        original_error = getattr(billing_module, "PlanRestrictionError", None)

        try:
            mock_restriction = Mock()
            mock_restriction.enforce_agent_limit = AsyncMock()
            billing_module.PlanRestrictionService = Mock(return_value=mock_restriction)
            billing_module.PlanRestrictionError = Exception

            from src.controllers.agents.index import clone_agent

            with pytest.raises(HTTPException) as exc_info:
                await clone_agent(agent_slug="test-agent", request=request, tenant_id=mock_tenant_id, db=mock_db)

            assert exc_info.value.status_code == 409
        finally:
            if original_service:
                billing_module.PlanRestrictionService = original_service
            if original_error:
                billing_module.PlanRestrictionError = original_error
