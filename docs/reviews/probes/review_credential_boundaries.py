"""Local diagnostic: synthetic identities and mocked DB/provider boundaries, no network."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef', JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef', ENCRYPTION_KEY=Fernet.generate_key().decode(), CELERY_BROKER_URL='redis://localhost:6379/15', CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from src.middleware.agent_api_auth import get_tenant_from_jwt_or_api_key
from src.controllers.agents.handoff import get_handoff_detail
from src.controllers.oauth import salesforce, jira
from src.models import Account, AccountStatus, Tenant, TenantAccountJoin
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.oauth_app import OAuthApp
from src.models.user_oauth_token import UserOAuthToken
from src.services.agents.security import encrypt_value

async def main():
    results={}
    tenant, agent_a, agent_b=uuid4(),uuid4(),uuid4()
    key='sk_live_synthetic_review_key_0123456789'
    record=SimpleNamespace(id=uuid4(),tenant_id=tenant,agent_id=agent_a,permissions=['chat'],api_key=encrypt_value(key),expires_at=None)
    conv=Conversation(id=uuid4(),agent_id=agent_b,handoff_status='active')
    conv.messages=[Message(id=uuid4(),role='user',content='agent B private conversation',status='completed')]
    db=AsyncMock()
    async def execute(stmt):
        entity=stmt.column_descriptions[0]['entity']
        if entity is AgentApiKey: return SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:[record]))
        value={Conversation:conv,Agent:SimpleNamespace(id=agent_b,tenant_id=tenant)}[entity]
        return SimpleNamespace(scalar_one_or_none=lambda:value)
    db.execute.side_effect=execute
    authorized_tenant=await get_tenant_from_jwt_or_api_key('Bearer '+key,db)
    detail=await get_handoff_detail(conv.id,authorized_tenant,db)
    results['agent_key']={'permissions':record.permissions,'different_agent':agent_a!=agent_b,'other_agent_message_returned':detail['messages'][0]['content']=='agent B private conversation'}
    for module, provider_name, class_name in [(salesforce,'salesforce','SalesforceOAuth'),(jira,'jira','JiraOAuth')]:
        account=SimpleNamespace(id=uuid4(),status=AccountStatus.ACTIVE,auth_version=0)
        app=SimpleNamespace(id=12,provider=provider_name,tenant_id=None,is_platform_app=True,client_id='synthetic',client_secret='synthetic',redirect_uri='https://example.invalid/callback',config={'instance_url':'https://original.example.invalid','cloud_id':'original-cloud'},access_token='unchanged-shared-token')
        user_token=SimpleNamespace(access_token='old-personal-token')
        state={'oauth_app_id':12,'account_id':str(account.id),'tenant_id':str(tenant),'auth_version':0,'user_level':True,'redirect_url':'https://example.invalid'}
        db=AsyncMock()
        async def execute_oauth(stmt):
            entity=stmt.column_descriptions[0]['entity']
            value={Account:account,TenantAccountJoin:object(),Tenant:SimpleNamespace(disabled_platform_oauth_providers=[]),OAuthApp:app,UserOAuthToken:user_token}[entity]
            return SimpleNamespace(scalar_one_or_none=lambda:value)
        db.execute.side_effect=execute_oauth
        provider=MagicMock()
        provider.get_access_token=AsyncMock(return_value={'access_token':'new-personal-token','instance_url':'https://personal.example.invalid','expires_in':3600})
        provider.get_user_info=AsyncMock(return_value={'id':'user','email':'member@example.invalid','name':'Member','account_id':'user','cloud_id':'personal-cloud'})
        permission=AsyncMock(return_value=False)
        with patch.object(module,'get_oauth_state',return_value=state),patch.object(module,class_name,return_value=provider),patch.object(module,'decrypt_value',side_effect=lambda x:x),patch.object(module,'get_app_base_url',new=AsyncMock(return_value='https://example.invalid')),patch('src.services.permissions.permission_service.PermissionService.check_permission',new=permission):
            await getattr(module,provider_name+'_callback')('code','state',db)
        field='instance_url' if provider_name=='salesforce' else 'cloud_id'
        results[provider_name]={'platform_config_changed':app.config[field] != ('https://original.example.invalid' if provider_name=='salesforce' else 'original-cloud'),'shared_permission_checks':permission.await_count,'commits':db.commit.await_count,'shared_token_unchanged':app.access_token=='unchanged-shared-token'}
    print(json.dumps(results,indent=2))

asyncio.run(main())
