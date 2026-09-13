"""
Human Contacts Controller

API endpoints for managing human team members that agents can escalate to.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.services.roles.human_contact_service import HumanContactService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/human-contacts", tags=["human-contacts"])


# Request/Response Models


class CreateContactRequest(BaseModel):
    """Request model for creating a contact."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr | None = None
    slack_user_id: str | None = Field(None, max_length=100)
    slack_workspace_id: str | None = Field(None, max_length=100)
    whatsapp_number: str | None = Field(None, max_length=50)
    account_id: str | None = None
    preferred_channel: str = Field(default="email", pattern="^(email|slack|whatsapp)$")
    timezone: str = Field(default="UTC", max_length=100)
    notification_preferences: str = Field(default="all", pattern="^(all|urgent_only|none)$")


class UpdateContactRequest(BaseModel):
    """Request model for updating a contact."""

    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    slack_user_id: str | None = Field(None, max_length=100)
    slack_workspace_id: str | None = Field(None, max_length=100)
    whatsapp_number: str | None = Field(None, max_length=50)
    account_id: str | None = None
    preferred_channel: str | None = Field(None, pattern="^(email|slack|whatsapp)$")
    timezone: str | None = Field(None, max_length=100)
    notification_preferences: str | None = Field(None, pattern="^(all|urgent_only|none)$")
    is_active: bool | None = None


class ContactResponse(BaseModel):
    """Response model for a contact."""

    id: str
    name: str
    email: str | None
    slack_user_id: str | None
    slack_workspace_id: str | None
    whatsapp_number: str | None
    account_id: str | None
    preferred_channel: str
    timezone: str | None
    notification_preferences: str
    is_active: bool
    available_channels: list[str]
    created_at: str
    updated_at: str


# Endpoints


@router.get("", response_model=list[ContactResponse])
async def list_contacts(
    active_only: bool = Query(True, description="Only return active contacts"),
    search: str | None = Query(None, description="Search by name or email"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all human contacts."""
    try:
        service = HumanContactService(db)
        contacts = await service.list_contacts(tenant_id=tenant_id, active_only=active_only, search=search)

        return [
            ContactResponse(
                id=str(contact.id),
                name=contact.name,
                email=contact.email,
                slack_user_id=contact.slack_user_id,
                slack_workspace_id=contact.slack_workspace_id,
                whatsapp_number=contact.whatsapp_number,
                account_id=str(contact.account_id) if contact.account_id else None,
                preferred_channel=contact.preferred_channel,
                timezone=contact.timezone,
                notification_preferences=contact.notification_preferences,
                is_active=contact.is_active,
                available_channels=contact.get_available_channels(),
                created_at=contact.created_at.isoformat() if contact.created_at else None,
                updated_at=contact.updated_at.isoformat() if contact.updated_at else None,
            )
            for contact in contacts
        ]
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ContactResponse, status_code=201)
async def create_contact(
    request: CreateContactRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new human contact."""
    try:
        service = HumanContactService(db)

        contact = await service.create_contact(
            tenant_id=tenant_id,
            name=request.name,
            email=request.email,
            slack_user_id=request.slack_user_id,
            slack_workspace_id=request.slack_workspace_id,
            whatsapp_number=request.whatsapp_number,
            account_id=UUID(request.account_id) if request.account_id else None,
            preferred_channel=request.preferred_channel,
            timezone=request.timezone,
            notification_preferences=request.notification_preferences,
        )

        return ContactResponse(
            id=str(contact.id),
            name=contact.name,
            email=contact.email,
            slack_user_id=contact.slack_user_id,
            slack_workspace_id=contact.slack_workspace_id,
            whatsapp_number=contact.whatsapp_number,
            account_id=str(contact.account_id) if contact.account_id else None,
            preferred_channel=contact.preferred_channel,
            timezone=contact.timezone,
            notification_preferences=contact.notification_preferences,
            is_active=contact.is_active,
            available_channels=contact.get_available_channels(),
            created_at=contact.created_at.isoformat() if contact.created_at else None,
            updated_at=contact.updated_at.isoformat() if contact.updated_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get a specific contact."""
    try:
        service = HumanContactService(db)
        contact = await service.get_contact(UUID(contact_id))

        if not contact or contact.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Contact not found")

        return ContactResponse(
            id=str(contact.id),
            name=contact.name,
            email=contact.email,
            slack_user_id=contact.slack_user_id,
            slack_workspace_id=contact.slack_workspace_id,
            whatsapp_number=contact.whatsapp_number,
            account_id=str(contact.account_id) if contact.account_id else None,
            preferred_channel=contact.preferred_channel,
            timezone=contact.timezone,
            notification_preferences=contact.notification_preferences,
            is_active=contact.is_active,
            available_channels=contact.get_available_channels(),
            created_at=contact.created_at.isoformat() if contact.created_at else None,
            updated_at=contact.updated_at.isoformat() if contact.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    request: UpdateContactRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a contact."""
    try:
        service = HumanContactService(db)

        update_data = request.model_dump(exclude_unset=True)

        # Convert account_id to UUID if present
        if "account_id" in update_data and update_data["account_id"]:
            update_data["account_id"] = UUID(update_data["account_id"])

        contact = await service.update_contact(contact_id=UUID(contact_id), tenant_id=tenant_id, **update_data)

        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        return ContactResponse(
            id=str(contact.id),
            name=contact.name,
            email=contact.email,
            slack_user_id=contact.slack_user_id,
            slack_workspace_id=contact.slack_workspace_id,
            whatsapp_number=contact.whatsapp_number,
            account_id=str(contact.account_id) if contact.account_id else None,
            preferred_channel=contact.preferred_channel,
            timezone=contact.timezone,
            notification_preferences=contact.notification_preferences,
            is_active=contact.is_active,
            available_channels=contact.get_available_channels(),
            created_at=contact.created_at.isoformat() if contact.created_at else None,
            updated_at=contact.updated_at.isoformat() if contact.updated_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Delete a contact."""
    try:
        service = HumanContactService(db)

        success = await service.delete_contact(contact_id=UUID(contact_id), tenant_id=tenant_id)

        if not success:
            raise HTTPException(status_code=404, detail="Contact not found")

        return None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{contact_id}/deactivate", response_model=ContactResponse)
async def deactivate_contact(
    contact_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Deactivate a contact instead of deleting."""
    try:
        service = HumanContactService(db)

        contact = await service.deactivate_contact(contact_id=UUID(contact_id), tenant_id=tenant_id)

        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        return ContactResponse(
            id=str(contact.id),
            name=contact.name,
            email=contact.email,
            slack_user_id=contact.slack_user_id,
            slack_workspace_id=contact.slack_workspace_id,
            whatsapp_number=contact.whatsapp_number,
            account_id=str(contact.account_id) if contact.account_id else None,
            preferred_channel=contact.preferred_channel,
            timezone=contact.timezone,
            notification_preferences=contact.notification_preferences,
            is_active=contact.is_active,
            available_channels=contact.get_available_channels(),
            created_at=contact.created_at.isoformat() if contact.created_at else None,
            updated_at=contact.updated_at.isoformat() if contact.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contact ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating contact: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
