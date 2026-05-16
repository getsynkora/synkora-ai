"""
Console authentication endpoints.

Handles login, registration, token refresh, and logout.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.database import get_async_db
from src.middleware import get_current_account
from src.models import Account
from src.schemas.base import StrictModel
from src.services import AuthService, SessionService
from src.services.security.password_validator import PasswordValidator, check_hibp
from src.utils.config_helper import get_app_base_url

logger = logging.getLogger(__name__)

# Cookie security settings — driven by the canonical APP_ENV setting, not a
# separate ENVIRONMENT variable that could be mismatched in production.
COOKIE_SECURE = settings.is_production
COOKIE_DOMAIN = settings.cookie_domain if hasattr(settings, "cookie_domain") else None

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(min_length=6)
    two_factor_token: str | None = Field(default=None, min_length=6, max_length=6)  # TOTP code
    temp_token: str | None = None  # Required when submitting two_factor_token


class RegisterRequest(StrictModel):
    """Registration request schema with strong password policy."""

    email: EmailStr
    password: str = Field(max_length=128)
    name: str = Field(min_length=1, max_length=100)
    tenant_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        is_valid, error_msg = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class RefreshRequest(BaseModel):
    """Token refresh request schema.

    refresh_token is optional — the preferred path is the HttpOnly cookie
    set by the login endpoint.  The body field is accepted as a fallback
    (e.g. mobile clients that cannot use cookies).
    """

    refresh_token: str | None = None
    tenant_id: str | None = None  # Optional tenant ID to preserve context


@router.post("/login")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Login endpoint.

    Args:
        request: HTTP request (used for IP extraction and audit logging)
        data: Login credentials
        db: Database session

    Returns:
        Authentication tokens and user information
        If 2FA is enabled, returns requires_2fa: true and a temporary token
    """
    from src.services.activity.activity_log_service import ActivityLogService
    from src.utils.ip_utils import get_client_ip

    client_ip = get_client_ip(
        request.client.host if request.client else "",
        request.headers.get("x-forwarded-for"),
        request.headers.get("x-real-ip"),
    )
    user_agent = request.headers.get("user-agent", "")

    # Authenticate user
    try:
        account = await AuthService.authenticate(db, data.email, data.password)
    except ValueError as e:
        # SECURITY: Account is locked due to too many failed attempts
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    if not account:
        # Audit: log failed login attempt (best-effort — don't fail the response)
        try:
            from sqlalchemy import select as _select

            from src.models import Account as _Account

            _result = await db.execute(_select(_Account).filter_by(email=data.email))
            _acct = _result.scalar_one_or_none()
            if _acct:
                _log_svc = ActivityLogService(db)
                await _log_svc.log_activity(
                    tenant_id=None,
                    account_id=_acct.id,
                    action="login_failed",
                    resource_type="account",
                    details={"ip": client_ip, "user_agent": user_agent},
                    ip_address=client_ip,
                    user_agent=user_agent,
                )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # SECURITY: Enforce SAML SSO — if any tenant this account belongs to has an
    # active force_saml config, password-based login must be rejected regardless
    # of credential validity.  This check runs before 2FA and before token
    # issuance to prevent bypass.
    try:
        from src.models.saml_config import SAMLConfig
        from src.models.tenant import TenantAccountJoin

        saml_result = await db.execute(
            select(SAMLConfig)
            .join(TenantAccountJoin, TenantAccountJoin.tenant_id == SAMLConfig.tenant_id)
            .filter(
                TenantAccountJoin.account_id == account.id,
                SAMLConfig.is_active.is_(True),
                SAMLConfig.force_saml.is_(True),
            )
            .limit(1)
        )
        if saml_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "saml_required",
                    "message": "This organization requires SAML SSO. Please sign in via your identity provider.",
                },
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error checking SAML config during login for account %s", account.id)

    # SECURITY: Admin-enforced 2FA — if any tenant this account belongs to has
    # mfa_required=true, reject login if the account has no TOTP configured.
    try:
        from src.models.tenant import Tenant as _Tenant
        from src.models.tenant import TenantAccountJoin as _TAJ

        _mfa_result = await db.execute(
            select(_Tenant)
            .join(_TAJ, _TAJ.tenant_id == _Tenant.id)
            .filter(
                _TAJ.account_id == account.id,
                _Tenant.mfa_required == "true",
            )
            .limit(1)
        )
        _mfa_tenant = _mfa_result.scalar_one_or_none()
        if _mfa_tenant is not None:
            _acct_2fa_enabled = getattr(account, "two_factor_enabled", False)
            _acct_2fa_secret = getattr(account, "two_factor_secret", None)
            if not (_acct_2fa_enabled and _acct_2fa_secret):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "mfa_setup_required",
                        "message": "Your organization requires two-factor authentication. Please set up 2FA before logging in.",
                    },
                )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error checking tenant mfa_required during login for account %s", account.id)

    # SECURITY: Check if 2FA is enabled AND configured for this account
    # Only require 2FA if both the flag is set AND the secret exists
    # SECURITY FIX: Removed ENFORCE_2FA bypass - 2FA cannot be bypassed via environment variable
    two_factor_enabled = getattr(account, "two_factor_enabled", False)
    two_factor_secret = getattr(account, "two_factor_secret", None)

    if two_factor_enabled and two_factor_secret:
        # If 2FA token not provided, return partial response requiring 2FA
        if not data.two_factor_token:
            # Generate a temporary token for 2FA flow (expires in 5 minutes)
            import json
            import secrets

            temp_token = secrets.token_urlsafe(32)

            # SECURITY: Store 2FA pending tokens in Redis - no fallback
            from src.config.redis import get_redis_async

            redis_client = get_redis_async()
            if not redis_client:
                logger.warning("SECURITY: Redis unavailable for 2FA token storage")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable. Please try again later.",
                )

            # Store with 5 minute TTL
            await redis_client.setex(
                f"2fa_pending:{temp_token}",
                300,  # 5 minutes TTL
                json.dumps({"account_id": str(account.id)}),
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": False,
                    "requires_2fa": True,
                    "temp_token": temp_token,
                    "message": "Two-factor authentication required",
                },
            )
        else:
            # Verify 2FA token — requires the temp_token issued in the first step
            import json

            import pyotp

            from src.config.redis import get_redis_async

            redis_client = get_redis_async()
            if not redis_client:
                logger.warning("SECURITY: Redis unavailable for 2FA verification")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable. Please try again later.",
                )

            # Require temp_token — prevents skipping the challenge step
            if not data.temp_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="temp_token is required for two-factor authentication",
                )

            pending_key = f"2fa_pending:{data.temp_token}"
            pending_data = await redis_client.getdel(pending_key)
            if not pending_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Two-factor session expired or invalid. Please log in again.",
                )

            pending = json.loads(pending_data)
            if pending.get("account_id") != str(account.id):
                # Token/account mismatch — reject (token already consumed by getdel above)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid two-factor session.",
                )

            # Rate-limit TOTP attempts per temp_token (max 5)
            attempts_key = f"2fa_attempts:{data.temp_token}"
            attempt_count = await redis_client.incr(attempts_key)
            await redis_client.expire(attempts_key, 300)  # Expire with the session

            if attempt_count > 5:
                await redis_client.delete(attempts_key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many two-factor attempts. Please log in again.",
                )

            totp = pyotp.TOTP(two_factor_secret)
            if not totp.verify(data.two_factor_token, valid_window=1):
                # TOTP failed — try backup codes as fallback
                backup_valid = await AuthService.consume_backup_code(account.id, data.two_factor_token, db)
                if not backup_valid:
                    # SECURITY AUDIT: log every MFA failure for alerting / brute-force detection
                    try:
                        from src.services.activity.activity_log_service import ActivityLogService

                        _mfa_fail_tenant_id = None
                        from sqlalchemy import select as _sel_mfa

                        from src.models.tenant import TenantAccountJoin as _TAJ_mfa

                        _mfa_res = await db.execute(_sel_mfa(_TAJ_mfa).filter_by(account_id=account.id))
                        _mfa_mem = _mfa_res.scalar_one_or_none()
                        if _mfa_mem:
                            _mfa_fail_tenant_id = _mfa_mem.tenant_id

                        _mfa_svc = ActivityLogService(db)
                        await _mfa_svc.log_activity(
                            tenant_id=_mfa_fail_tenant_id,
                            account_id=account.id,
                            action="mfa_failed",
                            resource_type="account",
                            resource_id=account.id,
                        )
                    except Exception as _mfa_audit_exc:
                        logger.warning(f"Failed to write mfa_failed audit log: {_mfa_audit_exc}")

                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid two-factor authentication code"
                    )

            # TOTP or backup code verified — pending token already consumed atomically by getdel above
            await redis_client.delete(attempts_key)

    # Get user's tenants
    tenants = await AuthService.get_account_tenants(db, account.id)

    # SECURITY: Enforce 2FA for ADMIN/OWNER roles (opt-in via REQUIRE_2FA_FOR_ADMIN=true).
    # Disabled by default to avoid locking out fresh deployments and test environments.
    from src.config import settings as _settings
    from src.models.tenant import AccountRole as _AccountRole

    if _settings.require_2fa_for_admin and not (two_factor_enabled and two_factor_secret):
        privileged_roles = {_AccountRole.ADMIN.value, _AccountRole.OWNER.value}
        if any(t["role"] in privileged_roles for t in tenants):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "2fa_required_for_role",
                    "message": "Two-factor authentication is required for admin accounts. Please enable 2FA before logging in.",
                },
            )

    # Create session with first tenant (or None if no tenants)
    tenant_id = tenants[0]["tenant_id"] if tenants else None
    session_data = await SessionService.create_session(db, account, tenant_id)

    # Audit: persist IP and user-agent to account record for audit trail.
    # Also check whether this is a new-IP login and fire a background notification.
    try:
        from datetime import UTC
        from datetime import datetime as _datetime
        from datetime import timedelta as _timedelta

        prev_ip = getattr(account, "last_login_ip", None)
        prev_login_at_str = getattr(account, "last_login_at", None)

        _now = _datetime.now(UTC)
        account.last_login_ip = client_ip
        account.last_login_at = _now.isoformat()
        await db.commit()

        # Fire new-login notification when:
        #  - IP has changed, AND
        #  - Last login was more than 1 hour ago (avoids spurious noise for
        #    round-trip refreshes from the same session)
        if prev_ip and prev_ip != client_ip:
            _fire_notification = True
            if prev_login_at_str:
                try:
                    _prev_dt = _datetime.fromisoformat(prev_login_at_str)
                    if _prev_dt.tzinfo is None:
                        _prev_dt = _prev_dt.replace(tzinfo=UTC)
                    if (_now - _prev_dt) < _timedelta(hours=1):
                        _fire_notification = False
                except Exception:
                    pass
            if _fire_notification:
                try:
                    from src.tasks.email_tasks import send_new_login_notification

                    send_new_login_notification.delay(
                        str(account.id),
                        client_ip,
                        user_agent,
                        _now.isoformat(),
                    )
                except Exception:
                    pass
    except Exception:
        pass

    # Build response data
    response_data = {
        "success": True,
        "data": {
            **session_data,
            "account": {
                "id": str(account.id),
                "email": account.email,
                "name": account.name,
                "status": account.status,
            },
            "tenants": tenants,
        },
        "message": "Login successful",
    }

    # Audit: log successful login (best-effort — don't fail the response)
    try:
        _log_svc = ActivityLogService(db)
        _tenant_id_for_log = tenants[0]["tenant_id"] if tenants else None
        import uuid as _uuid

        await _log_svc.log_activity(
            tenant_id=_uuid.UUID(_tenant_id_for_log) if _tenant_id_for_log else None,
            account_id=account.id,
            action="login_success",
            resource_type="account",
            details={"ip": client_ip, "user_agent": user_agent},
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except Exception:
        pass

    # Store the refresh token in an HttpOnly cookie so JS cannot read it (XSS-safe).
    # Scoped to the refresh endpoint only — the browser never sends it on normal API calls.
    # The access token is returned in the response body and kept in JS memory by the SPA.
    response = JSONResponse(content=response_data)
    # SECURITY: Prevent auth tokens from being stored in any cache layer.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.set_cookie(
        key="refresh_token",
        value=session_data["refresh_token"],
        httponly=True,  # JS-unreachable — XSS cannot steal the refresh token
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=30 * 24 * 3600,  # 30 days — matches refresh token lifetime
        path="/console/api/auth/refresh",  # Sent only to the refresh endpoint
        domain=COOKIE_DOMAIN,
    )

    return response


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Registration endpoint.

    Args:
        data: Registration information
        db: Database session

    Returns:
        Authentication tokens and user information
    """
    try:
        # HIBP breach check — fail open if service is unreachable
        if await check_hibp(data.password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This password has appeared in a data breach. Please choose a different password.",
            )

        # Register user
        account, tenant = await AuthService.register(
            db,
            email=data.email,
            password=data.password,
            name=data.name,
            tenant_name=data.tenant_name,
        )

        # Send verification email asynchronously using Celery
        try:
            from src.tasks.email_tasks import send_verification_email_task

            # Get base URL from request or use default
            base_url = await get_app_base_url(db, tenant.id)

            # Queue email task asynchronously
            send_verification_email_task.delay(account_id=str(account.id), base_url=base_url)
            logger.info(f"Verification email task queued for account {account.id}")
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Failed to queue verification email: {e}")

        # Don't create session - user needs to verify email first
        # Build response without session tokens
        return {
            "success": True,
            "data": {
                "account": {
                    "id": str(account.id),
                    "email": account.email,
                    "name": account.name,
                    "status": account.status,
                },
                "tenant": {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "plan": tenant.plan,
                    "status": tenant.status,
                },
            },
            "message": "Registration successful. Please check your email to verify your account.",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/refresh")
async def refresh(request: Request, data: RefreshRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Token refresh endpoint.

    Accepts the refresh token from the HttpOnly cookie (preferred, browser clients)
    or from the request body (fallback for mobile / non-browser clients).

    Returns a new access token in the response body and rotates the refresh token
    cookie so the old one cannot be replayed.
    """
    try:
        # Cookie takes priority — JS cannot forge it (HttpOnly)
        refresh_token = request.cookies.get("refresh_token") or data.refresh_token
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is required",
            )

        tenant_id = None
        if data.tenant_id:
            import uuid

            tenant_id = uuid.UUID(data.tenant_id)

        session_data = await SessionService.refresh_session(db, refresh_token, tenant_id)

        response_data = {
            "success": True,
            "data": session_data,
            "message": "Token refreshed successfully",
        }

        # Rotate the refresh token cookie — old token is now invalid
        response = JSONResponse(content=response_data)
        # SECURITY: Prevent refreshed tokens from being stored in any cache layer.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.set_cookie(
            key="refresh_token",
            value=session_data["refresh_token"],
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="strict",
            max_age=30 * 24 * 3600,
            path="/console/api/auth/refresh",
            domain=COOKIE_DOMAIN,
        )

        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


@router.post("/logout")
async def logout(
    request: Request,
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Logout endpoint.

    Args:
        request: HTTP request (for IP and user-agent audit logging)
        current_account: Current authenticated account
        db: Database session

    Returns:
        Success message
    """
    # Revoke session
    await SessionService.revoke_session(db, current_account.id)

    # Audit: log logout (best-effort — never fail the response)
    try:
        from src.services.activity.activity_log_service import ActivityLogService
        from src.utils.ip_utils import get_client_ip

        _log_svc = ActivityLogService(db)
        await _log_svc.log_activity(
            tenant_id=None,
            account_id=current_account.id,
            action="logout",
            resource_type="account",
            details={
                "ip": get_client_ip(
                    request.client.host if request.client else "",
                    request.headers.get("x-forwarded-for"),
                    request.headers.get("x-real-ip"),
                ),
                "user_agent": request.headers.get("user-agent", ""),
            },
            ip_address=get_client_ip(
                request.client.host if request.client else "",
                request.headers.get("x-forwarded-for"),
                request.headers.get("x-real-ip"),
            ),
            user_agent=request.headers.get("user-agent", ""),
        )
    except Exception:
        pass

    # Clear the refresh token cookie
    response = JSONResponse(
        content={
            "success": True,
            "message": "Logout successful",
        }
    )
    response.delete_cookie(
        key="refresh_token",
        path="/console/api/auth/refresh",
        domain=COOKIE_DOMAIN,
    )

    return response


# Alias routes for frontend compatibility
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(data: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    """Alias for /register endpoint."""
    return await register(data, db)


@router.post("/signin")
async def signin(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    """Alias for /login endpoint."""
    return await login(request, data, db)


@router.get("/me")
async def get_current_user(
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get current user information.

    Args:
        current_account: Current authenticated account
        db: Database session

    Returns:
        User account and tenant information
    """
    import json

    from src.config.redis import get_redis_async

    cache_key = f"me:{current_account.id}"
    redis = get_redis_async()

    # Try Redis cache first (60s TTL — fresh enough for nav, fast on every page load)
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Get user's tenants
    tenants = await AuthService.get_account_tenants(db, current_account.id)

    result = {
        "success": True,
        "data": {
            "account": {
                "id": str(current_account.id),
                "email": current_account.email,
                "name": current_account.name,
                "status": current_account.status,
                "created_at": current_account.created_at.isoformat(),
            },
            "tenants": tenants,
        },
    }

    if redis:
        try:
            await redis.setex(cache_key, 60, json.dumps(result, default=str))
        except Exception:
            pass

    return result


class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password."""

    email: EmailStr


class ResetPasswordRequest(StrictModel):
    """Request model for reset password with strong password policy."""

    token: str
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        is_valid, error_msg = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class VerifyEmailRequest(BaseModel):
    """Request model for email verification."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Request model for resending verification email."""

    email: EmailStr


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Request a password reset email.

    Args:
        data: Forgot password request with email
        db: Database session

    Returns:
        Success message
    """
    result = await AuthService.request_password_reset(db, data.email)

    # Always return success to prevent email enumeration
    if result:
        from src.tasks.email_tasks import send_password_reset_email_task
        from src.utils.config_helper import get_app_base_url

        account, reset_token = result

        # Get base URL (tenant_id not needed; falls back to APP_BASE_URL env var)
        base_url = await get_app_base_url(db)

        # Queue password reset email asynchronously
        try:
            send_password_reset_email_task.delay(email=account.email, reset_token=reset_token, base_url=base_url)
            logger.info(f"Password reset email task queued for {account.email}")
        except Exception as e:
            logger.error(f"Failed to queue password reset email: {e}")

    return {
        "success": True,
        "message": "If the email exists, a password reset link has been sent.",
    }


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Reset password using a reset token.

    Args:
        data: Reset password request with token and new password
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    # HIBP breach check on new password — fail open if service is unreachable
    if await check_hibp(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This password has appeared in a data breach. Please choose a different password.",
        )

    account = await AuthService.reset_password(db, data.token, data.new_password)

    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    return {
        "success": True,
        "message": "Password has been reset successfully",
    }


@router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Verify email using a verification token.

    Args:
        data: Verify email request with token
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid
    """
    account = await AuthService.verify_email(db, data.token)

    if isinstance(account, dict) and account.get("error") == "verification_link_expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=account["message"])

    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token")

    return {
        "success": True,
        "message": "Email has been verified successfully",
        "data": {
            "account": {
                "id": str(account.id),
                "email": account.email,
                "name": account.name,
            }
        },
    }


@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Resend email verification link.

    Args:
        data: Resend verification request with email
        db: Database session

    Returns:
        Success message
    """
    # Find account by email
    result = await db.execute(select(Account).filter_by(email=data.email))
    account = result.scalar_one_or_none()

    if account and account.id:
        from src.tasks.email_tasks import send_verification_email_task

        # Get base URL (tenant_id not needed; falls back to APP_BASE_URL env var)
        base_url = await get_app_base_url(db)

        # Queue verification email asynchronously
        try:
            send_verification_email_task.delay(account_id=str(account.id), base_url=base_url)
            logger.info(f"Resend verification email task queued for account {account.id}")
        except Exception as e:
            logger.error(f"Failed to queue verification email: {e}")

    # Always return success to prevent email enumeration
    return {
        "success": True,
        "message": "If the email exists, a verification link has been sent.",
    }


# ── Chrome Extension PKCE Auth ────────────────────────────────────────────────


class ExtensionAuthorizeRequest(BaseModel):
    """Query parameters for the extension PKCE authorize endpoint."""

    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: str = Field(default="S256")
    state: str = Field(min_length=16, max_length=256)
    redirect_uri: str


class ExtensionTokenRequest(BaseModel):
    """Request body for the extension PKCE token exchange endpoint."""

    code: str
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str


_EXTENSION_CODE_TTL = 600  # 10 minutes


def _validate_redirect_uri(redirect_uri: str) -> None:
    """Allow chrome-extension:// and chromiumapp.org (launchWebAuthFlow) redirect URIs."""
    from urllib.parse import urlparse

    if redirect_uri.startswith("chrome-extension://"):
        return
    parsed = urlparse(redirect_uri)
    if parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".chromiumapp.org"):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="redirect_uri must use chrome-extension:// or chromiumapp.org scheme",
    )


@router.get("/extension/authorize")
async def extension_authorize(
    code_challenge: str,
    state: str,
    redirect_uri: str,
    code_challenge_method: str = "S256",
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    PKCE authorization endpoint for the Chrome extension.

    Requires an active session (Bearer token from the dashboard).
    Generates a short-lived auth code, stores challenge in Redis,
    and returns the code + state so the extension can complete the exchange.

    Security:
    - redirect_uri must be chrome-extension://
    - code_challenge_method must be S256
    - Auth code stored in Redis with 10-minute TTL
    - Code is single-use (deleted on exchange)
    """
    import hashlib
    import secrets

    _validate_redirect_uri(redirect_uri)

    if code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only S256 code_challenge_method is supported",
        )

    if len(code_challenge) < 43 or len(code_challenge) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code_challenge length",
        )

    from src.config.redis import get_redis_async

    redis_client = get_redis_async()
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service temporarily unavailable",
        )

    import json

    auth_code = secrets.token_urlsafe(48)
    await redis_client.setex(
        f"ext_auth_code:{auth_code}",
        _EXTENSION_CODE_TTL,
        json.dumps(
            {
                "account_id": str(account.id),
                "code_challenge": code_challenge,
                "redirect_uri": redirect_uri,
            }
        ),
    )

    logger.info("Extension auth code issued for account %s", account.id)
    return {"code": auth_code, "state": state}


@router.post("/extension/token")
async def extension_token(
    data: ExtensionTokenRequest,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    PKCE token exchange endpoint for the Chrome extension.

    Validates the auth code and code_verifier, issues JWT access + refresh tokens.

    Security:
    - Auth code is single-use (deleted from Redis immediately)
    - PKCE verification: sha256(code_verifier) must match stored code_challenge
    - redirect_uri must exactly match what was used in /authorize
    """
    import base64
    import hashlib
    import json

    from src.config.redis import get_redis_async

    _validate_redirect_uri(data.redirect_uri)

    redis_client = get_redis_async()
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service temporarily unavailable",
        )

    # Fetch and immediately delete the auth code (single-use)
    code_key = f"ext_auth_code:{data.code}"
    raw = await redis_client.getdel(code_key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code",
        )

    stored = json.loads(raw)

    # Validate redirect_uri matches
    if stored["redirect_uri"] != data.redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri mismatch",
        )

    # PKCE verification: sha256(code_verifier) must equal stored code_challenge
    digest = hashlib.sha256(data.code_verifier.encode()).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    if computed_challenge != stored["code_challenge"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE verification failed",
        )

    # Load account
    from uuid import UUID

    result = await db.execute(select(Account).filter(Account.id == UUID(stored["account_id"])))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found",
        )

    # Resolve tenant — same pattern as the login endpoint
    import uuid as _uuid

    tenants = await AuthService.get_account_tenants(db, account.id)
    tenant_id = _uuid.UUID(tenants[0]["tenant_id"]) if tenants else None

    session_data = await SessionService.create_session(db, account, tenant_id)

    logger.info("Extension tokens issued for account %s (tenant %s)", account.id, tenant_id)
    return {
        "access_token": session_data["access_token"],
        "refresh_token": session_data["refresh_token"],
        "token_type": "Bearer",
        "expires_in": session_data["expires_in"],
    }
