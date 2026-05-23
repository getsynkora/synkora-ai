"""
Portal Schemas

Pydantic models for portal configuration requests and responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class PortalSocialLinks(BaseModel):
    twitter: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class PortalBrandingConfig(BaseModel):
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    font_family: str | None = None
    site_title: str | None = Field(default=None, max_length=120)
    tagline: str | None = Field(default=None, max_length=240)
    footer_text: str | None = Field(default=None, max_length=500)
    social_links: PortalSocialLinks | None = None


class PortalSEOConfig(BaseModel):
    meta_description: str | None = Field(default=None, max_length=320)
    og_image_url: str | None = None


class TenantPortalResponse(BaseModel):
    id: str
    tenant_id: str
    portal_enabled: bool
    subdomain: str | None
    portal_domain: str | None
    branding_config: dict[str, Any] | None
    featured_agent_slugs: list[str] | None
    seo_config: dict[str, Any] | None
    created_at: str
    updated_at: str


class PortalAgentResponse(BaseModel):
    slug: str
    agent_name: str
    description: str | None
    avatar: str | None
    category: str | None
    tags: list[str] | None
    suggestion_prompts: list[Any] | None
    portal_visibility: str


class PortalConfigResponse(BaseModel):
    portal_enabled: bool
    subdomain: str | None
    branding_config: dict[str, Any] | None
    seo_config: dict[str, Any] | None
    featured_agents: list[PortalAgentResponse]


class UpdatePortalSettingsBody(BaseModel):
    portal_enabled: bool | None = None
    portal_domain: str | None = None
    branding_config: PortalBrandingConfig | None = None
    featured_agent_slugs: list[str] | None = None
    seo_config: PortalSEOConfig | None = None
