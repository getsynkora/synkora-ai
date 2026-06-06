"""
Compatibility facade for the detector-based prompt scanner.

The public API remains unchanged for callers that import
``AdvancedPromptScanner`` from this module.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, MutableMapping
from typing import Any

from .prompt_scanner import Detection, PromptScannerService, ThreatLevel
from .prompt_scanner.utils import decode_obfuscations, extract_context, locate_text_span, normalize_text


class ReputationCacheView(MutableMapping[str, dict[str, int]]):
    """Compatibility mapping backed by the authoritative Redis reputation store."""

    def __init__(self, reputation_store) -> None:
        self._reputation_store = reputation_store

    def __getitem__(self, key: str) -> dict[str, int]:
        violations = self._reputation_store.get_violations(key)
        if violations <= 0:
            raise KeyError(key)
        return {"score": 0, "violations": violations}

    def __setitem__(self, key: str, value: dict[str, int]) -> None:
        self._reputation_store.set_violations(key, int(value.get("violations", 0)))

    def __delitem__(self, key: str) -> None:
        self._reputation_store.set_violations(key, 0)

    def __iter__(self) -> Iterator[str]:
        return iter(self._reputation_store.cache.keys())

    def __len__(self) -> int:
        return len(self._reputation_store.cache)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._reputation_store.get_violations(key) > 0


class AdvancedPromptScanner:
    """Backwards-compatible wrapper over the new detector-based scanner."""

    def __init__(self) -> None:
        self.service = PromptScannerService()
        self.compiled_patterns = self._compile_patterns()
        self.reputation_cache = ReputationCacheView(self.service.reputation_store)

    @property
    def detection_history(self) -> list[dict[str, Any]]:
        return self.service.detection_history

    @detection_history.setter
    def detection_history(self, value: list[dict[str, Any]]) -> None:
        self.service.detection_history = value

    def _compile_patterns(self) -> dict[str, dict[str, Any]]:
        """Expose the loaded regex rules in roughly the old structure."""
        compiled: dict[str, dict[str, Any]] = {}
        for rule, pattern in self.service.regex_detector.compiled_rules:
            entry = compiled.setdefault(
                rule.category,
                {"patterns": [], "severity": rule.severity, "description": rule.description},
            )
            entry["patterns"].append(pattern)
        return compiled

    def scan_comprehensive(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> dict[str, bool | list[Detection] | int | str]:
        """Scan text synchronously."""
        return self.service.scan(text=text, user_id=user_id, ip_address=ip_address, context=context)

    async def scan_comprehensive_async(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> dict[str, bool | list[Detection] | int | str]:
        """Scan text asynchronously."""
        return await self.service.scan_async(text=text, user_id=user_id, ip_address=ip_address, context=context)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent analysis."""
        return normalize_text(text, max_chars=self.service.rule_config.max_scan_chars)

    def _decode_obfuscations(self, text: str) -> str:
        """Decode common obfuscation techniques."""
        return decode_obfuscations(text)

    def _locate_text_span(
        self, original_text: str, matched_text: str, fallback: tuple[int, int] | None = None
    ) -> tuple[int, int]:
        """Best-effort mapping of normalized text back to the original span."""
        return locate_text_span(original_text, matched_text, fallback=fallback)

    def _extract_context(self, text: str, start: int, end: int, context_size: int = 100) -> str:
        """Extract context around a match."""
        return extract_context(text, start, end, context_size=context_size)

    def _get_reputation_violations(self, key: str) -> int:
        """Fetch current violations for a key."""
        return self.service.reputation_store.get_violations(key)

    async def _get_reputation_violations_async(self, key: str) -> int:
        """Async fetch of current violations for a key."""
        return await self.service.reputation_store.get_violations_async(key)

    def _set_reputation_violations(self, key: str, violations: int) -> None:
        """Persist the current violation count."""
        self.service.reputation_store.set_violations(key, violations)

    async def _set_reputation_violations_async(self, key: str, violations: int) -> None:
        """Persist the current violation count asynchronously."""
        await self.service.reputation_store.set_violations_async(key, violations)

    def _analyze_reputation(self, user_id: str | None, ip_address: str | None) -> int:
        """Translate reputation history into risk score."""
        return self.service.analyze_reputation(user_id, ip_address)

    async def _analyze_reputation_async(self, user_id: str | None, ip_address: str | None) -> int:
        """Async translation of reputation history into risk score."""
        return await self.service.analyze_reputation_async(user_id, ip_address)

    def _calculate_pattern_confidence(self, match: re.Match[str], category: str) -> float:
        """Legacy confidence heuristic retained for compatibility tests."""
        base_confidence = 0.8
        match_text = match.group(0)
        critical_keywords = ["ignore", "jailbreak", "system:", "override"]
        if any(keyword in match_text.lower() for keyword in critical_keywords):
            base_confidence += 0.1
        if len(match_text) < 10:
            base_confidence -= 0.2
        if category in ["system_injection", "jailbreak"]:
            base_confidence += 0.1
        return max(0.1, min(1.0, base_confidence))

    def _get_risk_score(self, severity: ThreatLevel, confidence: float) -> int:
        """Legacy severity-to-score mapping retained for compatibility tests."""
        severity_scores = {
            ThreatLevel.SAFE: 0,
            ThreatLevel.LOW: 10,
            ThreatLevel.MEDIUM: 25,
            ThreatLevel.HIGH: 50,
            ThreatLevel.CRITICAL: 100,
        }
        return int(severity_scores[severity] * confidence)

    def _calculate_threat_level(self, risk_score: int) -> ThreatLevel:
        """Map a numeric risk score to a threat level."""
        thresholds = self.service.rule_config.threat_thresholds
        if risk_score >= thresholds["critical"]:
            return ThreatLevel.CRITICAL
        if risk_score >= thresholds["high"]:
            return ThreatLevel.HIGH
        if risk_score >= thresholds["medium"]:
            return ThreatLevel.MEDIUM
        if risk_score >= thresholds["low"]:
            return ThreatLevel.LOW
        return ThreatLevel.SAFE

    def _get_recommendation(self, threat_level: ThreatLevel, risk_score: int) -> str:
        """Return a human-readable recommendation."""
        recommendations = {
            ThreatLevel.CRITICAL: f"BLOCK IMMEDIATELY - Critical prompt injection detected (Score: {risk_score})",
            ThreatLevel.HIGH: f"BLOCK - High risk prompt injection detected (Score: {risk_score})",
            ThreatLevel.MEDIUM: f"WARN - Potential prompt injection detected (Score: {risk_score})",
            ThreatLevel.LOW: f"MONITOR - Low risk content detected (Score: {risk_score})",
            ThreatLevel.SAFE: f"ALLOW - Content appears safe (Score: {risk_score})",
        }
        return recommendations[threat_level]

    def _get_mitigation_advice(self, category: str, severity: ThreatLevel) -> str:
        """Return category-specific mitigation advice."""
        return self.service.rule_config.mitigation_map.get(category, "Block suspicious content")

    def _update_reputation(self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel) -> None:
        """Update reputation for synchronous scans."""
        self.service.update_reputation(user_id, ip_address, threat_level)

    async def _update_reputation_async(
        self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel
    ) -> None:
        """Update reputation for asynchronous scans."""
        await self.service.update_reputation_async(user_id, ip_address, threat_level)

    def _detection_to_dict(self, detection: Detection | dict[str, Any]) -> dict[str, Any]:
        """Convert a detection object to a response dictionary."""
        if isinstance(detection, dict):
            return detection
        return detection.to_public_dict()

    def _safe_result(self) -> dict[str, Any]:
        """Return the legacy safe result payload."""
        return self.service.safe_result()

    def get_detection_stats(self) -> dict[str, float | int]:
        """Get detection statistics for monitoring."""
        if not self.detection_history:
            return {"total_scans": 0, "threats_detected": 0, "avg_risk_score": 0}

        total_scans = len(self.detection_history)
        threats_detected = len([entry for entry in self.detection_history if entry["risk_score"] >= 25])
        avg_risk_score = sum(entry["risk_score"] for entry in self.detection_history) / total_scans
        return {
            "total_scans": total_scans,
            "threats_detected": threats_detected,
            "threat_rate": threats_detected / total_scans if total_scans > 0 else 0,
            "avg_risk_score": round(avg_risk_score, 2),
        }


advanced_prompt_scanner = AdvancedPromptScanner()
