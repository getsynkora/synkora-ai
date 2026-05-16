"""Pydantic schemas for Company Brain domain management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BrainDomainCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Human-readable domain name")
    slug: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$", description="URL-safe slug")
    description: str | None = Field(None, description="Shown to the LLM classifier as context")
    rerank_weight: float = Field(1.0, ge=0.1, le=10.0, description="Result score multiplier")
    is_active: bool = True
    knowledge_base_id: int | None = Field(None, description="The KnowledgeBase this domain represents")

    @field_validator("slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower()


class BrainDomainUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    rerank_weight: float | None = Field(None, ge=0.1, le=10.0)
    is_active: bool | None = None
    knowledge_base_id: int | None = None


class BrainDomainResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    description: str | None
    rerank_weight: float
    is_active: bool
    knowledge_base_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignDataSourceBody(BaseModel):
    """Assign / unassign a data source to/from a domain."""

    data_source_id: int
    domain_id: UUID | None = Field(None, description="None to unassign")
