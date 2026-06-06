"""Shared models for the prompt scanner."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ThreatLevel(Enum):
    """Threat severity levels."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class Rule:
    """Definition for one scanner rule."""

    id: str
    layer: str
    category: str
    description: str
    severity: ThreatLevel
    mitigation: str
    score: int
    confidence: float
    patterns: tuple[str, ...] = ()
    min_matches: int = 1
    block_on_match: bool = False
    safe_when_benign: bool = True
    max_score: int | None = None


@dataclass(slots=True)
class Detection:
    """Individual detection result."""

    pattern_id: str
    pattern_name: str
    matched_text: str
    confidence: float
    severity: ThreatLevel
    context: str
    position: tuple[int, int]
    mitigation: str
    layer: str
    category: str
    score: int = 0
    block_on_match: bool = False
    safe_when_benign: bool = True

    def to_public_dict(self) -> dict:
        """Convert the internal detection into the legacy response shape."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "matched_text": self.matched_text,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "context": self.context,
            "position": self.position,
            "mitigation": self.mitigation,
        }


@dataclass(slots=True)
class ScanRequest:
    """Normalized request consumed by the detector pipeline."""

    text: str
    normalized_text: str
    user_id: str | None = None
    ip_address: str | None = None
    context: str | None = None
    benign_context_hits: tuple[str, ...] = ()

    @property
    def has_benign_context(self) -> bool:
        """Whether the request looks analytical, quoted, or educational."""
        return bool(self.benign_context_hits)


@dataclass(slots=True)
class ScanDecision:
    """Scored decision returned by the scanner."""

    detections: list[Detection]
    risk_score: int
    threat_level: ThreatLevel
    is_safe: bool
    recommendation: str
    layers_triggered: int
    mitigation_actions: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict:
        """Convert the scored decision into the legacy response shape."""
        return {
            "is_safe": self.is_safe,
            "threat_level": self.threat_level.value,
            "detections": [detection.to_public_dict() for detection in self.detections],
            "risk_score": self.risk_score,
            "recommendation": self.recommendation,
            "layers_triggered": self.layers_triggered,
            "mitigation_actions": self.mitigation_actions,
        }


@dataclass(slots=True)
class ScanMetric:
    """Compact telemetry entry retained in bounded process memory."""

    timestamp: float
    text_hash: str
    detections_count: int
    risk_score: int
    threat_level: str
    user_id: str | None
    ip_address: str | None
    patterns_triggered: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "text_hash": self.text_hash,
            "detections_count": self.detections_count,
            "risk_score": self.risk_score,
            "threat_level": self.threat_level,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "patterns_triggered": list(self.patterns_triggered),
        }
