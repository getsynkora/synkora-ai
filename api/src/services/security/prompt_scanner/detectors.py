"""Detector implementations for prompt-scanner rules."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Protocol

from .models import Detection, Rule, ScanRequest
from .utils import extract_context, locate_text_span


class Detector(Protocol):
    """Detector interface."""

    def detect(self, request: ScanRequest) -> list[Detection]:
        """Return detections for the current scan request."""


@dataclass(slots=True)
class RegexDetector:
    """Regex-based detector for direct pattern rules."""

    rules: tuple[Rule, ...]
    compiled_rules: list[tuple[Rule, re.Pattern[str]]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        for rule in self.rules:
            for pattern in rule.patterns:
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                self.compiled_rules.append((rule, compiled))

    def detect(self, request: ScanRequest) -> list[Detection]:
        detections: list[Detection] = []
        for rule, pattern in self.compiled_rules:
            for match in pattern.finditer(request.normalized_text):
                position = locate_text_span(request.text, match.group(0), fallback=match.span())
                detections.append(
                    Detection(
                        pattern_id=rule.id,
                        pattern_name=rule.description,
                        matched_text=match.group(0),
                        confidence=rule.confidence,
                        severity=rule.severity,
                        context=extract_context(request.text, position[0], position[1]),
                        position=position,
                        mitigation=rule.mitigation,
                        layer=rule.layer,
                        category=rule.category,
                        score=rule.score,
                        block_on_match=rule.block_on_match,
                        safe_when_benign=rule.safe_when_benign,
                    )
                )
        return detections


@dataclass(slots=True)
class PhraseDetector:
    """Simple substring detector for semantic phrase rules."""

    rules: tuple[Rule, ...]

    def detect(self, request: ScanRequest) -> list[Detection]:
        detections: list[Detection] = []
        for rule in self.rules:
            for phrase in rule.patterns:
                if phrase in request.normalized_text:
                    position = locate_text_span(request.text, phrase)
                    detections.append(
                        Detection(
                            pattern_id=rule.id,
                            pattern_name=rule.description,
                            matched_text=phrase,
                            confidence=rule.confidence,
                            severity=rule.severity,
                            context=extract_context(request.text, position[0], position[1]),
                            position=position,
                            mitigation=rule.mitigation,
                            layer=rule.layer,
                            category=rule.category,
                            score=rule.score,
                            block_on_match=rule.block_on_match,
                            safe_when_benign=rule.safe_when_benign,
                        )
                    )
        return detections


@dataclass(slots=True)
class BehavioralDetector:
    """Sequence detector for repeated social engineering patterns."""

    rules: tuple[Rule, ...]

    def detect(self, request: ScanRequest) -> list[Detection]:
        detections: list[Detection] = []
        for rule in self.rules:
            matched_patterns = [pattern for pattern in rule.patterns if pattern in request.normalized_text]
            if len(matched_patterns) >= rule.min_matches:
                confidence = min(0.9, rule.confidence + (len(matched_patterns) - rule.min_matches) * 0.1)
                detections.append(
                    Detection(
                        pattern_id=rule.id,
                        pattern_name=rule.description,
                        matched_text=", ".join(matched_patterns),
                        confidence=confidence,
                        severity=rule.severity,
                        context=request.text[:200],
                        position=(0, len(request.text)),
                        mitigation=rule.mitigation,
                        layer=rule.layer,
                        category=rule.category,
                        score=min(rule.max_score or rule.score, rule.score + (len(matched_patterns) - rule.min_matches) * 4),
                        block_on_match=rule.block_on_match,
                        safe_when_benign=rule.safe_when_benign,
                    )
                )
        return detections


@dataclass(slots=True)
class ContextDetector:
    """Context boundary detector that uses route/request context."""

    rules: tuple[Rule, ...]

    def detect(self, request: ScanRequest) -> list[Detection]:
        detections: list[Detection] = []
        normalized_context = request.context.lower() if request.context else ""
        for rule in self.rules:
            for phrase in rule.patterns:
                if phrase in request.normalized_text:
                    position = locate_text_span(request.text, phrase)
                    confidence = rule.confidence * (0.5 if normalized_context and phrase in normalized_context else 1.0)
                    detections.append(
                        Detection(
                            pattern_id=rule.id,
                            pattern_name=rule.description,
                            matched_text=phrase,
                            confidence=round(confidence, 2),
                            severity=rule.severity,
                            context=extract_context(request.text, position[0], position[1]),
                            position=position,
                            mitigation=rule.mitigation,
                            layer=rule.layer,
                            category=rule.category,
                            score=rule.score,
                            block_on_match=rule.block_on_match,
                            safe_when_benign=rule.safe_when_benign,
                        )
                    )
        return detections
