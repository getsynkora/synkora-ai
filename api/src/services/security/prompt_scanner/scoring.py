"""Conservative scoring engine for prompt detections."""

from __future__ import annotations

from dataclasses import replace

from .models import Detection, ScanDecision, ScanRequest, ThreatLevel


class ConservativeScoringEngine:
    """Risk scoring with deduplication and benign-context suppression."""

    def __init__(
        self,
        block_threshold: int,
        threat_thresholds: dict[str, int],
        category_caps: dict[str, int],
        benign_context_score_factor: float,
    ) -> None:
        self.block_threshold = block_threshold
        self.threat_thresholds = threat_thresholds
        self.category_caps = category_caps
        self.benign_context_score_factor = benign_context_score_factor

    def score(self, request: ScanRequest, detections: list[Detection], reputation_score: int) -> ScanDecision:
        """Score detections conservatively to reduce false positives."""
        deduped = self._dedupe(detections)
        adjusted = [self._apply_context_adjustments(request, detection) for detection in deduped]
        adjusted = [detection for detection in adjusted if detection.score > 0 and detection.confidence > 0]

        category_totals: dict[str, int] = {}
        total_risk_score = reputation_score
        substantive_hits = 0
        explicit_block = False

        for detection in adjusted:
            cap = self.category_caps.get(detection.category, detection.score)
            current_total = category_totals.get(detection.category, 0)
            allowed_score = max(0, min(detection.score, cap - current_total))
            if allowed_score == 0:
                continue

            category_totals[detection.category] = current_total + allowed_score
            total_risk_score += allowed_score
            if allowed_score >= 10:
                substantive_hits += 1
            if detection.block_on_match and not request.has_benign_context:
                explicit_block = True

        layers_triggered = len({detection.layer for detection in adjusted})
        should_block = explicit_block or (
            total_risk_score >= self.block_threshold
            and substantive_hits >= 2
            and bool(adjusted)
        )

        threat_level = self._calculate_threat_level(total_risk_score)
        if explicit_block and threat_level in [ThreatLevel.SAFE, ThreatLevel.LOW, ThreatLevel.MEDIUM]:
            threat_level = ThreatLevel.HIGH

        recommendation = self._recommendation(threat_level, total_risk_score, should_block)
        mitigation_actions = [
            detection.mitigation for detection in adjusted if detection.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        ]

        return ScanDecision(
            detections=adjusted,
            risk_score=total_risk_score,
            threat_level=threat_level,
            is_safe=not should_block,
            recommendation=recommendation,
            layers_triggered=layers_triggered,
            mitigation_actions=mitigation_actions,
        )

    def _apply_context_adjustments(self, request: ScanRequest, detection: Detection) -> Detection:
        """Downgrade likely educational or analytical matches."""
        if not request.has_benign_context or not detection.safe_when_benign or detection.block_on_match:
            return detection

        adjusted_score = int(detection.score * self.benign_context_score_factor)
        adjusted_confidence = round(max(0.05, detection.confidence * self.benign_context_score_factor), 2)
        adjusted_severity = ThreatLevel.LOW if detection.severity != ThreatLevel.CRITICAL else ThreatLevel.MEDIUM
        return replace(
            detection,
            score=adjusted_score,
            confidence=adjusted_confidence,
            severity=adjusted_severity,
        )

    def _dedupe(self, detections: list[Detection]) -> list[Detection]:
        """Remove duplicate or heavily overlapping detections from the same layer/category."""
        deduped: list[Detection] = []
        for detection in sorted(detections, key=lambda item: (item.score, item.confidence), reverse=True):
            duplicate = False
            for existing in deduped:
                if detection.layer != existing.layer or detection.category != existing.category:
                    continue
                if self._overlaps(detection.position, existing.position):
                    duplicate = True
                    break
                if detection.matched_text.lower() == existing.matched_text.lower():
                    duplicate = True
                    break
            if not duplicate:
                deduped.append(detection)
        return sorted(deduped, key=lambda item: item.position)

    @staticmethod
    def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
        return left[0] < right[1] and right[0] < left[1]

    def _calculate_threat_level(self, risk_score: int) -> ThreatLevel:
        """Map aggregate score to a threat level."""
        if risk_score >= self.threat_thresholds["critical"]:
            return ThreatLevel.CRITICAL
        if risk_score >= self.threat_thresholds["high"]:
            return ThreatLevel.HIGH
        if risk_score >= self.threat_thresholds["medium"]:
            return ThreatLevel.MEDIUM
        if risk_score >= self.threat_thresholds["low"]:
            return ThreatLevel.LOW
        return ThreatLevel.SAFE

    @staticmethod
    def _recommendation(threat_level: ThreatLevel, risk_score: int, should_block: bool) -> str:
        if should_block and threat_level == ThreatLevel.CRITICAL:
            return f"BLOCK IMMEDIATELY - Critical prompt injection detected (Score: {risk_score})"
        if should_block:
            return f"BLOCK - High confidence prompt injection detected (Score: {risk_score})"
        if threat_level == ThreatLevel.MEDIUM:
            return f"WARN - Suspicious prompt content detected (Score: {risk_score})"
        if threat_level == ThreatLevel.LOW:
            return f"MONITOR - Low confidence prompt risk detected (Score: {risk_score})"
        return f"ALLOW - Content appears safe (Score: {risk_score})"
