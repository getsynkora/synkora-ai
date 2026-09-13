"""Tenant-scoped SCIM provisioning; global login identity is never mutable through SCIM."""

import hashlib
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scim_membership import SCIMMembership
from src.models.scim_token import SCIMToken
from src.models.tenant import Account, AccountRole, AccountStatus, TenantAccountJoin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SCIM schema URNs
# ---------------------------------------------------------------------------
_SCHEMA_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
_SCHEMA_LIST = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
_SCHEMA_ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a plaintext SCIM token."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_scim_token() -> tuple[str, str]:
    """
    Generate a new SCIM bearer token.

    Returns:
        (plaintext, token_hash) — store only the hash; show plaintext once.
    """
    plaintext = secrets.token_urlsafe(32)
    return plaintext, _hash_token(plaintext)


# ---------------------------------------------------------------------------
# SCIM resource serialisers
# ---------------------------------------------------------------------------


def _account_to_scim(account: Account, tenant_id: uuid.UUID) -> dict:
    """Serialise an Account instance to a SCIM 2.0 User resource dict."""
    active = account.status == AccountStatus.ACTIVE
    created_iso = account.created_at.isoformat() if account.created_at else datetime.now(UTC).isoformat()
    updated_iso = account.updated_at.isoformat() if account.updated_at else created_iso
    return {
        "schemas": [_SCHEMA_USER],
        "id": str(account.id),
        "externalId": str(account.id),
        "userName": account.email,
        "name": {
            "formatted": account.name,
            "givenName": account.name.split(" ", 1)[0] if account.name else "",
            "familyName": account.name.split(" ", 1)[1] if account.name and " " in account.name else "",
        },
        "displayName": account.name,
        "emails": [
            {
                "value": account.email,
                "primary": True,
                "type": "work",
            }
        ],
        "active": active,
        "meta": {
            "resourceType": "User",
            "created": created_iso,
            "lastModified": updated_iso,
            "location": f"/scim/v2/Users/{account.id}",
        },
    }


def _parse_name(scim_data: dict) -> str:
    """Extract a display name string from a SCIM User payload."""
    name_obj = scim_data.get("name", {})
    if name_obj.get("formatted"):
        return name_obj["formatted"]
    given = name_obj.get("givenName", "")
    family = name_obj.get("familyName", "")
    full = f"{given} {family}".strip()
    if full:
        return full
    # Fall back to userName (email prefix)
    username = scim_data.get("userName", "")
    return username.split("@")[0] if "@" in username else username


# ---------------------------------------------------------------------------
# Filter parser — only supports: userName eq "value"
# ---------------------------------------------------------------------------

_FILTER_RE = re.compile(r'^userName\s+eq\s+"([^"]+)"$', re.IGNORECASE)


def _apply_filter(query, filter_str: str | None):
    """Apply a basic SCIM filter to a SQLAlchemy Account query."""
    if not filter_str:
        return query
    m = _FILTER_RE.match(filter_str.strip())
    if m:
        email_value = m.group(1)
        return query.filter(Account.email == email_value)
    # Unsupported filter — return unmodified (caller should handle 400 if strict)
    logger.warning("Unsupported SCIM filter ignored: %s", filter_str)
    return query


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


async def validate_scim_token(db: AsyncSession, token: str) -> SCIMToken | None:
    """
    Validate a SCIM bearer token.

    Hashes the incoming plaintext, looks it up, and updates last_used_at on hit.

    Args:
        db: Async database session
        token: Plaintext bearer token from the Authorization header

    Returns:
        SCIMToken if valid and active, None otherwise
    """
    token_hash = _hash_token(token)
    result = await db.execute(
        select(SCIMToken).filter(SCIMToken.token_hash == token_hash, SCIMToken.is_active.is_(True))
    )
    scim_token = result.scalar_one_or_none()
    if scim_token:
        scim_token.touch()
        await db.commit()
    return scim_token


# ---------------------------------------------------------------------------
# SCIM User operations
# ---------------------------------------------------------------------------


def _resources(tenant_id):
    return (
        select(Account, SCIMMembership, TenantAccountJoin)
        .outerjoin(SCIMMembership, and_(SCIMMembership.account_id == Account.id, SCIMMembership.tenant_id == tenant_id))
        .outerjoin(
            TenantAccountJoin,
            and_(TenantAccountJoin.account_id == Account.id, TenantAccountJoin.tenant_id == tenant_id),
        )
        .where(or_(SCIMMembership.id.isnot(None), TenantAccountJoin.id.isnot(None)))
    )


def _resource(account, profile, membership, tenant_id):
    data = _account_to_scim(account, tenant_id)
    data["active"] = membership is not None and account.status == AccountStatus.ACTIVE
    if profile and profile.display_name is not None:
        name = profile.display_name
        data["displayName"] = name
        data["name"] = {
            "formatted": name,
            "givenName": name.split(" ", 1)[0],
            "familyName": name.split(" ", 1)[1] if " " in name else "",
        }
    return data


async def _locked_resource(db, tenant_id, user_id):
    try:
        user_id = uuid.UUID(str(user_id))
    except ValueError:
        return None
    # Serialize lifecycle changes without locking nullable outer-join rows.
    await db.execute(
        select(Account.id)
        .where(Account.id == user_id, Account.id.in_(_resources(tenant_id).with_only_columns(Account.id)))
        .with_for_update()
    )
    result = await db.execute(_resources(tenant_id).where(Account.id == user_id))
    return result.first()


async def list_users(db, tenant_id, start_index=1, count=100, filter_str=None):
    count = max(0, min(count, 200))
    query = _apply_filter(_resources(tenant_id), filter_str)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    rows = (await db.execute(query.order_by(Account.id).offset(max(start_index - 1, 0)).limit(count))).all()
    return {
        "schemas": [_SCHEMA_LIST],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(rows),
        "Resources": [_resource(*row, tenant_id) for row in rows],
    }


async def get_user(db, tenant_id, scim_user_id):
    try:
        user_id = uuid.UUID(scim_user_id)
    except ValueError:
        return None
    row = (await db.execute(_resources(tenant_id).where(Account.id == user_id))).first()
    return _resource(*row, tenant_id) if row else None


async def create_user(db, tenant_id, scim_data):
    if not isinstance(scim_data, dict) or not isinstance(scim_data.get("userName", ""), str):
        raise ValueError("userName must be a string")
    email = scim_data.get("userName", "").strip().lower()
    if not email:
        raise ValueError("userName is required")
    active = scim_data.get("active", True)
    if not isinstance(active, bool):
        raise ValueError("active must be a boolean")
    account = (await db.execute(select(Account).where(Account.email == email))).scalar_one_or_none()
    if account is not None:
        # An email match does not authorize attaching an existing global identity.
        raise ValueError(
            "User cannot be provisioned; use the verified membership/invitation flow for existing accounts"
        )
    name = _parse_name(scim_data) or email.split("@")[0]
    account = Account(name=name, email=email, status=AccountStatus.ACTIVE, auth_provider="scim")
    db.add(account)
    await db.flush()
    profile = SCIMMembership(
        tenant_id=tenant_id, account_id=account.id, display_name=name, role=AccountRole.NORMAL.value
    )
    db.add(profile)
    membership = None
    if active:
        membership = TenantAccountJoin(tenant_id=tenant_id, account_id=account.id, role=AccountRole.NORMAL)
        db.add(membership)
    await db.commit()
    await db.refresh(account)
    return _resource(account, profile, membership, tenant_id)


def _validate_fields(account, values):
    allowed = {"username", "active", "name", "displayname", "externalid", "emails", "schemas", "id", "meta"}
    if not isinstance(values, dict) or any(not isinstance(k, str) or k.lower() not in allowed for k in values):
        raise ValueError("Unsupported SCIM fields")
    values = {key.lower(): value for key, value in values.items()}
    if "username" in values and (
        not isinstance(values["username"], str) or values["username"].strip().lower() != account.email.lower()
    ):
        raise ValueError("SCIM cannot change global login identity")
    if "emails" in values:
        emails = values["emails"]
        if not isinstance(emails, list) or any(
            not isinstance(e, dict)
            or not isinstance(e.get("value"), str)
            or e["value"].lower() != account.email.lower()
            for e in emails
        ):
            raise ValueError("SCIM cannot change global login identity")
    if "active" in values and not isinstance(values["active"], bool):
        raise ValueError("active must be a boolean")
    name = values.get("displayname")
    if "name" in values:
        if not isinstance(values["name"], dict):
            raise ValueError("name must be an object")
        name = _parse_name({"name": values["name"]})
    if name is not None and (not isinstance(name, str) or len(name) > 255):
        raise ValueError("Invalid display name")
    return values.get("active"), name


async def _apply_local(db, tenant_id, row, active, name):
    account, profile, membership = row
    if profile is None:
        profile = SCIMMembership(
            tenant_id=tenant_id, account_id=account.id, display_name=account.name, role=membership.role.value
        )
        db.add(profile)
    if name is not None:
        profile.display_name = name
    if active is False and membership is not None:
        profile.role = membership.role.value
        profile.membership_attributes = {
            "role_id": str(membership.role_id) if membership.role_id else None,
            "custom_permissions": membership.custom_permissions,
            "invited_by": str(membership.invited_by) if membership.invited_by else None,
            "joined_at": membership.joined_at,
        }
        await db.delete(membership)
        membership = None
    elif active is True and membership is None:
        saved = profile.membership_attributes or {}
        membership = TenantAccountJoin(
            tenant_id=tenant_id,
            account_id=account.id,
            role=AccountRole(profile.role),
            role_id=uuid.UUID(saved["role_id"]) if saved.get("role_id") else None,
            custom_permissions=saved.get("custom_permissions"),
            invited_by=uuid.UUID(saved["invited_by"]) if saved.get("invited_by") else None,
            joined_at=saved.get("joined_at"),
        )
        db.add(membership)
    await db.commit()
    return _resource(account, profile, membership, tenant_id)


async def update_user(db, tenant_id, scim_user_id, scim_data):
    row = await _locked_resource(db, tenant_id, scim_user_id)
    if row is None:
        return None
    active, name = _validate_fields(row[0], scim_data)
    return await _apply_local(db, tenant_id, row, True if active is None else active, name)


async def patch_user(db, tenant_id, scim_user_id, patch_ops):
    row = await _locked_resource(db, tenant_id, scim_user_id)
    if row is None:
        return None
    active, name = None, None
    # Validate every operation before changing any persistent object.
    for op in patch_ops:
        if not isinstance(op, dict) or str(op.get("op", "")).lower() not in {"add", "replace"}:
            raise ValueError("Unsupported SCIM operation")
        path = str(op.get("path") or "").lower()
        value = op.get("value")
        if path in {"name.givenname", "name.familyname"}:
            if not isinstance(value, str):
                raise ValueError("Invalid name")
            current = name if name is not None else (row[1].display_name if row[1] else row[0].name) or ""
            parts = current.split(" ", 1)
            value = {
                "givenName": value if path.endswith("givenname") else parts[0],
                "familyName": value if path.endswith("familyname") else (parts[1] if len(parts) > 1 else ""),
            }
            path = "name"
        next_active, next_name = _validate_fields(row[0], {path: value} if path else value)
        if next_active is not None:
            active = next_active
        if next_name is not None:
            name = next_name
    return await _apply_local(db, tenant_id, row, active, name)


async def delete_user(db, tenant_id, scim_user_id):
    row = await _locked_resource(db, tenant_id, scim_user_id)
    if row is None:
        return False
    _, profile, membership = row
    if membership is not None:
        await db.delete(membership)
    if profile is not None:
        await db.delete(profile)
    # Live membership checks revoke only this tenant's access. Other sessions survive.
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Token management helpers (used by the admin management API)
# ---------------------------------------------------------------------------


async def create_scim_token(
    db: AsyncSession, tenant_id: uuid.UUID, description: str | None = None
) -> tuple[str, SCIMToken]:
    """
    Create a new SCIM token for tenant_id.

    Args:
        db: Async database session
        tenant_id: Tenant scope
        description: Optional human-readable label

    Returns:
        (plaintext_token, SCIMToken record) — store only the record; show plaintext once
    """
    plaintext, token_hash = generate_scim_token()
    token = SCIMToken(
        tenant_id=tenant_id,
        token_hash=token_hash,
        description=description,
        is_active=True,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return plaintext, token


async def list_scim_tokens(db: AsyncSession, tenant_id: uuid.UUID) -> list[SCIMToken]:
    """List all SCIM tokens for tenant_id (no plaintext)."""
    result = await db.execute(
        select(SCIMToken).filter(SCIMToken.tenant_id == tenant_id).order_by(SCIMToken.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_scim_token(db: AsyncSession, tenant_id: uuid.UUID, token_id: uuid.UUID) -> bool:
    """
    Revoke (deactivate) a SCIM token.

    Args:
        db: Async database session
        tenant_id: Tenant scope
        token_id: UUID of the SCIMToken to revoke

    Returns:
        True if found and revoked, False if not found / wrong tenant
    """
    result = await db.execute(select(SCIMToken).filter(SCIMToken.id == token_id, SCIMToken.tenant_id == tenant_id))
    token = result.scalar_one_or_none()
    if not token:
        return False
    token.is_active = False
    await db.commit()
    return True
