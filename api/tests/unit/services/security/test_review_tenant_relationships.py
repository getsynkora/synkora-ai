"""Regression tests for private role copying and tenant membership/resource boundaries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.services.roles.agent_role_service import AgentRoleService
from src.services.roles.project_service import ProjectService
from src.services.team.team_service import TeamService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "same_tenant,system,allowed", [(False, False, False), (True, False, True), (False, True, True)]
)
async def test_clone_authorizes_source(same_tenant, system, allowed):
    tenant = uuid4()
    source = SimpleNamespace(
        tenant_id=tenant if same_tenant else uuid4(),
        is_system_template=system,
        description="private",
        system_prompt_template="private prompt",
        suggested_tools=[],
        default_capabilities={},
    )
    service = AgentRoleService(AsyncMock())
    service.get_role = AsyncMock(return_value=source)
    service.create_role = AsyncMock(return_value=source)
    result = await service.clone_role(uuid4(), tenant, "Copy")
    assert (result is not None) == allowed
    assert service.create_role.await_count == int(allowed)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_project_rejects_inaccessible_knowledge_base_before_mutation(operation):
    tenant = uuid4()
    project = SimpleNamespace(knowledge_base_id=None)
    db = AsyncMock()
    db.add = MagicMock()
    absent = SimpleNamespace(scalar_one_or_none=lambda: None)
    db.execute.side_effect = (
        [SimpleNamespace(scalar_one_or_none=lambda: project), absent] if operation == "update" else [absent]
    )
    service = ProjectService(db)
    with pytest.raises(ValueError, match="Knowledge base not found"):
        if operation == "create":
            await service.create_project(tenant, "Project", knowledge_base_id=12)
        else:
            await service.update_project(uuid4(), tenant, knowledge_base_id=12)
    stmt = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "knowledge_bases.tenant_id =" in str(stmt)
    assert tenant in stmt.params.values()
    assert project.knowledge_base_id is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_accepts_owned_knowledge_base_and_null():
    tenant = uuid4()
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: 12)
    service = ProjectService(db)
    await service._validate_knowledge_base(12, tenant)
    await service._validate_knowledge_base(None, tenant)
    assert db.execute.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_role,target_role,new_role,removing,extra_owner,error",
    [
        ("ADMIN", "OWNER", "NORMAL", False, True, PermissionError),
        ("ADMIN", "OWNER", None, True, True, PermissionError),
        ("ADMIN", "OWNER", None, False, True, PermissionError),
        ("ADMIN", "NORMAL", "OWNER", False, True, PermissionError),
        ("NORMAL", "NORMAL", "ADMIN", False, True, PermissionError),
        ("OWNER", "OWNER", "NORMAL", False, False, ValueError),
        ("OWNER", "OWNER", None, True, False, ValueError),
        ("OWNER", "OWNER", "ADMIN", False, True, None),
        ("ADMIN", "NORMAL", "EDITOR", False, True, None),
        ("ADMIN", "NORMAL", None, True, True, None),
    ],
)
async def test_membership_privilege_boundaries(actor_role, target_role, new_role, removing, extra_owner, error):
    tenant, actor_id, target_id = uuid4(), uuid4(), uuid4()
    actor = SimpleNamespace(account_id=actor_id, role=actor_role)
    target = SimpleNamespace(account_id=target_id, role=target_role)
    # Model the last owner's self-demotion as well as changes to another owner.
    if actor_role == "OWNER" and not extra_owner:
        actor_id = target_id
        members = [target]
    else:
        members = [actor, target]
    if extra_owner:
        members.append(SimpleNamespace(account_id=uuid4(), role="OWNER"))
    db = AsyncMock()
    db.execute.side_effect = [MagicMock(), SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: members))]
    service = TeamService(db)
    if error:
        with pytest.raises(error):
            if removing:
                await service.remove_team_member(tenant, str(target_id), actor_id=actor_id)
            else:
                await service.update_team_member(tenant, str(target_id), actor_id=actor_id, role=new_role)
        db.commit.assert_not_awaited()
        db.delete.assert_not_awaited()
        assert target.role == target_role
    else:
        await service._authorize_member_change(tenant, str(target_id), actor_id, new_role=new_role, removing=removing)
    lock_stmt = str(db.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in lock_stmt
