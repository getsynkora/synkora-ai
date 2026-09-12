"""Local diagnostic probes; synthetic tokens, mocked DB/Redis/provider, no network."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY="review-only-synthetic-key-0123456789abcdef", JWT_SECRET_KEY="review-only-synthetic-key-0123456789abcdef", ENCRYPTION_KEY=Fernet.generate_key().decode(), CELERY_BROKER_URL="redis://localhost:6379/15", CELERY_RESULT_BACKEND="redis://localhost:6379/15")
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.auth_service import AuthService
from src.middleware.agent_api_auth import get_tenant_from_jwt_or_api_key
from src.controllers.agents import chat
from src.controllers.oauth import github
from src.models import AccountStatus

async def main():
    account_id, tenant_id = uuid4(), uuid4()
    results = {}
    with patch('src.services.auth_service.settings.jwt_secret_key', 'review-only-synthetic-key-0123456789abcdef'):
        token = AuthService.generate_access_token(account_id, tenant_id, auth_version=0)
        db = AsyncMock()
        accepted = await get_tenant_from_jwt_or_api_key('Bearer ' + token, db)
        results['handoff'] = {'tenant_accepted': accepted == tenant_id, 'database_checks': db.execute.await_count}
        account = SimpleNamespace(id=account_id, status=AccountStatus.ACTIVE, auth_version=1)
        ws = AsyncMock()
        ws.receive_json.side_effect = [{'type':'auth','token':token}, chat.WebSocketDisconnect()]
        redis = MagicMock(); redis.pipeline.return_value.execute = AsyncMock(return_value=[False, b'0'])
        auth_db = AsyncMock(); auth_db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda:account)
        factory = MagicMock(); factory.return_value.__aenter__ = AsyncMock(return_value=auth_db)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch.object(chat,'get_redis_async',return_value=redis), patch.object(chat,'get_async_session_factory',return_value=factory):
            await chat.chat_websocket(ws)
        results['websocket'] = {'stale_account_version_accepted': any(c.args[0].get('type')=='auth_ok' for c in ws.send_json.await_args_list), 'database_queries':auth_db.execute.await_count}
    app = SimpleNamespace(id=12, tenant_id=tenant_id, is_platform_app=False, auth_method='oauth', client_id='synthetic', client_secret='synthetic', redirect_uri='https://example.invalid/callback', scopes=['repo'], access_token='original')
    db = AsyncMock(); db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda:app)
    provider = MagicMock(); provider.get_authorization_url.return_value='https://example.invalid/authorize'
    provider.get_access_token=AsyncMock(return_value='attacker-provider-token'); provider.get_user_info=AsyncMock(return_value={'id':1,'login':'synthetic-attacker'})
    state = {}
    def save_state(data): state.update(data); return 'synthetic-state'
    with patch.object(github,'GitHubOAuth',return_value=provider), patch.object(github,'decrypt_value',side_effect=lambda x:x), patch.object(github,'encrypt_value',side_effect=lambda x:'encrypted:'+x), patch.object(github,'get_app_base_url',new=AsyncMock(return_value='https://example.invalid')), patch.object(github,'create_oauth_state',side_effect=save_state), patch.object(github,'get_oauth_state',return_value=state):
        response = await github.github_authorize(oauth_app_id=12,redirect_url=None,user_level=False,current_account=None,tenant_id=None,db=db)
        await github.github_callback(code='synthetic-provider-code',state='synthetic-state',db=db)
    results['oauth']={'anonymous_start_status':response.status_code,'state_has_account':bool(state['account_id']),'foreign_app_token_replaced':app.access_token=='encrypted:attacker-provider-token','commits':db.commit.await_count}
    print(json.dumps(results,indent=2))

asyncio.run(main())
