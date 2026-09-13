"""Exact HTTP origins for credential-bearing browser and integration requests."""

from urllib.parse import urlsplit


def http_origin(value: str) -> tuple[str, str, int]:
    if not isinstance(value, str) or any(ord(c) <= 32 for c in value) or "\\" in value:
        raise ValueError("Invalid HTTP origin")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Invalid HTTP origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Expected an origin without a path, query or fragment")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname.lower(), port


def allowed_dashboard_origin(origin: str, origins: list[str]) -> bool:
    try:
        candidate = http_origin(origin)
    except ValueError:
        return False
    for configured in origins:
        try:
            if candidate == http_origin(configured):
                return True
        except ValueError:
            continue
    return False


def dashboard_origins() -> list[str]:
    from src.config import settings

    origins = settings.cors_origins
    if settings.is_development and (not origins or origins == ["*"]):
        return [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 3001, 3005)]
    return origins
