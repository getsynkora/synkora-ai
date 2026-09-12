"""Synthetic non-OAuth connection ownership probe; no external requests."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef',JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef',ENCRYPTION_KEY=Fernet.generate_key().decode(),CELERY_BROKER_URL='redis://localhost:6379/15',CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from src.controllers.agents.tools import save_agent_tool, SaveAgentToolRequest
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.security import encrypt_value
from src.services.custom_tools import ToolExecutor

async def main():
    tenant,foreign,agent,bot_id,tool_id=[uuid4() for _ in range(5)]
    db=AsyncMock();db.add=MagicMock()
    db.execute.side_effect=[SimpleNamespace(scalar_one_or_none=lambda:SimpleNamespace(id=agent,tenant_id=tenant)),SimpleNamespace(scalar_one_or_none=lambda:None)]
    response=await save_agent_tool(str(agent),SaveAgentToolRequest(tool_name='synthetic',config={},slack_bot_id=str(bot_id),custom_tool_id=str(tool_id),operation_id='read'),SimpleNamespace(id=uuid4()),tenant,db)
    saved=db.add.call_args.args[0]
    result={'assignment':{'accepted':response.success,'foreign_bot_id_saved':saved.slack_bot_id==bot_id,'foreign_tool_id_saved':saved.custom_tool_id==tool_id,'db_lookups':db.execute.await_count}}
    db=AsyncMock()
    bot=SimpleNamespace(id=bot_id,tenant_id=foreign,bot_name='Foreign',slack_bot_token=encrypt_value('foreign-slack'))
    db.execute.side_effect=[SimpleNamespace(scalar_one_or_none=lambda:SimpleNamespace(oauth_app_id=None,slack_bot_id=bot_id)),SimpleNamespace(scalar_one_or_none=lambda:bot)]
    token=await CredentialResolver(SimpleNamespace(tenant_id=tenant,agent_id=agent,user_id=None,db_session=db)).get_slack_token('synthetic')
    result['slack']={'foreign_token_returned':token=='foreign-slack','tenant_filtered':tenant in db.execute.call_args.args[0].compile().params.values()}
    schema={'openapi':'3.0.0','info':{'title':'Synthetic','version':'1'},'servers':[{'url':'https://example.invalid'}],'paths':{'/records':{'get':{'operationId':'read','responses':{'200':{'description':'ok'}}}}}}
    custom=SimpleNamespace(id=tool_id,tenant_id=foreign,name='Foreign',openapi_schema=schema,server_url='https://example.invalid',auth_type='bearer',auth_config={'token':encrypt_value('foreign-custom')})
    attached=SimpleNamespace(custom_tool_id=tool_id,operation_id='read',tool_name='synthetic',config={})
    db=AsyncMock();db.execute.side_effect=[SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:[attached])),SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:[custom]))]
    registry=object.__new__(ADKToolRegistry);registry.register_tool=MagicMock()
    executors=[]
    def executor_factory(*args,**kwargs):
        executor=ToolExecutor(*args,**kwargs);executors.append(executor);return executor
    with patch('src.services.custom_tools.ToolExecutor',side_effect=executor_factory):
        await registry.load_agent_custom_tools(str(agent),db)
    result['custom']={'registered':registry.register_tool.call_count==1,'foreign_auth_loaded':bool(executors and executors[0]._build_headers({}).get('Authorization')=='Bearer foreign-custom'),'tenant_filtered':tenant in db.execute.call_args.args[0].compile().params.values()}
    print(json.dumps(result,indent=2))

asyncio.run(main())
