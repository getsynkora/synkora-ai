from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.activity_log import ActivityLog, ActivityType
from src.services.activity.activity_log_service import ActivityLogService


class TestActivityLogService:
    @pytest.fixture
    def mock_db(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db):
        return ActivityLogService(mock_db)

    @pytest.mark.asyncio
    async def test_log_activity_success(self, service, mock_db):
        tenant_id = uuid4()
        account_id = uuid4()

        log = await service.log_activity(
            tenant_id=tenant_id,
            account_id=account_id,
            action="create",
            resource_type="agent",
            resource_id=uuid4(),
            details={"name": "Test Agent"},
            ip_address="127.0.0.1",
            user_agent="TestClient",
        )

        assert log.tenant_id == tenant_id
        assert log.account_id == account_id
        assert log.action == "create"
        assert log.resource_type == "agent"
        assert log.activity_type == ActivityType.AGENT
        assert log.ip_address == "127.0.0.1"

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_activity_auth_type(self, service, mock_db):
        tenant_id = uuid4()
        account_id = uuid4()

        log = await service.log_activity(
            tenant_id=tenant_id, account_id=account_id, action="login", resource_type="auth"
        )
        # Assuming logic maps 'login' to AUTH type
        assert log.activity_type == ActivityType.AUTH
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_logs(self, service, mock_db):
        tenant_id = uuid4()
        mock_log = MagicMock(spec=ActivityLog)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute.return_value = mock_result

        result = await service.list_logs(tenant_id=tenant_id, limit=10)

        assert len(result) == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_logs_filters(self, service, mock_db):
        tenant_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await service.list_logs(
            tenant_id=tenant_id,
            account_id=str(uuid4()),
            action="create",
            resource_type="agent",
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC),
        )
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_user_activities(self, service, mock_db):
        account_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.get_user_activities(account_id)

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resource_activities(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.get_resource_activities("agent", uuid4())

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_security_events(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.get_security_events(uuid4())

        assert result == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_activities(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        count = await service.count_activities(tenant_id=uuid4(), action="create")
        assert count == 5

    @pytest.mark.asyncio
    async def test_delete_old_logs(self, service, mock_db):
        # delete_old_logs issues a single bulk DELETE rather than
        # select-then-delete-per-row, so the count comes from rowcount.
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_db.execute.return_value = mock_result

        count = await service.delete_old_logs(days=30, tenant_id=uuid4())

        assert count == 2
        mock_db.commit.assert_called_once()
