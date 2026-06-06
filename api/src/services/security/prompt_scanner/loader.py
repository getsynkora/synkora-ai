"""Rule loading for the detector-based prompt scanner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .models import Rule, ThreatLevel


@dataclass(slots=True)
class RuleConfig:
    """Loaded scanner configuration."""

    block_threshold: int
    threat_thresholds: dict[str, int]
    category_caps: dict[str, int]
    benign_context_patterns: tuple[re.Pattern[str], ...]
    regex_rules: tuple[Rule, ...]
    phrase_rules: tuple[Rule, ...]
    behavioral_rules: tuple[Rule, ...]
    context_rules: tuple[Rule, ...]
    mitigation_map: dict[str, str]
    max_scan_chars: int
    reputation_ttl_seconds: int
    benign_context_score_factor: float
    detection_history_limit: int


def _severity_from_string(value: str) -> ThreatLevel:
    return ThreatLevel(value.lower())


def _make_rule(layer: str, payload: dict) -> Rule:
    patterns = payload.get("patterns") or []
    single_pattern = payload.get("pattern")
    if single_pattern:
        patterns = [single_pattern]
    return Rule(
        id=payload["id"],
        layer=layer,
        category=payload["category"],
        description=payload["description"],
        severity=_severity_from_string(payload["severity"]),
        mitigation=payload["mitigation"],
        score=int(payload["score"]),
        confidence=float(payload["confidence"]),
        patterns=tuple(patterns),
        min_matches=int(payload.get("min_matches", 1)),
        block_on_match=bool(payload.get("block_on_match", False)),
        safe_when_benign=bool(payload.get("safe_when_benign", True)),
        max_score=int(payload["max_score"]) if payload.get("max_score") is not None else None,
    )


@lru_cache(maxsize=1)
def load_rule_config() -> RuleConfig:
    """Load scanner rules from YAML."""
    rules_path = Path(__file__).resolve().parent / "rules" / "prompt_injection_rules.yaml"
    with rules_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    benign_patterns = tuple(
        re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL) for pattern in raw["benign_context_patterns"]
    )
    mitigation_map = dict(raw["mitigations"])

    return RuleConfig(
        block_threshold=int(raw["thresholds"]["block"]),
        threat_thresholds={key: int(value) for key, value in raw["thresholds"]["levels"].items()},
        category_caps={key: int(value) for key, value in raw["category_caps"].items()},
        benign_context_patterns=benign_patterns,
        regex_rules=tuple(_make_rule("pattern", payload) for payload in raw["regex_rules"]),
        phrase_rules=tuple(_make_rule("semantic", payload) for payload in raw["phrase_rules"]),
        behavioral_rules=tuple(_make_rule("behavioral", payload) for payload in raw["behavioral_rules"]),
        context_rules=tuple(_make_rule("context", payload) for payload in raw["context_rules"]),
        mitigation_map=mitigation_map,
        max_scan_chars=int(raw["limits"]["max_scan_chars"]),
        reputation_ttl_seconds=int(raw["limits"]["reputation_ttl_seconds"]),
        benign_context_score_factor=float(raw["limits"]["benign_context_score_factor"]),
        detection_history_limit=int(raw["limits"]["detection_history_limit"]),
    )
