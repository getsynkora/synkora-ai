"""Synthetic SCIM provisioning/account mutation; no network or production database."""
import os
from cryptography.fernet import Fernet
os.environ.update(SECRET_KEY='review-synthetic-key-0123456789abcdef',JWT_SECRET_KEY='review-synthetic-key-0123456789abcdef',ENCRYPTION_KEY=Fernet.generate_key().decode(),CELERY_BROKER_URL='redis://localhost:6379/15',CELERY_RESULT_BACKEND='redis://localhost:6379/15')
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from src.models.tenant import Account, AccountStatus, AccountRole, TenantAccountJoin
from src.services.scim_service import create_user, patch_user

async def main():
    attacker,victim_tenant,user=[uuid4() for _ in range(3)]
    account=Account(id=user,email='victim@example.invalid',name='Victim',status=AccountStatus.ACTIVE)
    memberships=[TenantAccountJoin(tenant_id=victim_tenant,account_id=user,role=AccountRole.OWNER)]
    db=AsyncMock();db.add=MagicMock(side_effect=memberships.append)
    async def execute(stmt):
        entity=stmt.column_descriptions[0]['entity'];params=list(stmt.compile().params.values())
        if entity is Account:
            if 'victim@example.invalid' in params:value=account
            else:value=account if user in params and any(row.tenant_id in params for row in memberships) else None
        else:value=next((row for row in memberships if row.tenant_id in params and row.account_id in params),None)
        return SimpleNamespace(scalar_one_or_none=lambda:value)
    db.execute.side_effect=execute
    result=await create_user(db,attacker,{'userName':'victim@example.invalid'})
    await patch_user(db,attacker,result['id'],[{'op':'replace','path':'userName','value':'attacker@example.invalid'},{'op':'replace','path':'active','value':False}])
    print(json.dumps({'existing_foreign_account_linked':result['id']==str(user),'global_email_changed':account.email=='attacker@example.invalid','global_account_disabled':account.status==AccountStatus.INACTIVE,'original_tenant_owner_membership_retained':any(row.tenant_id==victim_tenant and row.role==AccountRole.OWNER for row in memberships)},indent=2))

asyncio.run(main())
