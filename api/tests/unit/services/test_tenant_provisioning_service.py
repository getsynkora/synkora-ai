from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_llm_config import AgentLLMConfig
from src.models.tenant_subscription import SubscriptionStatus
from src.services import tenant_provisioning_service as svc
from src.services.tenant_provisioning_service import ProvisioningError, TenantProvisioningService

MANAGER_ID = uuid4()


def _result(value=None, items=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.all.return_value = items or []
    r.scalars.return_value.first.return_value = value
    return r


@pytest.fixture
def db():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def service(db):
    return TenantProvisioningService(db, MagicMock(id=MANAGER_ID))


class TestTenantScope:
    async def test_unknown_or_unmanaged_tenant_is_not_found(self, service, db):
        db.execute.return_value = _result(None)
        with pytest.raises(ProvisioningError) as err:
            await service.get_managed(uuid4())
        assert err.value.status_code == 404

    async def test_lookup_is_restricted_to_tenants_this_manager_created(self, service, db):
        db.execute.return_value = _result(MagicMock())
        tenant_id = uuid4()
        await service.get_managed(tenant_id)
        compiled = db.execute.call_args[0][0].compile()
        assert "managed_by_tenant_id" in str(compiled)
        assert MANAGER_ID in compiled.params.values()
        assert tenant_id in compiled.params.values()


class TestCreateAgentFromTemplate:
    def _template(self):
        template = MagicMock(spec=Agent)
        template.id = uuid4()
        template.tenant_id = MANAGER_ID
        template.agent_type = "LLM"
        template.description = "Helps riders"
        template.system_prompt = "You are helpful."
        template.llm_config = {"provider": "openai", "model_name": "gpt-4o", "api_key": "MANAGER-SECRET"}
        template.suggestion_prompts = [{"title": "Hi"}]
        template.category = "Support"
        template.tags = ["a"]
        template.quota_pool = "assistant"
        return template

    def _llm_config(self):
        cfg = MagicMock(spec=AgentLLMConfig)
        cfg.name, cfg.provider, cfg.model_name = "Default", "openai", "gpt-4o"
        cfg.api_base, cfg.temperature, cfg.max_tokens, cfg.top_p = None, 0.7, None, None
        cfg.additional_params, cfg.is_default, cfg.display_order = None, True, 0
        return cfg

    async def _create(self, service, db, **kwargs):
        template = self._template()
        db.scalar.side_effect = [template, None]  # template found, name not taken
        db.execute.return_value = _result(items=[self._llm_config()])
        tenant = MagicMock(id=uuid4())
        with (
            patch.object(svc, "PlanRestrictionService") as restrictions,
            patch.object(svc, "QuotaService") as quota,
            patch.object(svc, "encrypt_value", side_effect=lambda v: f"enc({v})"),
        ):
            quota.return_value.unassigned_pool_keys = AsyncMock(return_value=None)
            restrictions.return_value.enforce_agent_limit = AsyncMock()
            agent = await service.create_agent_from_template(tenant, template.id, "Rider helper", **kwargs)
        added = [c.args[0] for c in db.add.call_args_list]
        return agent, tenant, added

    async def test_copies_settings_but_never_secrets(self, service, db):
        agent, tenant, added = await self._create(service, db)

        assert agent.tenant_id == tenant.id
        assert agent.system_prompt == "You are helpful."
        assert agent.quota_pool == "assistant"
        assert "api_key" not in agent.llm_config
        assert agent.tools_config is None  # tool credentials are never copied
        config = next(a for a in added if isinstance(a, AgentLLMConfig))
        assert config.api_key == "" and config.enabled is False
        assert config.tenant_id == tenant.id

    async def test_customer_llm_key_is_stored_encrypted_and_enables_the_model(self, service, db):
        agent, _, added = await self._create(service, db, llm_api_key="cust-key")

        assert agent.llm_config["api_key"] == "enc(cust-key)"
        config = next(a for a in added if isinstance(a, AgentLLMConfig))
        assert config.api_key == "enc(cust-key)" and config.enabled is True

    async def test_quota_pool_can_be_overridden(self, service, db):
        agent, _, _ = await self._create(service, db, quota_pool="operations")
        assert agent.quota_pool == "operations"

    async def test_template_must_belong_to_the_manager(self, service, db):
        db.scalar.side_effect = [None]
        with pytest.raises(ProvisioningError) as err:
            await service.create_agent_from_template(MagicMock(id=uuid4()), uuid4(), "x")
        assert err.value.status_code == 404
        assert MANAGER_ID in db.scalar.call_args[0][0].compile().params.values()

    async def test_agent_limit_of_the_customers_plan_is_enforced(self, service, db):
        db.scalar.side_effect = [self._template()]
        with patch.object(svc, "PlanRestrictionService") as restrictions, patch.object(svc, "QuotaService") as quota:
            quota.return_value.unassigned_pool_keys = AsyncMock(return_value=None)
            restrictions.return_value.enforce_agent_limit = AsyncMock(side_effect=svc.PlanRestrictionError("limit"))
            with pytest.raises(ProvisioningError) as err:
                await service.create_agent_from_template(MagicMock(id=uuid4()), uuid4(), "x")
        assert err.value.status_code == 403


class TestCreateApiKey:
    @pytest.mark.parametrize("permission", ["tenants:manage", "*", "agent:admin"])
    async def test_customer_keys_cannot_get_powerful_permissions(self, service, permission):
        with patch.object(service, "_agent_of", AsyncMock()):
            with pytest.raises(ProvisioningError, match="not allowed"):
                await service.create_api_key(MagicMock(id=uuid4()), uuid4(), "k", permissions=[permission])

    async def test_default_permissions_include_chat_and_plan_reading(self, service):
        key = MagicMock()
        with (
            patch.object(service, "_agent_of", AsyncMock()),
            patch.object(svc, "PlanRestrictionService") as restrictions,
            patch.object(svc.AgentApiKeyService, "create_api_key", AsyncMock(return_value=(key, "sk_plain"))) as create,
        ):
            restrictions.return_value.enforce_api_key_limit = AsyncMock()
            _, plain = await service.create_api_key(MagicMock(id=uuid4()), uuid4(), "k")
        assert plain == "sk_plain"
        assert set(create.call_args.kwargs["permissions"]) == {"chat", "read", "write", "billing:read"}


class TestSetSubscription:
    def _sub(self, status=SubscriptionStatus.ACTIVE):
        return MagicMock(
            id=uuid4(),
            plan_id=uuid4(),
            status=status,
            current_period_start=datetime(2026, 11, 1, tzinfo=UTC),
            current_period_end=datetime(2026, 12, 1, tzinfo=UTC),
            cancel_at_period_end=False,
            cancelled_at=None,
        )

    async def test_no_subscription_and_no_plan_is_a_conflict(self, service):
        with patch.object(service, "_latest_subscription", AsyncMock(return_value=None)):
            with pytest.raises(ProvisioningError) as err:
                await service.set_subscription(MagicMock(id=uuid4()))
        assert err.value.status_code == 409

    async def test_period_end_must_follow_start(self, service):
        start = datetime(2026, 12, 1, tzinfo=UTC)
        with pytest.raises(ProvisioningError, match="period_end"):
            await service.set_subscription(
                MagicMock(id=uuid4()), period_start=start, period_end=start - timedelta(days=1)
            )

    async def test_unknown_status_is_rejected(self, service):
        with patch.object(service, "_latest_subscription", AsyncMock(return_value=self._sub())):
            with pytest.raises(ProvisioningError, match="status"):
                await service.set_subscription(MagicMock(id=uuid4()), status="PAUSED")

    async def test_cancelling_records_when_and_reactivating_clears_it(self, service):
        sub = self._sub()
        with patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)):
            await service.set_subscription(MagicMock(id=uuid4()), status="cancelled")
            assert sub.status == SubscriptionStatus.CANCELLED and sub.cancelled_at is not None
            await service.set_subscription(MagicMock(id=uuid4()), status="ACTIVE")
            assert sub.status == SubscriptionStatus.ACTIVE and sub.cancelled_at is None

    async def test_new_period_and_cancel_at_period_end_are_saved(self, service):
        sub = self._sub()
        start, end = datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)
        with patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)):
            await service.set_subscription(
                MagicMock(id=uuid4()), period_start=start, period_end=end, cancel_at_period_end=True
            )
        assert (sub.current_period_start, sub.current_period_end) == (start, end)
        assert sub.cancel_at_period_end is True

    async def test_plan_change_on_a_running_subscription_prorates_through_upgrade(self, service):
        sub = self._sub()
        new_plan = MagicMock(id=uuid4())
        upgraded = self._sub()
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service, "_resolve_plan", AsyncMock(return_value=new_plan)),
            patch.object(service.subscriptions, "upgrade_subscription", AsyncMock(return_value=upgraded)) as upgrade,
        ):
            await service.set_subscription(MagicMock(id=uuid4()), plan="Scale")
        upgrade.assert_awaited_once()

    async def test_plan_change_on_a_suspended_subscription_just_switches_the_plan(self, service):
        sub = self._sub(SubscriptionStatus.SUSPENDED)
        new_plan = MagicMock(id=uuid4())
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service, "_resolve_plan", AsyncMock(return_value=new_plan)),
            patch.object(service.subscriptions, "upgrade_subscription", AsyncMock()) as upgrade,
        ):
            await service.set_subscription(MagicMock(id=uuid4()), plan="Scale")
        upgrade.assert_not_called()
        assert sub.plan_id == new_plan.id


class TestSubscriptionEvents:
    async def test_a_change_is_announced_to_webhook_endpoints(self, service):
        sub = MagicMock(
            id=uuid4(),
            plan_id=uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            cancelled_at=None,
        )
        tenant = MagicMock(id=uuid4())
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service.subscriptions, "get_plan", AsyncMock(return_value=MagicMock(plan_name="x"))),
            patch.object(svc, "emit_event", AsyncMock()) as emit,
        ):
            await service.set_subscription(tenant, status="SUSPENDED")

        emit.assert_awaited_once()
        assert emit.await_args.args[1] == tenant.id
        assert emit.await_args.args[2] == "subscription.updated"
        assert emit.await_args.args[3]["status"] == "SUSPENDED"


class TestNothingIsWrittenForABadRequest:
    async def test_bad_billing_cycle_creates_no_tenant(self, service, db):
        """Reproduces a 400 that still left the tenant behind, making a corrected retry return 409."""
        db.scalar.return_value = None
        with patch.object(service, "_resolve_plan", AsyncMock(return_value=MagicMock(id=uuid4()))):
            with pytest.raises(ProvisioningError, match="billing_cycle"):
                await service.create_tenant("Acme", external_ref="c1", plan="Growth", billing_cycle="WEEKLY")
        db.add.assert_not_called()
        db.flush.assert_not_called()
        db.commit.assert_not_called()

    async def test_a_failure_while_creating_rolls_everything_back(self, service, db):
        db.scalar.return_value = None
        with (
            patch.object(service, "_resolve_plan", AsyncMock(return_value=MagicMock(id=uuid4()))),
            patch.object(service, "_start_subscription", AsyncMock(side_effect=RuntimeError("db error"))),
        ):
            with pytest.raises(RuntimeError):
                await service.create_tenant("Acme", plan="Growth")
        db.rollback.assert_awaited_once()

    async def test_bad_values_stop_a_subscription_change_before_anything_is_committed(self, service):
        sub = MagicMock(id=uuid4(), plan_id=uuid4(), status=SubscriptionStatus.ACTIVE, cancel_at_period_end=False)
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service, "_resolve_plan", AsyncMock(return_value=MagicMock(id=uuid4()))),
            patch.object(service.subscriptions, "upgrade_subscription", AsyncMock()) as upgrade,
            patch.object(service.subscriptions, "renew_subscription", AsyncMock()) as renew,
        ):
            with pytest.raises(ProvisioningError, match="billing_cycle"):
                await service.set_subscription(MagicMock(id=uuid4()), plan="Scale", renew=True, billing_cycle="WEEKLY")
        upgrade.assert_not_called()
        renew.assert_not_called()

    def test_dates_without_a_timezone_are_taken_as_utc(self):
        naive_start = datetime(2026, 12, 1)
        aware_end = datetime(2027, 1, 1, tzinfo=UTC)
        start, end = TenantProvisioningService._clean_period(naive_start, aware_end)
        assert start.tzinfo is UTC and end == aware_end

    def test_an_end_before_the_start_is_rejected_even_when_only_one_has_a_timezone(self):
        with pytest.raises(ProvisioningError, match="period_end"):
            TenantProvisioningService._clean_period(datetime(2026, 12, 2, tzinfo=UTC), datetime(2026, 12, 1))


class TestRenewVersusCancelAtPeriodEnd:
    def _flagged(self):
        return MagicMock(
            id=uuid4(),
            plan_id=uuid4(),
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime(2026, 11, 1, tzinfo=UTC),
            current_period_end=datetime(2026, 12, 1, tzinfo=UTC),
            cancel_at_period_end=True,
            cancelled_at=None,
        )

    async def test_a_paid_renewal_clears_a_pending_cancellation_before_renewing(self, service):
        """Reproduces renew=true, cancel_at_period_end=false ending the subscription instead of renewing it."""
        sub = self._flagged()
        flag_seen_by_renew = []

        async def renew(_id):
            flag_seen_by_renew.append(sub.cancel_at_period_end)
            return sub

        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service.subscriptions, "renew_subscription", AsyncMock(side_effect=renew)),
        ):
            await service.set_subscription(MagicMock(id=uuid4()), renew=True, cancel_at_period_end=False)

        assert flag_seen_by_renew == [False]  # renew saw no pending cancellation, so it does not cancel
        assert sub.cancel_at_period_end is False
        assert sub.status == SubscriptionStatus.ACTIVE

    async def test_renew_without_mentioning_the_flag_also_clears_it(self, service):
        sub = self._flagged()
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service.subscriptions, "renew_subscription", AsyncMock(return_value=sub)),
        ):
            await service.set_subscription(MagicMock(id=uuid4()), renew=True)
        assert sub.cancel_at_period_end is False

    async def test_renew_and_cancel_in_one_request_renews_then_schedules_the_cancellation(self, service):
        sub = self._flagged()
        sub.cancel_at_period_end = False
        with (
            patch.object(service, "_latest_subscription", AsyncMock(return_value=sub)),
            patch.object(service.subscriptions, "renew_subscription", AsyncMock(return_value=sub)),
        ):
            await service.set_subscription(MagicMock(id=uuid4()), renew=True, cancel_at_period_end=True)
        assert sub.cancel_at_period_end is True


class TestAgentPoolMustBeInTheCustomersPlan:
    async def test_a_pool_the_plan_does_not_include_is_refused_before_anything_is_created(self, service, db):
        """Reproduces an agent created on a pool plan with no matching pool, which then fails every chat."""
        template = MagicMock(id=uuid4(), tenant_id=MANAGER_ID, quota_pool=None)
        db.scalar.side_effect = [template]
        with patch.object(svc, "QuotaService") as quota:
            quota.return_value.unassigned_pool_keys = AsyncMock(return_value=["assistant", "operations"])
            with pytest.raises(ProvisioningError, match="assistant, operations") as err:
                await service.create_agent_from_template(MagicMock(id=uuid4()), template.id, "Helper")
        assert "'default'" in str(err.value)
        assert err.value.status_code == 400
        db.add.assert_not_called()
        quota.return_value.unassigned_pool_keys.assert_awaited_once()

    async def test_an_explicit_pool_overrides_the_templates_when_checking(self, service, db):
        template = MagicMock(id=uuid4(), tenant_id=MANAGER_ID, quota_pool="assistant")
        db.scalar.side_effect = [template]
        with patch.object(svc, "QuotaService") as quota:
            quota.return_value.unassigned_pool_keys = AsyncMock(return_value=["assistant"])
            with pytest.raises(ProvisioningError, match="'typo'"):
                await service.create_agent_from_template(
                    MagicMock(id=uuid4()), template.id, "Helper", quota_pool="typo"
                )
        assert quota.return_value.unassigned_pool_keys.await_args.args[1] == "typo"
