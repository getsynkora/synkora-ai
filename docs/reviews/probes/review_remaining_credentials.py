"""Local probes using synthetic tokens, mocked persistence, and no external network."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef',JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef',ENCRYPTION_KEY=Fernet.generate_key().decode(),CELERY_BROKER_URL='redis://localhost:6379/15',CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import httpx
from fastapi import FastAPI
from src.controllers.agents import handoff
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.models.user_oauth_token import UserOAuthToken
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.security import encrypt_value

async def main():
    results={}
    owner_a,owner_b,tenant_a,tenant_b= [uuid4() for _ in range(4)]
    memberships={owner_a:tenant_a,owner_b:tenant_b}
    app=SimpleNamespace(id=12,provider='micromobility',is_platform_app=True,tenant_id=None,app_name='Shared provider',auth_method='oauth',config={'base_url':'https://example.invalid'},api_token=None,access_token=None)
    for legacy in [False,True]:
        record=UserOAuthToken(account_id=owner_b,oauth_app_id=12)
        record.access_token=encrypt_value('foreign-token') if legacy else 'foreign-token'
        db=AsyncMock();statements=[]
        async def execute(stmt):
            statements.append(stmt)
            entity=stmt.column_descriptions[0]['entity']
            value={AgentTool:SimpleNamespace(oauth_app_id=12),OAuthApp:app,UserOAuthToken:record}[entity]
            return SimpleNamespace(scalar_one_or_none=lambda:value)
        db.execute.side_effect=execute
        @asynccontextmanager
        async def session():yield db
        context=SimpleNamespace(tenant_id=tenant_a,user_id=None,agent_id=uuid4(),db_session=db)
        with patch('src.core.database.get_async_session_factory',return_value=session):
            result=await CredentialResolver(context).get_micromobility_credentials('tool')
        query=statements[-1].compile()
        results['micromobility_legacy' if legacy else 'micromobility_current']={'foreign_token_returned':bool(result and result.get('access_token')=='foreign-token'),'personal_query_parameters':sorted(query.params.keys()),'token_owner_is_other_user':record.account_id!=owner_a,'owner_belongs_to_current_tenant':memberships[record.account_id]==context.tenant_id}
    key=SimpleNamespace(id=uuid4(),tenant_id=tenant_a,agent_id=uuid4(),permissions=['handoff:read'],allowed_ips=['203.0.113.10'],allowed_origins=['allowed.example.com'],rate_limit_per_minute=1)
    ip_check=MagicMock(wraps=AgentApiKeyService.validate_ip_address)
    origin_check=MagicMock(wraps=AgentApiKeyService.validate_origin)
    rate_check=MagicMock(return_value=(False,'Synthetic exhausted quota'))
    api=FastAPI();api.include_router(handoff.router)
    db=AsyncMock();db.execute.return_value=SimpleNamespace(scalar_one=lambda:0,scalars=lambda:SimpleNamespace(all=lambda:[]))
    api.dependency_overrides[get_async_db]=lambda:db
    with patch.object(AgentApiAuthMiddleware,'validate_api_key',new=AsyncMock(return_value=key)),patch.object(AgentApiKeyService,'validate_ip_address',ip_check),patch.object(AgentApiKeyService,'validate_origin',origin_check),patch.object(AgentApiKeyService,'check_rate_limit',rate_check):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api,client=('198.51.100.20',4321)),base_url='http://test') as client:
            response=await client.get('/conversations/handoffs',headers={'Authorization':'Bearer sk_synthetic','Origin':'https://unapproved.example.net'})
        results['handoff_restrictions']={'status':response.status_code,'ip_checks':ip_check.call_count,'origin_checks':origin_check.call_count,'rate_checks':rate_check.call_count}
    results['wildcard_origin']={'lookalike_accepted':AgentApiKeyService.validate_origin(SimpleNamespace(allowed_origins=['*.example.com']),'https://notexample.com')}
    print(json.dumps(results,indent=2))

asyncio.run(main())
