"""
Agent Domains Controller

API endpoints for managing agent custom domains and chat page customization.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.schemas.agent_domain import (
    AgentDomainCreate,
    AgentDomainResponse,
    AgentDomainUpdate,
    DNSRecordsResponse,
    DNSVerificationResponse,
)
from src.services.domains.dns_service import DNSService
from src.services.domains.domain_resolver import DomainResolver
from src.services.domains.domain_service import DomainService

router = APIRouter(prefix="/api/v1/agents/{agent_slug}/domains", tags=["agent-domains"])

# Public domain resolution router (no auth required)
public_router = APIRouter(prefix="/api/domains", tags=["domain-resolution"])


async def _get_agent_by_name(db: AsyncSession, agent_slug: str, tenant_id: uuid.UUID) -> Agent:
    """Helper function to get agent by slug."""
    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")
    return agent


@router.get("", response_model=list[AgentDomainResponse])
async def list_agent_domains(
    agent_slug: str, tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """List all domains for an agent."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)

    domains = await domain_service.list_domains(agent_id=agent.id, tenant_id=tenant_id)
    return domains


@router.post("", response_model=AgentDomainResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_domain(
    agent_slug: str,
    domain_data: AgentDomainCreate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new domain for an agent."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)

    try:
        domain = await domain_service.create_domain(
            agent_id=agent.id,
            tenant_id=tenant_id,
            subdomain=domain_data.subdomain,
            custom_domain=domain_data.domain,
            chat_page_config=domain_data.chat_page_config,
        )
        return domain
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{domain_id}", response_model=AgentDomainResponse)
async def get_agent_domain(
    agent_slug: str,
    domain_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific domain."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)

    domain = await domain_service.get_domain(domain_id=domain_id, tenant_id=tenant_id)

    if not domain or domain.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    return domain


@router.put("/{domain_id}", response_model=AgentDomainResponse)
async def update_agent_domain(
    agent_slug: str,
    domain_id: uuid.UUID,
    domain_data: AgentDomainUpdate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a domain."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)

    # Verify domain belongs to agent
    domain = await domain_service.get_domain(domain_id=domain_id, tenant_id=tenant_id)

    if not domain or domain.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    try:
        updated_domain = await domain_service.update_domain(
            domain_id=domain_id,
            tenant_id=tenant_id,
            subdomain=domain_data.subdomain,
            custom_domain=domain_data.domain,
            is_custom_domain=domain_data.is_custom_domain,
            chat_page_config=domain_data.chat_page_config,
        )
        return updated_domain
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_domain(
    agent_slug: str,
    domain_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a domain."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)

    # Verify domain belongs to agent
    domain = await domain_service.get_domain(domain_id=domain_id, tenant_id=tenant_id)

    if not domain or domain.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    await domain_service.delete_domain(domain_id=domain_id, tenant_id=tenant_id)


@router.get("/{domain_id}/dns-records", response_model=DNSRecordsResponse)
async def get_required_dns_records(
    agent_slug: str,
    domain_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get required DNS records for domain setup."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)
    dns_service = DNSService(db)

    domain = await domain_service.get_domain(domain_id=domain_id, tenant_id=tenant_id)

    if not domain or domain.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    if not domain.is_custom_domain or not domain.domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a custom domain")

    records = await dns_service.get_required_dns_records(
        custom_domain=domain.domain, subdomain=domain.subdomain, verification_token=domain.verification_token
    )

    from src.config.settings import settings

    return {"records": records, "platform_domain": settings.platform_domain}


@router.post("/{domain_id}/verify", response_model=DNSVerificationResponse)
async def verify_domain_dns(
    agent_slug: str,
    domain_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Verify DNS configuration for a custom domain."""
    agent = await _get_agent_by_name(db, agent_slug, tenant_id)
    domain_service = DomainService(db)
    dns_service = DNSService(db)

    domain = await domain_service.get_domain(domain_id=domain_id, tenant_id=tenant_id)

    if not domain or domain.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    # Check if domain is a custom domain
    if not domain.is_custom_domain or not domain.domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This is not a custom domain that requires verification"
        )

    is_verified, error_message = await dns_service.verify_custom_domain(domain_id=domain_id, tenant_id=tenant_id)

    if is_verified:
        # Update domain verification status
        await domain_service.verify_domain(domain_id=domain_id, tenant_id=tenant_id)
        return {"is_verified": True, "message": "Domain verified successfully"}
    else:
        # Mark verification as failed
        await domain_service.mark_verification_failed(
            domain_id=domain_id, tenant_id=tenant_id, error_message=error_message or "DNS verification failed"
        )

        # Return detailed error with domain info for debugging
        return {
            "is_verified": False,
            "message": error_message or "DNS verification failed",
            "details": {
                "domain": domain.domain,
                "subdomain": domain.subdomain,
                "verification_method": domain.verification_method,
                "error": error_message,
            },
        }


@public_router.get("/resolve")
async def resolve_current_domain(
    request: Request,
    hostname: str | None = None,
    agent_slug: str | None = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Resolve domain or agent_slug to agent and configuration.
    Used by custom domain chat pages and direct agent access.
    No authentication required - public endpoint.

    Query Parameters:
        hostname: Optional hostname to resolve (e.g., 'product-owner.synkora.ai')
        agent_slug: Optional agent slug to resolve (e.g., 'product-owner-agent')
    """
    resolver = DomainResolver(db)
    agent = None
    resolved_hostname = hostname

    # If hostname is provided in query param, use it
    if hostname:
        agent = await resolver.resolve_agent_from_domain(hostname)
    # If agent_slug is provided, resolve by slug
    elif agent_slug:
        agent = await resolver.resolve_agent_by_slug(agent_slug)
        resolved_hostname = None
    # Otherwise, try to get hostname from request headers
    # In Kubernetes/proxy environments, check X-Forwarded-Host first
    # This preserves the original domain name from the client
    else:
        # Check forwarded headers first (for proxy/ingress scenarios)
        forwarded_host = request.headers.get("X-Forwarded-Host")
        original_host = request.headers.get("X-Original-Host")
        host_header = request.headers.get("host", "")

        # Prefer forwarded headers over direct host header
        resolved_hostname = None
        if forwarded_host:
            resolved_hostname = forwarded_host.split(":")[0].split(",")[0].strip()
        elif original_host:
            resolved_hostname = original_host.split(":")[0].split(",")[0].strip()
        elif host_header:
            resolved_hostname = host_header.split(":")[0]

        if resolved_hostname:
            agent = await resolver.resolve_agent_from_domain(resolved_hostname)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No agent found for this domain or agent name"
        )

    # Get configuration
    config = await resolver.get_chat_config(str(agent.id), resolved_hostname)

    return {
        "agent_id": str(agent.id),
        "agent_name": agent.agent_name,
        "agent_type": agent.agent_type,
        "description": agent.description or "",
        "domain": resolved_hostname or "direct",
        "chat_page_config": config,
    }
