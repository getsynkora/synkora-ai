"""Verified TLS configuration for shared observability clients."""

from src.config.settings import settings


def elasticsearch_tls_options() -> dict:
    options = {"verify_certs": True}
    if settings.elasticsearch_ca_certs:
        options["ca_certs"] = settings.elasticsearch_ca_certs
    return options
