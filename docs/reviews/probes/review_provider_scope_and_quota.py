"""Synthetic local reproductions; no production credentials or network requests."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef',JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef',ENCRYPTION_KEY=Fernet.generate_key().decode(),CELERY_BROKER_URL='redis://localhost:6379/15',CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from src.controllers.agents.tools import save_agent_tool, SaveAgentToolRequest
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.models.user_oauth_token import UserOAuthToken
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.security import encrypt_value
from src.services.agent_api.api_key_service import AgentApiKeyService

async def main():
    output={}
    tenant,foreign_tenant,user,other_user,agent=[uuid4() for _ in range(5)]
    db=AsyncMock()
    db.add=MagicMock()
    db.execute.side_effect=[SimpleNamespace(scalar_one_or_none=lambda:SimpleNamespace(id=agent,tenant_id=tenant)),SimpleNamespace(scalar_one_or_none=lambda:None)]
    response=await save_agent_tool(str(agent),SaveAgentToolRequest(tool_name='gitlab_test',oauth_app_id=912,config={}),SimpleNamespace(id=user),tenant,db)
    output['foreign_connection_assignment']={'accepted':response.success,'saved_oauth_app_id':db.add.call_args.args[0].oauth_app_id,'database_lookups':db.execute.await_count}
    for mode in ('foreign_app','other_member'):
        app=SimpleNamespace(id=912,tenant_id=foreign_tenant if mode=='foreign_app' else tenant,is_platform_app=False,config={},client_id=None,client_secret=None,auth_method='oauth',access_token=encrypt_value('foreign-app-token') if mode=='foreign_app' else None,token_expires_at=None,app_name='Synthetic provider')
        token=UserOAuthToken(account_id=other_user,oauth_app_id=912)
        token.access_token='other-member-token'
        db=AsyncMock(); personal_queries=[]; app_queries=[]
        async def execute(stmt):
            entity=stmt.column_descriptions[0]['entity']
            if entity is AgentTool:value=SimpleNamespace(oauth_app_id=912)
            elif entity is OAuthApp:
                app_queries.append(stmt);value=app
            else:
                personal_queries.append(stmt)
                value=token if mode=='other_member' and len(personal_queries)==2 else None
            return SimpleNamespace(scalar_one_or_none=lambda:value)
        db.execute.side_effect=execute
        context=SimpleNamespace(user_id=user,tenant_id=tenant,agent_id=agent,db_session=db)
        result=await CredentialResolver(context).get_gitlab_token('gitlab_test',retry_refresh=False)
        output[mode]={'unexpected_token_returned':result[0]==('foreign-app-token' if mode=='foreign_app' else 'other-member-token'),'app_query_scoped_to_tenant':tenant in app_queries[0].compile().params.values(),'fallback_scoped_to_current_account':user in personal_queries[-1].compile().params.values()}
    workers=8
    class RedisModel:
        def __init__(self):self.data={};self.barrier=Barrier(workers);self.lock=Lock()
        def zremrangebyscore(self,*args):pass
        def zcard(self,key):
            with self.lock:count=len(self.data.get(key,{}))
            self.barrier.wait(timeout=10)
            return count
        def zadd(self,key,mapping):
            with self.lock:self.data.setdefault(key,{}).update(mapping)
        def expire(self,*args):pass
    redis=RedisModel()
    key=SimpleNamespace(rate_limit_per_minute=1,rate_limit_per_hour=1,rate_limit_per_day=1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(lambda n:AgentApiKeyService._check_rate_limit_redis(redis,'synthetic-key',1000+n/1000,key),range(workers)))
    output['concurrent_quota']={'configured_limit':1,'concurrent_requests':workers,'accepted':sum(allowed for allowed,_ in results)}
    print(json.dumps(output,indent=2))

asyncio.run(main())
