"""
PhoneProviderCredential Model

Stores encrypted API credentials for call platform providers (Vapi, etc.).
Mirrors the VoiceApiKey pattern.
"""

from sqlalchemy import Boolean, Column, String, Text

from src.models.base import BaseModel, TenantMixin


class PhoneProviderCredential(BaseModel, TenantMixin):
    """
    Encrypted credential for a phone call provider.

    credentials_encrypted is a Fernet-encrypted JSON blob, e.g. {"api_key": "..."}.
    """

    __tablename__ = "phone_provider_credentials"

    provider = Column(String(50), nullable=False, comment="Provider name (vapi)")

    credentials_encrypted = Column(Text, nullable=False, comment="Fernet-encrypted JSON credentials")

    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PhoneProviderCredential(id={self.id}, provider='{self.provider}', is_active={self.is_active})>"

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        exclude = exclude or set()
        exclude.add("credentials_encrypted")
        return super().to_dict(exclude=exclude)
