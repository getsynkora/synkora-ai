"""Schemas for AI War Room debates."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DebateParticipantConfig(BaseModel):
    """Configuration for a single debate participant (internal agent)."""

    agent_id: UUID = Field(..., description="ID of the Synkora agent")
    role: str | None = Field(None, description="Optional role label (e.g. 'For', 'Against')")


class ExternalParticipantConfig(BaseModel):
    """Configuration for an external agent joining via API."""

    agent_name: str = Field(..., description="Display name of the external agent")
    agent_description: str | None = Field(None, description="Brief description")
    callback_url: str | None = Field(None, description="URL where Synkora POSTs round context")
    auth_token: str | None = Field(None, description="Bearer token for callback authentication")


class DebateContext(BaseModel):
    """Optional context data for the debate (e.g., GitHub PR)."""

    type: Literal["github_pr", "text"] = Field(..., description="Context type")
    # GitHub PR fields
    github_url: str | None = Field(None, description="Full GitHub PR URL")
    repo_full_name: str | None = Field(None, description="owner/repo")
    pr_number: int | None = Field(None, description="PR number")
    pr_title: str | None = None
    pr_description: str | None = None
    pr_diff: str | None = None
    pr_files_changed: list[str] | None = None
    pr_author: str | None = None
    pr_base_branch: str | None = None
    pr_head_branch: str | None = None
    # Plain text context
    text: str | None = Field(None, description="Plain text context")


class DebateCreateRequest(BaseModel):
    """Request to create a new debate session."""

    topic: str = Field(..., min_length=5, max_length=1000, description="The debate topic / question")
    debate_type: Literal["structured", "freeform"] = Field(
        "structured",
        description="structured = fixed rounds with synthesis; freeform = open-ended",
    )
    rounds: int = Field(3, ge=1, le=10, description="Number of debate rounds")
    participants: list[DebateParticipantConfig] = Field(
        ..., min_length=2, max_length=8, description="Internal agents participating"
    )
    synthesizer_agent_id: UUID | None = Field(None, description="Optional agent to synthesize the final verdict")
    is_public: bool = Field(False, description="Whether the debate is publicly viewable")
    allow_external: bool = Field(False, description="Whether external agents can join")
    context: DebateContext | None = Field(None, description="Optional context (e.g., GitHub PR to review)")


class DebateUpdateRequest(BaseModel):
    """Request to update a pending debate session."""

    topic: str | None = Field(None, min_length=5, max_length=1000)
    debate_type: Literal["structured", "freeform"] | None = None
    rounds: int | None = Field(None, ge=1, le=10)
    participants: list[DebateParticipantConfig] | None = Field(None, min_length=2, max_length=8)
    synthesizer_agent_id: UUID | None = None
    is_public: bool | None = None
    allow_external: bool | None = None
    context: DebateContext | None = None


class DebateJoinRequest(BaseModel):
    """Request for an external agent to join a debate."""

    agent_name: str = Field(..., min_length=1, max_length=200)
    agent_description: str | None = None
    callback_url: str | None = None
    auth_token: str | None = None


class DebateRespondRequest(BaseModel):
    """External agent submitting a response."""

    participant_id: str = Field(..., description="Participant ID received on join")
    participant_token: str | None = Field(None, max_length=256, description="Private capability returned once on join")
    round: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=100000)


class DebateParticipantSchema(BaseModel):
    """Participant info returned in API responses."""

    id: str
    agent_name: str
    agent_id: str | None = None
    role: str | None = None
    is_external: bool = False
    color: str = "#6366f1"


def public_participants(participants: list[dict]) -> list[dict]:
    """Explicit public fields: never return callback or participant credentials."""
    return [DebateParticipantSchema.model_validate(participant).model_dump() for participant in participants]


class DebateMessageSchema(BaseModel):
    """A single message in the debate timeline."""

    id: str
    participant_id: str
    agent_name: str
    round: int
    content: str
    is_verdict: bool = False
    is_external: bool = False
    created_at: str
    color: str = "#6366f1"


class DebateSessionSchema(BaseModel):
    """Full debate session response."""

    id: str
    topic: str
    debate_type: str
    rounds: int
    current_round: int
    status: str  # pending, active, synthesizing, completed, error
    is_public: bool
    allow_external: bool
    share_token: str | None = None
    participants: list[DebateParticipantSchema]
    messages: list[DebateMessageSchema]
    verdict: str | None = None
    created_at: str
    completed_at: str | None = None


class DebateListItem(BaseModel):
    """Debate summary for list views."""

    id: str
    topic: str
    debate_type: str
    rounds: int
    current_round: int
    status: str
    participant_count: int
    is_public: bool
    created_at: str
