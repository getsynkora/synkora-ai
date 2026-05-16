"""
BrainDomain model — tenant-owned domain groupings for Company Brain.

A domain is a named, weighted grouping of DataSource records that defines
one knowledge silo of the company. Any company can define any domains they
need — there are no hardcoded domain names in the codebase.

Examples:
  Deriv:     internal, trading, cs, acquisition, compliance
  Acme Corp: engineering, sales, support
  Hospital:  clinical, admin, research

Two permissions are auto-created when a domain is created (via the service
layer, not a DB trigger), using the existing permissions/roles tables:
  brain.{slug}.query  — can search this domain
  brain.{slug}.admin  — can configure / manage this domain
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class BrainDomain(BaseModel):
    """Tenant-configurable Company Brain domain."""

    __tablename__ = "brain_domains"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_brain_domain_tenant_slug"),)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning tenant",
    )

    name = Column(
        String(120),
        nullable=False,
        comment="Human-readable domain name, e.g. 'Trading' or 'Engineering'",
    )

    slug = Column(
        String(80),
        nullable=False,
        index=True,
        comment="URL/permission-safe identifier, e.g. 'trading'. Unique per tenant.",
    )

    description = Column(
        Text,
        nullable=True,
        comment="What this domain covers — passed to the LLM query classifier as context",
    )

    rerank_weight = Column(
        Float,
        nullable=False,
        default=1.0,
        comment="Multiplier applied to result scores from this domain (>1 boosts, <1 demotes)",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Inactive domains are excluded from all queries",
    )

    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="The KnowledgeBase that IS this domain's storage layer. "
        "Query routing resolves: domain → KB → data sources.",
    )

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[knowledge_base_id])
    data_sources = relationship(
        "DataSource",
        back_populates="brain_domain",
        foreign_keys="DataSource.brain_domain_id",
    )

    def __repr__(self) -> str:
        return f"<BrainDomain(id={self.id}, slug='{self.slug}', tenant_id={self.tenant_id})>"

    @property
    def query_permission(self) -> str:
        """Permission name for querying this domain."""
        return f"brain.{self.slug}.query"

    @property
    def admin_permission(self) -> str:
        """Permission name for administering this domain."""
        return f"brain.{self.slug}.admin"
