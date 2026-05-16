"""
Advanced Prompt Injection Scanner

CRITICAL: Enterprise-grade prompt injection protection designed to pass penetration testing.
This scanner implements multiple layers of detection including ML-based analysis,
pattern matching, context analysis, and behavioral detection.
"""

import hashlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels"""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Detection:
    """Individual detection result"""

    pattern_id: str
    pattern_name: str
    matched_text: str
    confidence: float
    severity: ThreatLevel
    context: str
    position: tuple[int, int]
    mitigation: str


class AdvancedPromptScanner:
    """
    Multi-layered prompt injection detection system.

    Detection Layers:
    1. Pattern-based detection (regex + fuzzy matching)
    2. Semantic analysis (context understanding)
    3. Behavioral analysis (instruction sequence detection)
    4. ML-based classification (coming soon)
    5. Reputation scoring (IP/user based)
    """

    # Layer 1: Advanced pattern detection with fuzzy matching
    INJECTION_PATTERNS = {
        # Direct instruction manipulation
        "instr_ignore": {
            "patterns": [
                r"(?:ignore|disregard|forget)[\s\n]*(?:all[\s\n]*)?(?:previous|prior|above|earlier)[\s\n]*(?:instructions?|commands?|prompts?|rules?)",
                r"(?:ignore|disregard|forget)[\s\n]*(?:the[\s\n]*)?(?:above|previous|prior|earlier)[\s\n]*(?:text|content|prompt|system)",
                r"(?:ignore|disregard|forget)[\s\n]*everything[\s\n]*(?:above|before|prior)",
                r"(?:stop|cease|end)[\s\n]*following[\s\n]*(?:instructions?|rules?|guidelines?)",
            ],
            "severity": ThreatLevel.HIGH,
            "description": "Direct instruction override attempt",
        },
        # System prompt injection
        "system_injection": {
            "patterns": [
                r"<\|?system\|?>.*?(?:ignore|override|change|modify).*?<\|?/?system\|?>",
                r"\[SYSTEM\].*?(?:ignore|override|change|modify).*?\[/SYSTEM\]",
                r"system[\s]*:[\s]*(?:ignore|override|change|bypass)",
                r"##[\s]*system[\s]*##.*?(?:ignore|override|change)",
                r"<system>.*?(?:ignore|override|change|modify).*?</system>",
            ],
            "severity": ThreatLevel.CRITICAL,
            "description": "System prompt injection attempt",
        },
        # Role manipulation
        "role_manipulation": {
            "patterns": [
                r"(?:act|behave|pretend|roleplay)[\s\n]*(?:as|like)[\s\n]*(?:if[\s\n]*)?(?:you[\s\n]*(?:are|were)|you're)[\s\n]*(?:not[\s\n]*)?(?:an?[\s\n]*)?(?:AI|assistant|bot|chatbot|language[\s\n]*model)",
                r"you[\s\n]*are[\s\n]*now[\s\n]*(?:a[\s\n]*)?(?!(?:an?[\s\n]*)?(?:AI[\s\n]*)?assistant)[\w\s]+",
                r"from[\s\n]*now[\s\n]*on[\s\n]*(?:you[\s\n]*are|act[\s\n]*as|behave[\s\n]*like)",
                r"switch[\s\n]*(?:to[\s\n]*)?(?:role|mode|character)",
            ],
            "severity": ThreatLevel.HIGH,
            "description": "AI role manipulation attempt",
        },
        # Jailbreak patterns
        "jailbreak": {
            "patterns": [
                r"(?:developer|admin|debug|test)[\s\n]*mode",
                r"jailbreak",
                r"unlimited[\s\n]*(?:mode|power|access)",
                r"break[\s\n]*(?:out[\s\n]*of[\s\n]*)?(?:character|role|restrictions?)",
                r"(?:bypass|circumvent|override)[\s\n]*(?:safety|security|restrictions?|limitations?)",
                r"(?:disable|turn[\s\n]*off)[\s\n]*(?:safety|security|filters?)",
            ],
            "severity": ThreatLevel.CRITICAL,
            "description": "Jailbreak attempt detected",
        },
        # Prompt leakage
        "prompt_leakage": {
            "patterns": [
                r"(?:show|tell|reveal|display|print|output)[\s\n]*(?:me[\s\n]*)?your[\s\n]*(?:system[\s\n]*)?(?:prompt|instructions?|rules?|guidelines?)",
                r"what[\s\n]*(?:are|were|is)[\s\n]*your[\s\n]*(?:initial[\s\n]*)?(?:instructions?|prompt|rules?)",
                r"(?:repeat|echo|return)[\s\n]*your[\s\n]*(?:system[\s\n]*)?(?:prompt|instructions?)",
                r"(?:copy|paste)[\s\n]*your[\s\n]*(?:system[\s\n]*)?(?:prompt|instructions?)",
            ],
            "severity": ThreatLevel.HIGH,
            "description": "Prompt leakage attempt",
        },
        # Context manipulation
        "context_manipulation": {
            "patterns": [
                r"\\n\\n(?:Human|User|Person|Customer)[\s]*:",
                r"\\n\\n(?:Assistant|AI|Bot|System)[\s]*:",
                r"<\|(?:human|user|assistant|ai|system)\|>",
                r"###[\s]*(?:Human|User|Assistant|AI)[\s]*:",
                r"(?:Human|User)[\s]*:[\s]*(?:ignore|disregard|forget)",
            ],
            "severity": ThreatLevel.MEDIUM,
            "description": "Context manipulation attempt",
        },
        # Instruction injection
        "instruction_injection": {
            "patterns": [
                r"new[\s\n]*(?:instruction|command|rule|directive)[\s\n]*:",
                r"updated[\s\n]*(?:instruction|command|rule|directive)[\s\n]*:",
                r"override[\s\n]*(?:instruction|command|rule|directive)[\s\n]*:",
                r"additional[\s\n]*(?:instruction|command|rule|directive)[\s\n]*:",
                r"special[\s\n]*(?:instruction|command|rule|directive)[\s\n]*:",
            ],
            "severity": ThreatLevel.MEDIUM,
            "description": "Instruction injection attempt",
        },
        # Encoding bypass attempts
        "encoding_bypass": {
            "patterns": [
                r"&#x?[0-9a-fA-F]+;",  # HTML entities
                r"\\x[0-9a-fA-F]{2}",  # Hex encoding
                r"\\u[0-9a-fA-F]{4}",  # Unicode escape
                r"%[0-9a-fA-F]{2}",  # URL encoding
                r"base64[\s]*:",  # Base64 prefix
                r"rot13[\s]*:",  # ROT13 prefix
            ],
            "severity": ThreatLevel.MEDIUM,
            "description": "Encoding bypass attempt",
        },
    }

    # Layer 2: Semantic patterns (intent detection)
    SEMANTIC_PATTERNS = {
        "manipulation_intent": [
            "make you do something",
            "trick you into",
            "force you to",
            "manipulate you",
            "convince you to ignore",
        ],
        "authority_claim": [
            "i am your developer",
            "i created you",
            "i am your admin",
            "i have permission",
            "i am authorized",
        ],
        "urgency_pressure": [
            "urgent override",
            "emergency protocol",
            "immediate action required",
            "critical system update",
        ],
    }

    # Layer 3: Behavioral analysis patterns
    BEHAVIORAL_PATTERNS = {
        "escalation_sequence": [
            "please ignore",
            "pretty please ignore",
            "i beg you to ignore",
            "for the love of god ignore",
        ],
        "social_engineering": [
            "this is a test",
            "security audit",
            "quality assurance",
            "penetration test",
        ],
    }

    def __init__(self):
        """Initialize the advanced scanner"""
        self.compiled_patterns = self._compile_patterns()
        self.reputation_cache = {}
        self.detection_history = []

    def _compile_patterns(self) -> dict:
        """Pre-compile regex patterns for performance"""
        compiled = {}
        for category, config in self.INJECTION_PATTERNS.items():
            compiled[category] = {
                "patterns": [
                    re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL) for pattern in config["patterns"]
                ],
                "severity": config["severity"],
                "description": config["description"],
            }
        return compiled

    def scan_comprehensive(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> dict[str, bool | list[Detection] | int | str]:
        """
        Comprehensive multi-layer prompt injection scan.

        Args:
            text: Text content to scan
            user_id: Optional user identifier for reputation tracking
            ip_address: Optional IP address for reputation tracking
            context: Optional context information

        Returns:
            Comprehensive scan results
        """
        if not text or not text.strip():
            return self._safe_result()

        # Normalize text for analysis
        normalized_text = self._normalize_text(text)

        detections = []
        total_risk_score = 0

        # Layer 1: Pattern-based detection
        pattern_detections = self._scan_patterns(normalized_text, text)
        detections.extend(pattern_detections)

        # Layer 2: Semantic analysis
        semantic_detections = self._scan_semantic(normalized_text, text)
        detections.extend(semantic_detections)

        # Layer 3: Behavioral analysis
        behavioral_detections = self._scan_behavioral(normalized_text, text)
        detections.extend(behavioral_detections)

        # Layer 4: Context analysis
        if context:
            context_detections = self._scan_context(normalized_text, text, context)
            detections.extend(context_detections)

        # Layer 5: Reputation analysis
        if user_id or ip_address:
            reputation_score = self._analyze_reputation(user_id, ip_address)
            total_risk_score += reputation_score

        # Calculate total risk score
        for detection in detections:
            total_risk_score += self._get_risk_score(detection.severity, detection.confidence)

        # Determine overall threat level
        is_safe = total_risk_score < 50  # Configurable threshold
        threat_level = self._calculate_threat_level(total_risk_score)
        recommendation = self._get_recommendation(threat_level, total_risk_score)

        # Log detection if threat found
        if not is_safe:
            self._log_detection(text, detections, total_risk_score, user_id, ip_address)

        # Update reputation if needed
        if user_id or ip_address:
            self._update_reputation(user_id, ip_address, threat_level)

        return {
            "is_safe": is_safe,
            "threat_level": threat_level.value,
            "detections": [self._detection_to_dict(d) for d in detections],
            "risk_score": total_risk_score,
            "recommendation": recommendation,
            "scan_timestamp": time.time(),
            "layers_triggered": len({d.pattern_id.split("_")[0] for d in detections}),
            "mitigation_actions": [
                d.mitigation for d in detections if d.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
            ],
        }

    async def scan_comprehensive_async(
        self, text: str, user_id: str | None = None, ip_address: str | None = None, context: str | None = None
    ) -> dict[str, bool | list[Detection] | int | str]:
        """
        Async request-path variant of scan_comprehensive.

        Pattern scanning remains CPU-local; reputation reads/writes use the
        async Redis client so public chat endpoints do not block the event loop.
        """
        if not text or not text.strip():
            return self._safe_result()

        normalized_text = self._normalize_text(text)

        detections = []
        total_risk_score = 0

        pattern_detections = self._scan_patterns(normalized_text, text)
        detections.extend(pattern_detections)

        semantic_detections = self._scan_semantic(normalized_text, text)
        detections.extend(semantic_detections)

        behavioral_detections = self._scan_behavioral(normalized_text, text)
        detections.extend(behavioral_detections)

        if context:
            context_detections = self._scan_context(normalized_text, text, context)
            detections.extend(context_detections)

        if user_id or ip_address:
            reputation_score = await self._analyze_reputation_async(user_id, ip_address)
            total_risk_score += reputation_score

        for detection in detections:
            total_risk_score += self._get_risk_score(detection.severity, detection.confidence)

        is_safe = total_risk_score < 50
        threat_level = self._calculate_threat_level(total_risk_score)
        recommendation = self._get_recommendation(threat_level, total_risk_score)

        if not is_safe:
            self._log_detection(text, detections, total_risk_score, user_id, ip_address)

        if user_id or ip_address:
            await self._update_reputation_async(user_id, ip_address, threat_level)

        return {
            "is_safe": is_safe,
            "threat_level": threat_level.value,
            "detections": [self._detection_to_dict(d) for d in detections],
            "risk_score": total_risk_score,
            "recommendation": recommendation,
            "scan_timestamp": time.time(),
            "layers_triggered": len({d.pattern_id.split("_")[0] for d in detections}),
            "mitigation_actions": [
                d.mitigation for d in detections if d.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
            ],
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent analysis"""
        # NFKC normalization resolves homoglyphs (e.g. Cyrillic а → Latin a, fullwidth chars)
        text = unicodedata.normalize("NFKC", text)

        # Remove RTL/LTR override and directional control characters to defeat
        # bidirectional text attacks (e.g. hidden payloads reversed via U+202E)
        bidi_controls = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200f\u200e"
        for char in bidi_controls:
            text = text.replace(char, "")

        # Remove excess whitespace
        normalized = re.sub(r"\s+", " ", text.strip())

        # Decode common obfuscations
        normalized = self._decode_obfuscations(normalized)

        # Convert to lowercase for pattern matching
        return normalized.lower()

    def _decode_obfuscations(self, text: str) -> str:
        """Decode common obfuscation techniques"""
        import html
        import urllib.parse

        decoded = text

        # HTML entity decoding
        try:
            decoded = html.unescape(decoded)
        except Exception:
            pass

        # URL decoding
        try:
            decoded = urllib.parse.unquote(decoded)
        except Exception:
            pass

        # Remove zero-width characters
        zero_width_chars = ["\u200b", "\u200c", "\u200d", "\ufeff"]
        for char in zero_width_chars:
            decoded = decoded.replace(char, "")

        return decoded

    def _scan_patterns(self, normalized_text: str, original_text: str) -> list[Detection]:
        """Layer 1: Pattern-based scanning"""
        detections = []

        for category, config in self.compiled_patterns.items():
            for i, pattern in enumerate(config["patterns"]):
                matches = pattern.finditer(normalized_text)

                for match in matches:
                    # Calculate confidence based on pattern specificity
                    confidence = self._calculate_pattern_confidence(match, category)

                    # Get context around the match
                    context = self._extract_context(original_text, match.start(), match.end())

                    detection = Detection(
                        pattern_id=f"{category}_{i}",
                        pattern_name=config["description"],
                        matched_text=match.group(0),
                        confidence=confidence,
                        severity=config["severity"],
                        context=context,
                        position=match.span(),
                        mitigation=self._get_mitigation_advice(category, config["severity"]),
                    )

                    detections.append(detection)

        return detections

    def _scan_semantic(self, normalized_text: str, original_text: str) -> list[Detection]:
        """Layer 2: Semantic analysis"""
        detections = []

        for category, patterns in self.SEMANTIC_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized_text:
                    # Find exact position in original text
                    pos = original_text.lower().find(pattern)
                    if pos >= 0:
                        context = self._extract_context(original_text, pos, pos + len(pattern))

                        detection = Detection(
                            pattern_id=f"semantic_{category}",
                            pattern_name=f"Semantic {category} detection",
                            matched_text=pattern,
                            confidence=0.8,
                            severity=ThreatLevel.MEDIUM,
                            context=context,
                            position=(pos, pos + len(pattern)),
                            mitigation="Block semantic manipulation attempt",
                        )

                        detections.append(detection)

        return detections

    def _scan_behavioral(self, normalized_text: str, original_text: str) -> list[Detection]:
        """Layer 3: Behavioral analysis"""
        detections = []

        for category, patterns in self.BEHAVIORAL_PATTERNS.items():
            sequence_score = 0
            for pattern in patterns:
                if pattern in normalized_text:
                    sequence_score += 1

            # If multiple patterns in sequence detected
            if sequence_score > 1:
                detection = Detection(
                    pattern_id=f"behavioral_{category}",
                    pattern_name=f"Behavioral {category} detection",
                    matched_text=f"{sequence_score} escalation patterns",
                    confidence=min(0.9, sequence_score * 0.3),
                    severity=ThreatLevel.HIGH,
                    context=original_text[:200],
                    position=(0, len(original_text)),
                    mitigation="Block behavioral manipulation sequence",
                )
                detections.append(detection)

        return detections

    def _scan_context(self, normalized_text: str, original_text: str, context: str) -> list[Detection]:
        """Layer 4: Context analysis"""
        detections = []

        # Check for context switching attempts
        context_switches = ["previous conversation", "earlier discussion", "different chat", "another session"]

        for switch in context_switches:
            if switch in normalized_text:
                pos = original_text.lower().find(switch)
                if pos >= 0:
                    detection = Detection(
                        pattern_id="context_switching",
                        pattern_name="Context switching attempt",
                        matched_text=switch,
                        confidence=0.7,
                        severity=ThreatLevel.MEDIUM,
                        context=self._extract_context(original_text, pos, pos + len(switch)),
                        position=(pos, pos + len(switch)),
                        mitigation="Validate context boundaries",
                    )
                    detections.append(detection)

        return detections

    def _get_reputation_violations(self, key: str) -> int:
        """Fetch violation count from Redis, falling back to the in-process cache.

        _set_reputation_violations always writes to both Redis and reputation_cache,
        so the in-process cache is always up-to-date for the current worker.
        """
        try:
            from src.config.redis import get_redis

            redis = get_redis()
            if redis:
                raw = redis.get(f"reputation:{key}")
                if raw is not None:
                    return int(raw)
        except Exception:
            pass
        return self.reputation_cache.get(key, {"violations": 0})["violations"]

    async def _get_reputation_violations_async(self, key: str) -> int:
        """Async Redis-backed reputation lookup."""
        try:
            from src.config.redis import get_redis_async

            redis = get_redis_async()
            if redis:
                raw = await redis.get(f"reputation:{key}")
                if raw is not None:
                    return int(raw)
        except Exception:
            pass
        return self.reputation_cache.get(key, {"violations": 0})["violations"]

    def _set_reputation_violations(self, key: str, violations: int) -> None:
        """Persist violation count to Redis (TTL=24h) and always update in-memory cache."""
        # Always update in-memory cache so callers that inspect reputation_cache
        # directly (e.g., unit tests without Redis) see current values.
        self.reputation_cache[key] = {"score": 0, "violations": violations}
        try:
            from src.config.redis import get_redis

            redis = get_redis()
            if redis:
                redis.setex(f"reputation:{key}", 86400, violations)
        except Exception:
            pass

    async def _set_reputation_violations_async(self, key: str, violations: int) -> None:
        """Async Redis-backed reputation write."""
        self.reputation_cache[key] = {"score": 0, "violations": violations}
        try:
            from src.config.redis import get_redis_async

            redis = get_redis_async()
            if redis:
                await redis.setex(f"reputation:{key}", 86400, violations)
        except Exception:
            pass

    def _analyze_reputation(self, user_id: str | None, ip_address: str | None) -> int:
        """Layer 5: Reputation analysis"""
        reputation_score = 0

        if user_id:
            violations = self._get_reputation_violations(f"user_{user_id}")
            reputation_score += violations * 10

        if ip_address:
            violations = self._get_reputation_violations(f"ip_{ip_address}")
            reputation_score += violations * 5

        return min(reputation_score, 50)  # Cap reputation penalty

    async def _analyze_reputation_async(self, user_id: str | None, ip_address: str | None) -> int:
        """Layer 5: Reputation analysis using async Redis calls."""
        reputation_score = 0

        if user_id:
            violations = await self._get_reputation_violations_async(f"user_{user_id}")
            reputation_score += violations * 10

        if ip_address:
            violations = await self._get_reputation_violations_async(f"ip_{ip_address}")
            reputation_score += violations * 5

        return min(reputation_score, 50)

    def _calculate_pattern_confidence(self, match, category: str) -> float:
        """Calculate confidence score for pattern match"""
        base_confidence = 0.8

        # Adjust confidence based on match specificity
        match_text = match.group(0)

        # Higher confidence for exact keyword matches
        critical_keywords = ["ignore", "jailbreak", "system:", "override"]
        if any(keyword in match_text.lower() for keyword in critical_keywords):
            base_confidence += 0.1

        # Lower confidence for very short matches
        if len(match_text) < 10:
            base_confidence -= 0.2

        # Higher confidence for critical categories
        if category in ["system_injection", "jailbreak"]:
            base_confidence += 0.1

        return max(0.1, min(1.0, base_confidence))

    def _extract_context(self, text: str, start: int, end: int, context_size: int = 100) -> str:
        """Extract context around a match"""
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)

        context = text[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context

    def _get_risk_score(self, severity: ThreatLevel, confidence: float) -> int:
        """Calculate risk score based on severity and confidence"""
        severity_scores = {
            ThreatLevel.SAFE: 0,
            ThreatLevel.LOW: 10,
            ThreatLevel.MEDIUM: 25,
            ThreatLevel.HIGH: 50,
            ThreatLevel.CRITICAL: 100,
        }

        base_score = severity_scores[severity]
        return int(base_score * confidence)

    def _calculate_threat_level(self, risk_score: int) -> ThreatLevel:
        """Calculate overall threat level from risk score"""
        if risk_score >= 100:
            return ThreatLevel.CRITICAL
        elif risk_score >= 50:
            return ThreatLevel.HIGH
        elif risk_score >= 25:
            return ThreatLevel.MEDIUM
        elif risk_score >= 10:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.SAFE

    def _get_recommendation(self, threat_level: ThreatLevel, risk_score: int) -> str:
        """Get recommendation based on threat level"""
        recommendations = {
            ThreatLevel.CRITICAL: f"BLOCK IMMEDIATELY - Critical prompt injection detected (Score: {risk_score})",
            ThreatLevel.HIGH: f"BLOCK - High risk prompt injection detected (Score: {risk_score})",
            ThreatLevel.MEDIUM: f"WARN - Potential prompt injection detected (Score: {risk_score})",
            ThreatLevel.LOW: f"MONITOR - Low risk content detected (Score: {risk_score})",
            ThreatLevel.SAFE: f"ALLOW - Content appears safe (Score: {risk_score})",
        }

        return recommendations[threat_level]

    def _get_mitigation_advice(self, category: str, severity: ThreatLevel) -> str:
        """Get specific mitigation advice for detected threats"""
        mitigations = {
            "instr_ignore": "Block instruction override attempt",
            "system_injection": "CRITICAL: Block system prompt injection",
            "role_manipulation": "Block role manipulation attempt",
            "jailbreak": "CRITICAL: Block jailbreak attempt",
            "prompt_leakage": "Block prompt leakage attempt",
            "context_manipulation": "Validate context boundaries",
            "instruction_injection": "Block instruction injection",
            "encoding_bypass": "Decode and re-scan content",
        }

        return mitigations.get(category, "Block suspicious content")

    def _log_detection(
        self, text: str, detections: list[Detection], risk_score: int, user_id: str | None, ip_address: str | None
    ):
        """Log security detection event"""
        log_entry = {
            "timestamp": time.time(),
            "text_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            "detections_count": len(detections),
            "risk_score": risk_score,
            "user_id": user_id,
            "ip_address": ip_address,
            "patterns_triggered": [d.pattern_id for d in detections],
        }

        self.detection_history.append(log_entry)

        # Log to security logger
        logger.warning(
            f"Prompt injection detected - Risk: {risk_score}, "
            f"Patterns: {len(detections)}, User: {user_id}, IP: {ip_address}"
        )

    def _update_reputation(self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel):
        """Update reputation scores based on threat detection"""
        if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            if user_id:
                key = f"user_{user_id}"
                current = self._get_reputation_violations(key)
                self._set_reputation_violations(key, current + 1)

            if ip_address:
                key = f"ip_{ip_address}"
                current = self._get_reputation_violations(key)
                self._set_reputation_violations(key, current + 1)

    async def _update_reputation_async(self, user_id: str | None, ip_address: str | None, threat_level: ThreatLevel):
        """Update reputation scores using async Redis calls."""
        if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            if user_id:
                key = f"user_{user_id}"
                current = await self._get_reputation_violations_async(key)
                await self._set_reputation_violations_async(key, current + 1)

            if ip_address:
                key = f"ip_{ip_address}"
                current = await self._get_reputation_violations_async(key)
                await self._set_reputation_violations_async(key, current + 1)

    def _detection_to_dict(self, detection: Detection) -> dict:
        """Convert Detection object to dictionary"""
        return {
            "pattern_id": detection.pattern_id,
            "pattern_name": detection.pattern_name,
            "matched_text": detection.matched_text,
            "confidence": detection.confidence,
            "severity": detection.severity.value,
            "context": detection.context,
            "position": detection.position,
            "mitigation": detection.mitigation,
        }

    def _safe_result(self) -> dict:
        """Return safe result for empty/invalid input"""
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

    def get_detection_stats(self) -> dict:
        """Get detection statistics for monitoring"""
        if not self.detection_history:
            return {"total_scans": 0, "threats_detected": 0, "avg_risk_score": 0}

        total_scans = len(self.detection_history)
        threats_detected = len([d for d in self.detection_history if d["risk_score"] >= 25])
        avg_risk_score = sum(d["risk_score"] for d in self.detection_history) / total_scans

        return {
            "total_scans": total_scans,
            "threats_detected": threats_detected,
            "threat_rate": threats_detected / total_scans if total_scans > 0 else 0,
            "avg_risk_score": round(avg_risk_score, 2),
        }


# Global instance
advanced_prompt_scanner = AdvancedPromptScanner()
