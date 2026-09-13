"""
Debate Session model for AI War Room.

Stores multi-agent debate sessions with participants, messages, and configuration.
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel, TenantMixin


class DebateSession(BaseModel, TenantMixin):
    """A multi-agent debate session."""

    __tablename__ = "debate_sessions"

    topic = Column(Text, nullable=False, comment="The debate topic / question")
    debate_type = Column(String(50), nullable=False, default="structured", comment="structured or freeform")
    rounds = Column(Integer, nullable=False, default=3, comment="Total number of rounds")
    current_round = Column(Integer, nullable=False, default=0, comment="Current round number")
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        comment="pending, active, synthesizing, completed, error",
    )
    is_public = Column(Boolean, nullable=False, default=False, comment="Whether publicly viewable")
    allow_external = Column(Boolean, nullable=False, default=False, comment="Whether external agents can join")
    share_token = Column(String(64), nullable=True, unique=True, index=True, comment="Token for public share URL")
    participants = Column(
        JSON,
        nullable=False,
        default=list,
        comment="List of participant configs [{id, agent_id, agent_name, role, is_external, color}]",
    )
    messages = Column(
        JSON,
        nullable=False,
        default=list,
        comment="Debate messages [{id, participant_id, agent_name, round, content, is_verdict, created_at}]",
    )
    external_responses = Column(JSON, nullable=False, default=dict, server_default="{}")
    synthesizer_agent_id = Column(UUID(as_uuid=True), nullable=True, comment="Agent ID for synthesizing verdict")
    verdict = Column(Text, nullable=True, comment="Final synthesized verdict")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="Completion timestamp")
    created_by = Column(UUID(as_uuid=True), nullable=True, comment="Account that created the debate")
    debate_metadata = Column(JSON, nullable=True, default=dict, comment="Additional metadata / configuration")
