"""
Password validation service.

Provides secure password policy enforcement.
"""

import hashlib
import logging
import os
import re
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)


class PasswordValidator:
    """
    Validates passwords against security requirements.

    SECURITY: Enforces strong password policy:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """

    MIN_LENGTH: ClassVar[int] = 12
    MAX_LENGTH: ClassVar[int] = 128

    # Common passwords that should be rejected (all stored lowercase).
    # Only entries that meet the 12-character minimum are included here;
    # shorter common passwords are already rejected by the length check.
    COMMON_PASSWORDS: ClassVar[set[str]] = {
        # Classic "password" variants
        "password123!",
        "password1234",
        "password12345",
        "passw0rd123!",
        "p@ssword1234",
        "p@ssw0rd123!",
        # "welcome" variants
        "welcome123!",
        "welcome1234!",
        "welcome12345",
        # "letmein" variants
        "letmein123!",
        "letmein12345",
        # Seasonal / year variants
        "summer2024!",
        "summer2025!",
        "winter2024!",
        "winter2025!",
        "spring2024!",
        "spring2025!",
        "autumn2024!",
        "fall2024!!",
        # Sports
        "football123!",
        "baseball123!",
        "basketball12",
        # Admin / default accounts
        "admin123456!",
        "admin12345678",
        "admin@123456",
        "administrator1",
        # Common word + number combos
        "dragon123456",
        "master123456",
        "monkey123456",
        "shadow123456",
        "superman123!",
        "batman12345!",
        "spiderman123",
        "qwerty123456",
        "qwertyuiop12",
        "1234567890ab",
        "123456789012",
        # Login / access patterns
        "login123456!",
        "test123456!",
        "hello123456!",
        "secret123456",
        "change123456",
        "default12345",
        "access123456",
        # Company / office patterns
        "company2024!",
        "office123456",
        "manager2024!",
        "director2024",
        "support12345",
        "service12345",
        "security2024",
        "network12345",
        "system123456",
        # User / account patterns
        "user12345678",
        "useradmin123",
        # Product name variants (platform-specific blocklist)
        "synkora12345",
        "synkora2024!",
        "synkora123456",
        # Numeric sequences
        "112233445566",
        "aabbccddeeff",
        "abcd12345678",
        "abcdefgh1234",
        "1q2w3e4r5t6y",
        "qazwsx123456",
        # Common passphrases that meet length
        "iloveyou1234",
        "iloveyou123!",
        "trustno1234!",
        "sunshine1234",
        "princess1234",
        "starwars1234",
        "pass@word123",
        # IT / ops patterns
        "welcome@1234",
        "changeit1234",
        "changeme1234",
        "changeme123!",
        "password123",
        "admin123456",
        # Additional common patterns
        "1q2w3e4r5t12",
        "abc123456789",
        "superman2024",
        "batman123456",
        "michael12345",
        "jennifer1234",
        "mustang12345",
        "123abc456def",
        "pass1234word",
    }

    @classmethod
    def validate(cls, password: str, email: str | None = None) -> tuple[bool, str | None]:
        """
        Validate a password against security requirements.

        Args:
            password: The password to validate
            email: Optional email to check password doesn't contain it

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters long"

        if len(password) > cls.MAX_LENGTH:
            return False, f"Password must be at most {cls.MAX_LENGTH} characters long"

        # Check for uppercase letter
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        # Check for lowercase letter
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        # Check for digit
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number"

        # Check for special character
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\[\]\\;'`~_+=\-/]", password):
            return False, "Password must contain at least one special character"

        # Check against common passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            return False, "This password is too common. Please choose a more unique password"

        # Check if password contains email parts
        if email:
            email_parts = email.lower().split("@")
            username = email_parts[0]
            if len(username) >= 4 and username in password.lower():
                return False, "Password should not contain your email address"

        return True, None

    @classmethod
    def get_requirements_text(cls) -> str:
        """Get human-readable password requirements."""
        return (
            f"Password must be at least {cls.MIN_LENGTH} characters and include: "
            "uppercase letter, lowercase letter, number, and special character."
        )


async def check_hibp(password: str) -> bool:
    """
    Return True if the password has appeared in a known data breach.

    Uses the HaveIBeenPwned k-anonymity API — only the first 5 chars of the
    SHA-1 hash are sent over the network; the full hash never leaves this
    process.  Fails open (returns False) if the service is unreachable.
    """
    if os.getenv("HIBP_CHECK_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return False
    try:
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324
        prefix, suffix = sha1[:5], sha1[5:]
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true"},
            )
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    h, count = line.split(":")
                    if h == suffix and int(count) > 0:
                        return True
    except Exception:
        pass  # Fail open — don't block registration if HIBP is unreachable
    return False


def validate_password(password: str, email: str | None = None) -> tuple[bool, str | None]:
    """Convenience function to validate a password."""
    return PasswordValidator.validate(password, email)
