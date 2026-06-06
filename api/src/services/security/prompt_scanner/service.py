"""Detector-based prompt scanner service."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from .detectors import BehavioralDetector, ContextDetector, PhraseDetector, RegexDetector
from .loader import RuleConfig, load_rule_config
from .models import Detection, ScanMetric, ScanRequest, ThreatLevel
from .reputation import RedisBackedReputationStore
from .scoring import ConservativeScoringEngine
from .utils import hash_text, normalize_text

logger = logging.getLogger(__name__)


class PromptScannerService:
    """Orchestrates detectors, scoring, logging, and reputation storage."""

    def __init__(self, rule_config: RuleConfig | None = None) -> None:
        self.rule_config = rule_config or load_rule_config()
        self.reputation_store = RedisBackedReputationStore(ttl_seconds=self.rule_config.reputation_ttl_seconds)
        self._detection_history: deque[ScanMetric] = deque(maxlen=self.rule_config.detection_history_limit)
        self.regex_detector = RegexDetector(self.rule_config.regex_rules)
        self.phrase_detector = PhraseDetector(self.rule_config.phrase_rules)
        self.behavioral_detector = BehavioralDetector(self.rule_config.behavioral_rules)
        self.context_detector = ContextDetector(self.rule_config.context_rules)
        self.scoring_engine = ConservativeScoringEngine(
            block_threshold=self.rule_config.block_threshold,
            threat_thresholds=self.rule_config.threat_thresholds,
            category_caps=self.rule_config.category_caps,
            benign_context_score_factor=self.rule_config.benign_context_score_factor,
        )

    def scan(self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None) -> dict:
        """Run the synchronous detector pipeline."""
        if not text or not text.strip():
            result = self.safe_result()
            self.record_scan("", [], result["risk_score"], result["threat_level"], user_id, ip_address)
            return result

        request = self.build_request(text, user_id=user_id, ip_address=ip_address, context=context)
        detections = self.run_detectors(request)
        reputation_score = self.analyze_reputation(user_id, ip_address)
        decision = self.scoring_engine.score(request, detections, reputation_score)
        result = decision.to_public_dict()
        result["scan_timestamp"] = time.time()

        self.record_scan(text, decision.detections, result["risk_score"], result["threat_level"], user_id, ip_address)
        if not result["is_safe"]:
            self.log_detection(text, decision.detections, result["risk_score"], user_id, ip_address)
        if (user_id or ip_address) and decision.detections:
            self.update_reputation(user_id, ip_address, decision.threat_level)
        return result

    async def scan_async(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> dict:
        """Run the async detector pipeline."""
        if not text or not text.strip():
            result = self.safe_result()
            self.record_scan("", [], result["risk_score"], result["threat_level"], user_id, ip_address)
            return result

        request = self.build_request(text, user_id=user_id, ip_address=ip_address, context=context)
        detections = self.run_detectors(request)
        reputation_score = await self.analyze_reputation_async(user_id, ip_address)
        decision = self.scoring_engine.score(request, detections, reputation_score)
        result = decision.to_public_dict()
        result["scan_timestamp"] = time.time()

        self.record_scan(text, decision.detections, result["risk_score"], result["threat_level"], user_id, ip_address)
        if not result["is_safe"]:
            self.log_detection(text, decision.detections, result["risk_score"], user_id, ip_address)
        if (user_id or ip_address) and decision.detections:
            await self.update_reputation_async(user_id, ip_address, decision.threat_level)
        return result

    def build_request(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> ScanRequest:
        """Create the normalized request for detector execution."""
        normalized_text = normalize_text(text, max_chars=self.rule_config.max_scan_chars)
        benign_hits = tuple(
            pattern.pattern for pattern in self.rule_config.benign_context_patterns if pattern.search(text) or pattern.search(normalized_text)
        )
        return ScanRequest(
            text=text[: self.rule_config.max_scan_chars],
            normalized_text=normalized_text,
            user_id=user_id,
            ip_address=ip_address,
            context=context,
            benign_context_hits=benign_hits,
        )

    def run_detectors(self, request: ScanRequest) -> list[Detection]:
        """Run all configured detectors."""
        detections: list[Detection] = []
        detections.extend(self.regex_detector.detect(request))
        detections.extend(self.phrase_detector.detect(request))
        detections.extend(self.behavioral_detector.detect(request))
        if request.context:
            detections.extend(self.context_detector.detect(request))
        return detections

    def analyze_reputation(self, user_id: str | None, ip_address: str | None) -> int:
        """Translate reputation history into a bounded score contribution."""
        reputation_score = 0
        if user_id:
            reputation_score += self.reputation_store.get_violations(f"user_{user_id}") * 10
        if ip_address:
            reputation_score += self.reputation_store.get_violations(f"ip_{ip_address}") * 5
        return min(reputation_score, self.rule_config.block_threshold)

    async def analyze_reputation_async(self, user_id: str | None, ip_address: str | None) -> int:
        """Translate reputation history into a bounded score contribution asynchronously."""
        reputation_score = 0
        if user_id:
            reputation_score += (await self.reputation_store.get_violations_async(f"user_{user_id}")) * 10
        if ip_address:
            reputation_score += (await self.reputation_store.get_violations_async(f"ip_{ip_address}")) * 5
        return min(reputation_score, self.rule_config.block_threshold)

    def update_reputation(self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel) -> None:
        """Persist reputation penalties for blocked or severe requests."""
        if threat_level not in [ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            return
        if user_id:
            self.reputation_store.increment_violations(f"user_{user_id}")
        if ip_address:
            self.reputation_store.increment_violations(f"ip_{ip_address}")

    async def update_reputation_async(self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel) -> None:
        """Persist reputation penalties asynchronously."""
        if threat_level not in [ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            return
        if user_id:
            await self.reputation_store.increment_violations_async(f"user_{user_id}")
        if ip_address:
            await self.reputation_store.increment_violations_async(f"ip_{ip_address}")

    def record_scan(
        self,
        text: str,
        detections: list[Detection],
        risk_score: int,
        threat_level: str,
        user_id: str | None,
        ip_address: str | None,
    ) -> None:
        """Persist scan metrics for monitoring."""
        self._detection_history.append(
            ScanMetric(
                timestamp=time.time(),
                text_hash=hash_text(text),
                detections_count=len(detections),
                risk_score=risk_score,
                threat_level=threat_level,
                user_id=user_id,
                ip_address=ip_address,
                patterns_triggered=tuple(detection.pattern_id for detection in detections),
            )
        )

    @property
    def detection_history(self) -> list[dict[str, Any]]:
        """Expose bounded scan telemetry in the legacy list-of-dicts shape."""
        return [metric.to_dict() for metric in self._detection_history]

    @detection_history.setter
    def detection_history(self, entries: list[dict[str, Any]]) -> None:
        """Compatibility setter used by older callers/tests."""
        self._detection_history = deque(
            (
                ScanMetric(
                    timestamp=float(entry.get("timestamp", 0.0)),
                    text_hash=str(entry.get("text_hash", "")),
                    detections_count=int(entry.get("detections_count", 0)),
                    risk_score=int(entry.get("risk_score", 0)),
                    threat_level=str(entry.get("threat_level", ThreatLevel.SAFE.value)),
                    user_id=entry.get("user_id"),
                    ip_address=entry.get("ip_address"),
                    patterns_triggered=tuple(entry.get("patterns_triggered", ())),
                )
                for entry in entries
            ),
            maxlen=self.rule_config.detection_history_limit,
        )

    @staticmethod
    def log_detection(
        text: str,
        detections: list[Detection],
        risk_score: int,
        user_id: str | None,
        ip_address: str | None,
    ) -> None:
        """Emit a security log line for blocked content."""
        logger.warning(
            "Prompt injection detected - Risk: %s, Patterns: %s, User: %s, IP: %s, TextHash: %s",
            risk_score,
            len(detections),
            user_id,
            ip_address,
            hash_text(text),
        )

    @staticmethod
    def safe_result() -> dict:
        """Legacy safe result payload."""
        return {
            "is_safe": True,
            "threat_level": ThreatLevel.SAFE.value,
            "detections": [],
            "risk_score": 0,
            "recommendation": "ALLOW - No content to analyze",
            "scan_timestamp": time.time(),
            "layers_triggered": 0,
            "mitigation_actions": [],
        }
