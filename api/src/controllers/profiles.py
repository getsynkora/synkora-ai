"""
Profile management controller
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account
from src.services.profile.profile_service import ProfileService
from src.services.security.password_validator import PasswordValidator

logger = logging.getLogger(__name__)


def _fmt_dt(val: Any) -> str | None:
    """Return ISO-format string from a datetime or an already-string timestamp."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


# SECURITY: Maximum allowed avatar file size (5MB)
MAX_AVATAR_SIZE = 5 * 1024 * 1024

# SECURITY: Allowed image MIME types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# SECURITY: Magic bytes for image file validation
# This prevents attackers from uploading malicious files with spoofed Content-Type
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",  # JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",  # PNG
    b"GIF87a": "image/gif",  # GIF87a
    b"GIF89a": "image/gif",  # GIF89a
    b"RIFF": "image/webp",  # WebP (partial, followed by WEBP)
}


def _validate_image_magic_bytes(content: bytes) -> str | None:
    """
    Validate image file by checking magic bytes.

    SECURITY: This prevents malicious file uploads with spoofed Content-Type headers.

    Args:
        content: File content bytes

    Returns:
        Detected MIME type if valid image, None otherwise
    """
    for magic, mime_type in IMAGE_MAGIC_BYTES.items():
        if content.startswith(magic):
            # Special handling for WebP - check for WEBP signature after RIFF
            if magic == b"RIFF" and len(content) >= 12:
                if content[8:12] == b"WEBP":
                    return mime_type
            else:
                return mime_type
    return None


router = APIRouter(prefix="/profile", tags=["profile"])


# Pydantic models for request/response
class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None, pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    phone: str | None = Field(None, max_length=20)
    bio: str | None = Field(None, max_length=500)
    company: str | None = Field(None, max_length=255)
    job_title: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=255)
    notification_preferences: dict | None = None


class PasswordChange(BaseModel):
    """Password change request with strong password policy."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        is_valid, error_msg = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class TwoFactorEnable(BaseModel):
    password: str = Field(..., min_length=8)


class TwoFactorVerify(BaseModel):
    token: str = Field(..., min_length=6, max_length=6)


class ProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None
    bio: str | None
    company: str | None
    job_title: str | None
    location: str | None
    website: str | None
    avatar_url: str | None
    two_factor_enabled: bool
    is_platform_admin: bool
    notification_preferences: dict
    last_login_at: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_url: str


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)):
    """Get current user's profile"""
    try:
        profile_service = ProfileService(db)
        profile = await profile_service.get_profile(current_account.id)

        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        # Convert to dict with proper serialization
        return {
            "id": str(profile.id),
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "bio": profile.bio,
            "company": profile.company,
            "job_title": profile.job_title,
            "location": profile.location,
            "website": profile.website,
            "avatar_url": profile.avatar_url,
            "two_factor_enabled": profile.two_factor_enabled or False,
            "is_platform_admin": profile.is_platform_admin or False,
            "notification_preferences": profile.notification_preferences or {},
            "last_login_at": _fmt_dt(profile.last_login_at),
            "created_at": _fmt_dt(profile.created_at),
            "updated_at": _fmt_dt(profile.updated_at),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get profile")


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate, current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Update current user's profile"""
    try:
        profile_service = ProfileService(db)

        update_data = profile_data.model_dump(exclude_unset=True)

        # notification_preferences is handled by a separate service method
        notification_preferences = update_data.pop("notification_preferences", None)

        updated_profile = await profile_service.update_profile(current_account.id, **update_data)

        if updated_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        if notification_preferences is not None:
            updated_profile = await profile_service.update_notification_preferences(
                current_account.id, notification_preferences
            )

        # Convert to dict with proper serialization
        return {
            "id": str(updated_profile.id),
            "name": updated_profile.name,
            "email": updated_profile.email,
            "phone": updated_profile.phone,
            "bio": updated_profile.bio,
            "company": updated_profile.company,
            "job_title": updated_profile.job_title,
            "location": updated_profile.location,
            "website": updated_profile.website,
            "avatar_url": updated_profile.avatar_url,
            "two_factor_enabled": updated_profile.two_factor_enabled or False,
            "is_platform_admin": updated_profile.is_platform_admin or False,
            "notification_preferences": updated_profile.notification_preferences or {},
            "last_login_at": _fmt_dt(updated_profile.last_login_at),
            "created_at": _fmt_dt(updated_profile.created_at),
            "updated_at": _fmt_dt(updated_profile.updated_at),
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update profile")


@router.post("/me/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...), current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Upload profile avatar"""
    try:
        # Read file content
        contents = file.file.read()

        # SECURITY: Validate file size
        if len(contents) > MAX_AVATAR_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File size must be less than 5MB"
            )

        # SECURITY: Validate content type header
        if not file.content_type or file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )

        # SECURITY: Validate actual file content via magic bytes
        # This prevents malicious files with spoofed Content-Type headers
        detected_mime = _validate_image_magic_bytes(contents)
        if not detected_mime:
            logger.warning(f"Avatar upload rejected - invalid magic bytes for user {current_account.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file. File content does not match a supported image format.",
            )

        # SECURITY: Verify Content-Type matches actual file content
        if file.content_type != detected_mime:
            logger.warning(
                f"Avatar Content-Type mismatch for user {current_account.id}: "
                f"claimed={file.content_type}, detected={detected_mime}"
            )

        profile_service = ProfileService(db)
        updated_profile = await profile_service.upload_avatar(
            current_account.id, contents, file.filename or "avatar.jpg"
        )

        # Convert to dict with proper serialization
        return {
            "id": str(updated_profile.id),
            "name": updated_profile.name,
            "email": updated_profile.email,
            "phone": updated_profile.phone,
            "bio": updated_profile.bio,
            "company": updated_profile.company,
            "job_title": updated_profile.job_title,
            "location": updated_profile.location,
            "website": updated_profile.website,
            "avatar_url": updated_profile.avatar_url,
            "two_factor_enabled": updated_profile.two_factor_enabled or False,
            "is_platform_admin": updated_profile.is_platform_admin or False,
            "notification_preferences": updated_profile.notification_preferences or {},
            "last_login_at": _fmt_dt(updated_profile.last_login_at),
            "created_at": _fmt_dt(updated_profile.created_at),
            "updated_at": _fmt_dt(updated_profile.updated_at),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload avatar")


@router.delete("/me/avatar", response_model=ProfileResponse)
async def delete_avatar(current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)):
    """Delete profile avatar"""
    try:
        profile_service = ProfileService(db)
        updated_profile = await profile_service.delete_avatar(current_account.id)

        # Convert to dict with proper serialization
        return {
            "id": str(updated_profile.id),
            "name": updated_profile.name,
            "email": updated_profile.email,
            "phone": updated_profile.phone,
            "bio": updated_profile.bio,
            "company": updated_profile.company,
            "job_title": updated_profile.job_title,
            "location": updated_profile.location,
            "website": updated_profile.website,
            "avatar_url": updated_profile.avatar_url,
            "two_factor_enabled": updated_profile.two_factor_enabled or False,
            "is_platform_admin": updated_profile.is_platform_admin or False,
            "notification_preferences": updated_profile.notification_preferences or {},
            "last_login_at": _fmt_dt(updated_profile.last_login_at),
            "created_at": _fmt_dt(updated_profile.created_at),
            "updated_at": _fmt_dt(updated_profile.updated_at),
        }

    except Exception as e:
        logger.error(f"Error deleting avatar: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete avatar")


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: PasswordChange,
    current_account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Change user password"""
    try:
        profile_service = ProfileService(db)
        await profile_service.change_password(
            current_account.id, password_data.current_password, password_data.new_password
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to change password")


@router.post("/me/2fa/enable", response_model=TwoFactorSetupResponse)
async def enable_two_factor(
    request: TwoFactorEnable, current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Initiate two-factor authentication setup — returns secret + QR code URL for scanning."""
    try:
        import pyotp

        from src.services.auth_service import AuthService

        # Verify the user's current password before showing the 2FA secret
        if not AuthService.verify_password(request.password, current_account.password_hash or ""):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password")

        # Generate a new TOTP secret
        secret = pyotp.random_base32()

        # Build otpauth:// URI for QR code scanners (e.g. Google Authenticator)
        issuer = "Synkora"
        totp = pyotp.TOTP(secret)
        qr_code_url = totp.provisioning_uri(name=current_account.email, issuer_name=issuer)

        # Store the pending secret (user must verify with /2fa/verify before 2FA is activated)
        profile_service = ProfileService(db)
        await profile_service.enable_two_factor(current_account.id, secret)

        return {"secret": secret, "qr_code_url": qr_code_url}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error enabling 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable two-factor authentication"
        )


# SECURITY: Track 2FA verification attempts to prevent brute force
_2fa_attempts: dict[str, list[float]] = {}
_2FA_MAX_ATTEMPTS = 5
_2FA_WINDOW_SECONDS = 300  # 5 minutes


def _check_2fa_rate_limit(account_id: str) -> bool:
    """Check if account has exceeded 2FA verification rate limit."""
    import time

    global _2fa_attempts

    now = time.time()
    key = str(account_id)

    # PERFORMANCE: Evict stale entries when dict grows too large to prevent
    # unbounded memory growth from many unique account IDs over time.
    if len(_2fa_attempts) > 10000:
        _2fa_attempts = {
            k: [t for t in v if now - t < _2FA_WINDOW_SECONDS]
            for k, v in _2fa_attempts.items()
            if any(now - t < _2FA_WINDOW_SECONDS for t in v)
        }

    if key not in _2fa_attempts:
        _2fa_attempts[key] = []

    # Clean old attempts
    _2fa_attempts[key] = [t for t in _2fa_attempts[key] if now - t < _2FA_WINDOW_SECONDS]

    # Check limit
    if len(_2fa_attempts[key]) >= _2FA_MAX_ATTEMPTS:
        return False

    # Record attempt
    _2fa_attempts[key].append(now)
    return True


@router.post("/me/2fa/verify", response_model=ProfileResponse)
async def verify_two_factor(
    request: TwoFactorVerify, current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Verify and complete two-factor authentication setup"""
    try:
        # SECURITY: Rate limit 2FA verification attempts to prevent brute force
        if not _check_2fa_rate_limit(current_account.id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification attempts. Please wait 5 minutes before trying again.",
            )

        profile_service = ProfileService(db)
        is_valid = await profile_service.verify_two_factor(current_account.id, request.token)

        if not is_valid:
            raise ValueError("Invalid or expired TOTP code")

        # 2FA verified — enable it on the account and generate backup codes
        from sqlalchemy import select as _select

        from src.models.tenant import Account as _Account
        from src.services.auth_service import AuthService as _AuthService

        _result = await db.execute(_select(_Account).where(_Account.id == current_account.id))
        updated_profile = _result.scalar_one_or_none()
        if not updated_profile:
            raise ValueError("Account not found")

        # If not yet enabled, enable it now (verify step completes the setup)
        if not updated_profile.two_factor_enabled:
            updated_profile.two_factor_enabled = "true"
            await db.commit()
            await db.refresh(updated_profile)

        # Generate backup codes — returned once and must be saved by the user
        backup_codes = await _AuthService.generate_backup_codes(updated_profile.id, db)

        # Convert to dict with proper serialization
        return {
            "id": str(updated_profile.id),
            "name": updated_profile.name,
            "email": updated_profile.email,
            "phone": updated_profile.phone,
            "bio": updated_profile.bio,
            "company": updated_profile.company,
            "job_title": updated_profile.job_title,
            "location": updated_profile.location,
            "website": updated_profile.website,
            "avatar_url": updated_profile.avatar_url,
            "two_factor_enabled": updated_profile.two_factor_enabled or False,
            "is_platform_admin": updated_profile.is_platform_admin or False,
            "notification_preferences": updated_profile.notification_preferences or {},
            "last_login_at": _fmt_dt(updated_profile.last_login_at),
            "created_at": _fmt_dt(updated_profile.created_at),
            "updated_at": _fmt_dt(updated_profile.updated_at),
            "backup_codes": backup_codes,  # Plaintext — shown once, must be saved
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to verify two-factor authentication"
        )


# ---------------------------------------------------------------------------
# Session management endpoints
# ---------------------------------------------------------------------------


@router.get("/me/sessions")
async def list_sessions(
    request: Request,
    current_account=Depends(get_current_account),
) -> dict[str, Any]:
    """List active sessions for the current account.

    Returns all active refresh-token families stored in Redis, each with
    available metadata (creation time, last-used time, IP, user-agent).
    The current session is identified by matching the family ID embedded in
    the request's Authorization token.
    """
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if not redis:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session store unavailable",
            )

        account_id = str(current_account.id)

        # Discover all family keys: refresh:family:{account_id}:*
        pattern = f"refresh:family:{account_id}:*"
        cursor = 0
        family_keys: list[str] = []
        while True:
            cursor, keys = redis.scan(cursor, match=pattern, count=200)
            family_keys.extend(k.decode() if isinstance(k, bytes) else k for k in keys)
            if cursor == 0:
                break

        # Determine current family_id from the JWT in the Authorization header
        current_family_id: str | None = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.services.auth_service import AuthService

                payload = AuthService.decode_token(auth_header[7:])
                current_family_id = payload.get("fid")
            except Exception:
                pass

        sessions: list[dict[str, Any]] = []
        for key in family_keys:
            # key format: refresh:family:{account_id}:{family_id}
            parts = key.split(":")
            if len(parts) < 4:
                continue
            family_id = parts[3]

            # Retrieve session creation timestamp
            ts_key = f"session:created:{account_id}:{family_id}"
            ts_raw = redis.get(ts_key)
            created_at: str | None = None
            if ts_raw:
                try:
                    from datetime import UTC, datetime

                    ts = float(ts_raw.decode() if isinstance(ts_raw, bytes) else ts_raw)
                    created_at = datetime.fromtimestamp(ts, tz=UTC).isoformat()
                except Exception:
                    pass

            # Retrieve per-session metadata (ip, user-agent) if stored
            meta_key = f"session:meta:{account_id}:{family_id}"
            meta_raw = redis.get(meta_key)
            meta: dict[str, Any] = {}
            if meta_raw:
                try:
                    import json

                    meta = json.loads(meta_raw.decode() if isinstance(meta_raw, bytes) else meta_raw)
                except Exception:
                    pass

            sessions.append(
                {
                    "session_id": family_id,
                    "created_at": created_at,
                    "last_used_at": meta.get("last_used_at"),
                    "ip_address": meta.get("ip_address"),
                    "user_agent": meta.get("user_agent"),
                    "is_current": family_id == current_family_id,
                }
            )

        return {"sessions": sessions, "total": len(sessions)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing sessions for account %s: %s", current_account.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions",
        )


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    request: Request,
    current_account=Depends(get_current_account),
):
    """Revoke a specific session (refresh-token family) by its family ID.

    The current session is NOT protected from self-revocation — the caller
    should avoid passing their own session_id if they want to stay logged in.
    """
    try:
        from src.services.security.token_blacklist import get_token_blacklist_service

        blacklist_service = get_token_blacklist_service()
        blacklist_service.invalidate_refresh_token_family(current_account.id, session_id)
        logger.info(
            "Session %s revoked by account %s (remote revocation)",
            session_id,
            current_account.id,
        )

    except Exception as e:
        logger.error("Error revoking session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session",
        )


@router.delete("/me/sessions")
async def revoke_all_other_sessions(
    request: Request,
    current_account=Depends(get_current_account),
) -> dict[str, Any]:
    """Revoke all sessions except the current one.

    Returns the count of revoked sessions.
    """
    try:
        from src.config.redis import get_redis
        from src.services.security.token_blacklist import get_token_blacklist_service

        redis = get_redis()
        if not redis:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session store unavailable",
            )

        account_id = str(current_account.id)

        # Identify the current family
        current_family_id: str | None = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.services.auth_service import AuthService

                payload = AuthService.decode_token(auth_header[7:])
                current_family_id = payload.get("fid")
            except Exception:
                pass

        # Scan all family keys
        pattern = f"refresh:family:{account_id}:*"
        cursor = 0
        family_keys: list[str] = []
        while True:
            cursor, keys = redis.scan(cursor, match=pattern, count=200)
            family_keys.extend(k.decode() if isinstance(k, bytes) else k for k in keys)
            if cursor == 0:
                break

        blacklist_service = get_token_blacklist_service()
        revoked = 0
        for key in family_keys:
            parts = key.split(":")
            if len(parts) < 4:
                continue
            family_id = parts[3]
            if family_id == current_family_id:
                continue  # Keep the current session
            blacklist_service.invalidate_refresh_token_family(current_account.id, family_id)
            revoked += 1

        logger.info(
            "Revoked %d other sessions for account %s",
            revoked,
            current_account.id,
        )
        return {"revoked": revoked}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error revoking other sessions for account %s: %s", current_account.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions",
        )


@router.post("/me/2fa/disable", response_model=ProfileResponse)
async def disable_two_factor(current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)):
    """Disable two-factor authentication"""
    try:
        profile_service = ProfileService(db)
        updated_profile = await profile_service.disable_two_factor(current_account.id)

        # Convert to dict with proper serialization
        return {
            "id": str(updated_profile.id),
            "name": updated_profile.name,
            "email": updated_profile.email,
            "phone": updated_profile.phone,
            "bio": updated_profile.bio,
            "company": updated_profile.company,
            "job_title": updated_profile.job_title,
            "location": updated_profile.location,
            "website": updated_profile.website,
            "avatar_url": updated_profile.avatar_url,
            "two_factor_enabled": updated_profile.two_factor_enabled or False,
            "is_platform_admin": updated_profile.is_platform_admin or False,
            "notification_preferences": updated_profile.notification_preferences or {},
            "last_login_at": _fmt_dt(updated_profile.last_login_at),
            "created_at": _fmt_dt(updated_profile.created_at),
            "updated_at": _fmt_dt(updated_profile.updated_at),
        }

    except Exception as e:
        logger.error(f"Error disabling 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable two-factor authentication"
        )


@router.post("/me/2fa/backup-codes", status_code=status.HTTP_200_OK)
async def regenerate_backup_codes(
    current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Regenerate 2FA backup/recovery codes. Previous codes are invalidated."""
    try:
        if not current_account.two_factor_enabled or current_account.two_factor_enabled == "false":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled",
            )

        from src.services.auth_service import AuthService as _AuthService

        codes = await _AuthService.generate_backup_codes(current_account.id, db)
        return {
            "backup_codes": codes,
            "message": "New backup codes generated. Save these — they will not be shown again.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating backup codes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to regenerate backup codes"
        )


@router.get("/me/2fa/backup-codes", status_code=status.HTTP_200_OK)
async def get_backup_codes_status(
    current_account=Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """Return how many backup codes remain (not the codes themselves)."""
    try:
        from sqlalchemy import select as _select

        from src.models import Account as _Account

        result = await db.execute(_select(_Account).filter_by(id=current_account.id))
        account = result.scalar_one_or_none()
        stored = account.two_factor_backup_codes if account else None
        count = len(stored) if isinstance(stored, list) else 0
        return {
            "remaining_codes": count,
            "two_factor_enabled": bool(
                account and account.two_factor_enabled and account.two_factor_enabled != "false"
            ),
        }

    except Exception as e:
        logger.error(f"Error getting backup codes status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get backup codes status"
        )
