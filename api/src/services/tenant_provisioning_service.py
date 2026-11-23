"""
Tenant provisioning - lets one tenant (the "manager") set up and run customer tenants through the API.

Use case: a product that embeds Synkora for its own customers. The product's backend creates a
tenant per customer, puts it on a plan, gives it agents and API keys, and reads back plan and usage.
Nothing here is specific to an industry or product.

Rules that keep this safe:
- A manager can only see and change tenants it created (``managed_by_tenant_id``).
- Agents are created from a template agent that belongs to the manager. Only non-secret settings
  are copied: never LLM keys, tool credentials, OAuth links or knowledge-base links.
- Billing happens outside Synkora. The manager tells Synkora which plan a customer is on and for
  which period; Synkora enforces the plan's allowances.
"""

import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.agent_llm_config import AgentLLMConfig
from src.models.subscription_plan import SubscriptionPlan
from src.models.tenant import Tenant, TenantPlan, TenantStatus, TenantType
from src.models.tenant_subscription import BillingCycle, SubscriptionStatus, TenantSubscription
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.agents.security import encrypt_value
from src.services.billing.plan_restriction_service import PlanRestrictionError, PlanRestrictionService
from src.services.billing.quota_service import QuotaService
from src.services.billing.subscription_service import SubscriptionService
from src.services.outbound_webhooks import EVENT_SUBSCRIPTION_UPDATED, emit_event, subscription_event_data

logger = logging.getLogger(__name__)

# Permissions a customer's API key may be given. Anything else (for example tenant management) is refused.
GRANTABLE_KEY_PERMISSIONS = frozenset(
    {"chat", "read", "write", "billing:read", "handoff:read", "handoff:write", "knowledge:read", "knowledge:write"}
)
DEFAULT_KEY_PERMISSIONS = ["chat", "read", "write", "billing:read"]
# A key restricted to browser origins is meant to be shipped to end users' browsers. Every end user can read it, so it
# may only chat: reading, listing, changing or deleting conversations, usage or knowledge must happen server-side.
BROWSER_KEY_PERMISSIONS = frozenset({"chat"})


class ProvisioningError(Exception):
    """A provisioning request cannot be completed. ``status_code`` is the HTTP status to return."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# Anything whose name suggests a credential is never copied from a template to a customer. Counts such as
# max_tokens or budget_tokens are settings, not secrets, so names ending in "tokens" are kept.
_SENSITIVE_NAME_PARTS = ("key", "token", "secret", "password", "passwd", "auth", "header", "credential", "cookie")
_SECRET_IN_PATH = re.compile(r"(key|token|secret|sig|signature|password|auth)[=:;]", re.IGNORECASE)


def _is_sensitive_name(name: Any) -> bool:
    lowered = str(name).lower()
    if lowered.endswith("tokens"):
        return False
    return any(part in lowered for part in _SENSITIVE_NAME_PARTS)


def _without_credentials(value: Any) -> Any:
    """A copy of ``value`` with credential-like entries removed at every level."""
    if isinstance(value, dict):
        # A header given as {"name": "Authorization", "value": "..."} is dropped whole
        if any(k in value and _is_sensitive_name(value[k]) for k in ("name", "key", "header")):
            return None
        return {k: _without_credentials(v) for k, v in value.items() if not _is_sensitive_name(k)}
    if isinstance(value, list):
        return [item for item in (_without_credentials(v) for v in value) if item is not None]
    return value


def _safe_api_base(url: str | None) -> str | None:
    """
    Keep a custom model endpoint only when it carries no credentials: no user name or password, no query string
    or fragment, and nothing like "key=" or ";token=" in the path.
    """
    if not url:
        return url
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or _SECRET_IN_PATH.search(parsed.path):
        return None
    return url


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", text.lower())
    return re.sub(r"-+", "-", slug).strip("-") or "agent"


class TenantProvisioningService:
    def __init__(self, db: AsyncSession, manager: Tenant):
        self.db = db
        self.manager = manager
        self.subscriptions = SubscriptionService(db)

    # ---- tenants -------------------------------------------------------------------------------

    async def get_managed(self, tenant_id: uuid.UUID) -> Tenant:
        """A tenant this manager created. Anything else is reported as not found, never as forbidden."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.managed_by_tenant_id == self.manager.id)
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            raise ProvisioningError("Tenant not found", 404)
        return tenant

    async def list_tenants(
        self, limit: int = 50, offset: int = 0, external_ref: str | None = None
    ) -> tuple[list[Tenant], int]:
        conditions = [Tenant.managed_by_tenant_id == self.manager.id]
        if external_ref:
            conditions.append(Tenant.external_ref == external_ref)
        rows = await self.db.execute(
            select(Tenant).where(*conditions).order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
        )
        total = await self.db.scalar(select(func.count(Tenant.id)).where(*conditions))
        return list(rows.scalars().all()), int(total or 0)

    async def create_tenant(
        self,
        name: str,
        external_ref: str | None = None,
        plan: str | None = None,
        billing_cycle: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> Tenant:
        # Validate everything before anything is written, so a bad request leaves nothing behind
        await self._ensure_below_workspace_limit()
        cycle = self._parse_cycle(billing_cycle)
        period_start, period_end = self._clean_period(period_start, period_end)
        if external_ref:
            await self._ensure_external_ref_free(external_ref)
        plan_row = await self._resolve_plan(plan) if plan else None

        tenant = Tenant(
            name=name,
            plan=TenantPlan.FREE,
            status=TenantStatus.ACTIVE,
            tenant_type=TenantType.EXTERNAL,
            managed_by_tenant_id=self.manager.id,
            external_ref=external_ref,
        )
        try:
            self.db.add(tenant)
            await self.db.flush()
            if plan_row:
                await self._start_subscription(tenant, plan_row, cycle, period_start, period_end)
            else:
                await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ProvisioningError(f"A tenant with external_ref {external_ref!r} already exists", 409) from None
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(tenant)
        return tenant

    async def workspace_limit(self) -> int:
        """How many customer workspaces this manager may have: its plan's features.max_managed_tenants, else the default."""
        features = await self.db.scalar(
            select(SubscriptionPlan.features)
            .join(TenantSubscription, TenantSubscription.plan_id == SubscriptionPlan.id)
            .where(
                TenantSubscription.tenant_id == self.manager.id,
                TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            )
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
        )
        value = (features or {}).get("max_managed_tenants")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return settings.max_managed_tenants_default

    async def _ensure_below_workspace_limit(self) -> None:
        # Self-serve managers (any tenant with a platform key) must not be able to create workspaces without end
        limit = await self.workspace_limit()
        count = await self.db.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.managed_by_tenant_id == self.manager.id)
        )
        if (count or 0) >= limit:
            raise ProvisioningError(
                f"Workspace limit reached ({limit}). Upgrade your plan or contact support for more.", 403
            )

    async def update_tenant(self, tenant: Tenant, name: str | None = None, external_ref: str | None = None) -> Tenant:
        if name:
            tenant.name = name
        if external_ref and external_ref != tenant.external_ref:
            await self._ensure_external_ref_free(external_ref)
            tenant.external_ref = external_ref
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def _ensure_external_ref_free(self, external_ref: str) -> None:
        taken = await self.db.scalar(
            select(Tenant.id).where(Tenant.managed_by_tenant_id == self.manager.id, Tenant.external_ref == external_ref)
        )
        if taken:
            raise ProvisioningError(f"A tenant with external_ref {external_ref!r} already exists", 409)

    # ---- subscription --------------------------------------------------------------------------

    async def _resolve_plan(self, plan_ref: str) -> SubscriptionPlan:
        """A plan by id or by name. Inactive plans cannot be assigned."""
        conditions = [SubscriptionPlan.name == plan_ref]
        try:
            conditions.append(SubscriptionPlan.id == uuid.UUID(plan_ref))
        except ValueError:
            pass
        result = await self.db.execute(select(SubscriptionPlan).where(or_(*conditions)))
        plan = result.scalars().first()
        if plan is None:
            raise ProvisioningError(f"Plan {plan_ref!r} not found", 404)
        if not plan.is_active:
            raise ProvisioningError(f"Plan {plan_ref!r} is not available", 409)
        return plan

    @staticmethod
    def _parse_cycle(value: str | None) -> BillingCycle | None:
        if value is None:
            return None
        try:
            return BillingCycle(value.upper())
        except ValueError:
            raise ProvisioningError(f"billing_cycle must be one of {[c.value for c in BillingCycle]}") from None

    @staticmethod
    def _clean_period(start: datetime | None, end: datetime | None) -> tuple[datetime | None, datetime | None]:
        """Dates without a timezone are taken as UTC, then checked: the end must follow the start."""
        start = start.replace(tzinfo=UTC) if start and start.tzinfo is None else start
        end = end.replace(tzinfo=UTC) if end and end.tzinfo is None else end
        if start and end and end <= start:
            raise ProvisioningError("period_end must be after period_start")
        return start, end

    @staticmethod
    def _parse_status(value: str | None) -> SubscriptionStatus | None:
        if value is None:
            return None
        try:
            return SubscriptionStatus(value.upper())
        except ValueError:
            raise ProvisioningError(f"status must be one of {[s.value for s in SubscriptionStatus]}") from None

    async def _announce(self, tenant: Tenant, subscription: TenantSubscription) -> None:
        """Tell registered webhook endpoints that this customer's subscription changed. Best effort."""
        try:
            plan = await self.subscriptions.get_plan(subscription.plan_id)
            await emit_event(
                self.db,
                tenant.id,
                EVENT_SUBSCRIPTION_UPDATED,
                subscription_event_data(subscription, plan.name if plan else None),
            )
        except Exception:
            logger.warning("Could not announce subscription change for tenant %s", tenant.id, exc_info=True)

    async def _start_subscription(
        self,
        tenant: Tenant,
        plan: SubscriptionPlan,
        cycle: BillingCycle | None,
        period_start: datetime | None,
        period_end: datetime | None,
    ) -> TenantSubscription:
        """Create the subscription. ``cycle`` and the period must already be validated."""
        subscription = await self.subscriptions.create_subscription(tenant.id, plan.id, payment_provider="external")
        if cycle:
            subscription.billing_cycle = cycle
        self._apply_period(subscription, period_start, period_end)
        await self.db.commit()
        await self.db.refresh(subscription)
        await self._announce(tenant, subscription)
        return subscription

    @staticmethod
    def _apply_period(subscription: TenantSubscription, start: datetime | None, end: datetime | None) -> None:
        if start:
            subscription.current_period_start = start
            if not end and (subscription.current_period_end is None or subscription.current_period_end <= start):
                subscription.current_period_end = start + timedelta(days=30)
        if end:
            subscription.current_period_end = end

    async def _latest_subscription(self, tenant_id: uuid.UUID) -> TenantSubscription | None:
        """The most recent subscription in any status, so a suspended customer is updated, not duplicated."""
        result = await self.db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def set_subscription(
        self,
        tenant: Tenant,
        plan: str | None = None,
        status: str | None = None,
        billing_cycle: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        cancel_at_period_end: bool | None = None,
        renew: bool = False,
    ) -> TenantSubscription:
        """
        Change a customer's plan, status or billing period.

        Billing runs outside Synkora, so this is how a renewal is reported: send ``renew: true`` (or a
        new period). A new period starts every message pool at zero.
        """
        # Validate everything first: nothing below commits until the request is known to be good
        cycle = self._parse_cycle(billing_cycle)
        period_start, period_end = self._clean_period(period_start, period_end)
        new_status = self._parse_status(status)
        plan_row = await self._resolve_plan(plan) if plan else None

        subscription = await self._latest_subscription(tenant.id)
        if subscription is None:
            if plan_row is None:
                raise ProvisioningError("This tenant has no subscription yet: provide a plan", 409)
            return await self._start_subscription(tenant, plan_row, cycle, period_start, period_end)

        if plan_row and plan_row.id != subscription.plan_id:
            if subscription.status == SubscriptionStatus.ACTIVE:
                subscription = await self.subscriptions.upgrade_subscription(tenant.id, plan_row.id)
            else:
                subscription.plan_id = plan_row.id  # no proration for a subscription that is not running

        if renew:
            # A renewal reported by your billing system means the customer paid, so it overrides a pending
            # cancellation (unless this same request asks for one again, applied below).
            subscription.cancel_at_period_end = False
            subscription = await self.subscriptions.renew_subscription(subscription.id)

        if cycle:
            subscription.billing_cycle = cycle
        self._apply_period(subscription, period_start, period_end)
        if cancel_at_period_end is not None:
            subscription.cancel_at_period_end = cancel_at_period_end
        if new_status:
            subscription.status = new_status
            if new_status == SubscriptionStatus.CANCELLED:
                subscription.cancelled_at = datetime.now(UTC)
            elif new_status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL):
                subscription.cancelled_at = None
        await self.db.commit()
        await self.db.refresh(subscription)
        await self._announce(tenant, subscription)
        return subscription

    # ---- agents and keys -----------------------------------------------------------------------

    async def list_agents(self, tenant: Tenant) -> list[Agent]:
        result = await self.db.execute(
            select(Agent).where(Agent.tenant_id == tenant.id).order_by(Agent.created_at.asc())
        )
        return list(result.scalars().all())

    async def _agent_of(self, tenant: Tenant, agent_id: uuid.UUID) -> Agent:
        result = await self.db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant.id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ProvisioningError("Agent not found", 404)
        return agent

    async def create_agent_from_template(
        self,
        tenant: Tenant,
        template_agent_id: uuid.UUID,
        name: str,
        quota_pool: str | None = None,
        llm_api_key: str | None = None,
    ) -> Agent:
        """
        Create an agent in a customer tenant from one of the manager's own template agents.

        Copies prompt, description, suggestions, category, tags and the LLM provider, model and
        parameters. Never copies secrets or links to the manager's data: LLM keys, tool credentials,
        knowledge-base links, credential-like model parameters (headers, tokens, ...) and endpoint
        URLs that embed credentials are all left out. The new agent has no LLM key until
        ``llm_api_key`` is supplied (now or later with ``set_llm_key``).
        """
        template = await self.db.scalar(
            select(Agent).where(Agent.id == template_agent_id, Agent.tenant_id == self.manager.id)
        )
        if template is None:
            raise ProvisioningError("Template agent not found", 404)

        wanted_pool = quota_pool if quota_pool is not None else template.quota_pool
        offered = await QuotaService(self.db).unassigned_pool_keys(tenant.id, wanted_pool)
        if offered is not None:
            raise ProvisioningError(
                f"Pool {wanted_pool or 'default'!r} is not in this customer's plan. Choose one of: {', '.join(offered)}"
            )

        try:
            await PlanRestrictionService(self.db).enforce_agent_limit(tenant.id)
        except PlanRestrictionError as err:
            raise ProvisioningError(str(err), 403) from err

        taken = await self.db.scalar(select(Agent.id).where(Agent.tenant_id == tenant.id, Agent.agent_name == name))
        if taken:
            raise ProvisioningError(f"An agent named {name!r} already exists in this tenant", 409)

        legacy_llm = _without_credentials(dict(template.llm_config or {}))
        if "api_base" in legacy_llm:
            legacy_llm["api_base"] = _safe_api_base(legacy_llm["api_base"])
        if llm_api_key:
            legacy_llm["api_key"] = encrypt_value(llm_api_key)

        agent = Agent(
            tenant_id=tenant.id,
            agent_name=name,
            slug=f"{_slugify(name)}-{secrets.token_hex(3)}",
            agent_type=template.agent_type,
            description=template.description,
            system_prompt=template.system_prompt,
            llm_config=legacy_llm,
            tools_config=None,
            agent_metadata={},
            suggestion_prompts=list(template.suggestion_prompts or []),
            category=template.category,
            tags=list(template.tags or []),
            quota_pool=quota_pool if quota_pool is not None else template.quota_pool,
            is_public=False,
            status="ACTIVE",
            execution_count=0,
            success_count=0,
            likes_count=0,
            dislikes_count=0,
            usage_count=0,
        )
        self.db.add(agent)
        await self.db.flush()

        configs = await self.db.execute(select(AgentLLMConfig).where(AgentLLMConfig.agent_id == template.id))
        for config in configs.scalars().all():
            has_key = bool(llm_api_key) and config.is_default
            self.db.add(
                AgentLLMConfig(
                    tenant_id=tenant.id,
                    agent_id=agent.id,
                    name=config.name,
                    provider=config.provider,
                    model_name=config.model_name,
                    api_key=encrypt_value(llm_api_key) if has_key else "",
                    api_base=_safe_api_base(config.api_base),
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    top_p=config.top_p,
                    additional_params=_without_credentials(dict(config.additional_params))
                    if config.additional_params
                    else None,
                    is_default=config.is_default,
                    display_order=config.display_order,
                    enabled=has_key,
                )
            )
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def set_llm_key(self, tenant: Tenant, agent_id: uuid.UUID, api_key: str) -> None:
        """Set the LLM API key for a customer's agent and enable its default model."""
        agent = await self._agent_of(tenant, agent_id)
        agent.llm_config = {**(agent.llm_config or {}), "api_key": encrypt_value(api_key)}
        configs = await self.db.execute(select(AgentLLMConfig).where(AgentLLMConfig.agent_id == agent.id))
        for config in configs.scalars().all():
            if config.is_default:
                config.api_key = encrypt_value(api_key)
                config.enabled = True
        await self.db.commit()

    async def create_api_key(
        self,
        tenant: Tenant,
        agent_id: uuid.UUID,
        name: str,
        permissions: list[str] | None = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: int = 1000,
        rate_limit_per_day: int = 10000,
        allowed_origins: list[str] | None = None,
    ) -> tuple[AgentApiKey, str]:
        """Create an API key for a customer's agent. The plain key is returned once and never stored."""
        await self._agent_of(tenant, agent_id)
        if allowed_origins:
            wanted = ["chat"] if permissions is None else list(permissions)
            too_broad = sorted(set(wanted) - BROWSER_KEY_PERMISSIONS)
            if too_broad:
                raise ProvisioningError(
                    f"A key for browsers (allowed_origins) can only chat; {too_broad} must stay on your server. "
                    "Create a separate server-side key for those."
                )
        else:
            wanted = list(DEFAULT_KEY_PERMISSIONS) if permissions is None else list(permissions)
        if not wanted:
            raise ProvisioningError("A key needs at least one permission")
        refused = sorted(set(wanted) - GRANTABLE_KEY_PERMISSIONS)
        if refused:
            raise ProvisioningError(
                f"Permissions not allowed for customer keys: {refused}. Allowed: {sorted(GRANTABLE_KEY_PERMISSIONS)}"
            )
        try:
            await PlanRestrictionService(self.db).enforce_api_key_limit(tenant.id)
        except PlanRestrictionError as err:
            raise ProvisioningError(str(err), 403) from err

        api_key, plain = await AgentApiKeyService.create_api_key(
            db=self.db,
            agent_id=agent_id,
            tenant_id=tenant.id,
            name=name,
            permissions=list(wanted),
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            allowed_origins=allowed_origins,
        )
        return api_key, plain


def describe_tenant(tenant: Tenant) -> dict[str, Any]:
    """Public fields of a managed tenant."""
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "external_ref": tenant.external_ref,
        "status": tenant.status,
        "created_at": tenant.created_at,
    }
