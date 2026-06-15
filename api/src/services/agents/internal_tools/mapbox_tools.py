"""
Mapbox Tools — generic integration for static maps and directions.

Auth: api_key stored in OAuthApp (provider='mapbox', auth_method='api_token').
All configuration via OAuthApp.config.
"""

import json
import logging
import re
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Common color name → 6-digit hex (Mapbox only accepts 3 or 6-digit hex, no names)
_COLOR_NAME_MAP: dict[str, str] = {
    "red": "f44336",
    "green": "4caf50",
    "blue": "2196f3",
    "yellow": "ffeb3b",
    "orange": "ff9800",
    "purple": "9c27b0",
    "pink": "e91e63",
    "cyan": "00bcd4",
    "white": "ffffff",
    "black": "000000",
    "gray": "9e9e9e",
    "grey": "9e9e9e",
    "brown": "795548",
    "teal": "009688",
    "lime": "8bc34a",
    "indigo": "3f51b5",
    "amber": "ffc107",
    "maroon": "800000",
    "navy": "001f5b",
    "silver": "c0c0c0",
}

_HEX_RE = re.compile(r"^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$")


# Shorthand style names → full Mapbox style IDs
_STYLE_ALIASES: dict[str, str] = {
    "streets": "mapbox/streets-v12",
    "satellite": "mapbox/satellite-v9",
    "satellite-streets": "mapbox/satellite-streets-v12",
    "outdoors": "mapbox/outdoors-v12",
    "light": "mapbox/light-v11",
    "dark": "mapbox/dark-v11",
    "navigation-day": "mapbox/navigation-day-v1",
    "navigation-night": "mapbox/navigation-night-v1",
}


def _normalize_style(style: str) -> str:
    """Return a valid Mapbox style path (username/style_id)."""
    s = style.strip()
    # Check alias table first (e.g. "streets" → "mapbox/streets-v12")
    if s in _STYLE_ALIASES:
        return _STYLE_ALIASES[s]
    # If no slash, assume mapbox/ prefix
    if "/" not in s:
        return f"mapbox/{s}"
    return s


def _normalize_color(color: str | None) -> str:
    """Return a valid 3 or 6-digit hex string for Mapbox (no # prefix)."""
    if not color:
        return "f44336"
    color = color.strip().lstrip("#")
    lower = color.lower()
    if lower in _COLOR_NAME_MAP:
        return _COLOR_NAME_MAP[lower]
    if _HEX_RE.match(color):
        return color
    # Fall back to red if unrecognised
    return "f44336"


async def _get_mapbox_config(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve Mapbox credentials from the linked OAuthApp."""
    from sqlalchemy import select

    from src.core.database import get_async_session_factory
    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.services.agents.security import decrypt_value

    async with get_async_session_factory()() as db:
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == runtime_context.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled,
            )
        )
        agent_tool = result.scalar_one_or_none()
        if not agent_tool or not agent_tool.oauth_app_id:
            raise ValueError(
                f"No OAuth app configured for tool '{tool_name}'. "
                "Please connect a Mapbox OAuth app in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike("mapbox"),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError("No active Mapbox OAuth app found. Check your integrations.")
        if not oauth_app.api_token:
            raise ValueError("Mapbox API key is missing. Edit the OAuth app and add your access token.")

        config = oauth_app.config or {}
        style = _normalize_style(config.get("style", "mapbox/streets-v12"))
        return {
            "access_token": decrypt_value(oauth_app.api_token),
            "style": style,
            "timeout": float(config.get("timeout_seconds", 15)),
        }


def _build_static_map_url(
    access_token: str,
    style: str,
    center_lng: float,
    center_lat: float,
    zoom: int,
    width: int,
    height: int,
    markers: list[dict[str, Any]] | None,
    path: list[dict[str, Any]] | None,
) -> str:
    """Construct a Mapbox Static Images API URL."""
    base = f"https://api.mapbox.com/styles/v1/{style}/static"

    overlays = []
    if markers:
        for m in markers[:20]:  # Mapbox overlay limit
            color = _normalize_color(m.get("color"))
            # Mapbox requires label to be a single lowercase letter a-z or digit 0-9
            raw_label = str(m.get("label", "")).lower()[:1]
            label = quote(raw_label)
            lng = float(m["lng"])
            lat = float(m["lat"])
            pin = f"pin-s-{label}+{color}({lng},{lat})" if label else f"pin-s+{color}({lng},{lat})"
            overlays.append(pin)

    if path and len(path) >= 2:
        # Mapbox requires GeoJSON or encoded polyline — use GeoJSON LineString.
        # Downsample to 25 points max to keep URL under Mapbox's length limit.
        pts = path[:100]
        step = max(1, len(pts) // 25)
        sampled = pts[::step][:25]
        coords = [[round(float(p["lng"]), 6), round(float(p["lat"]), 6)] for p in sampled]
        geojson_str = json.dumps(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"stroke": "#0074D9", "stroke-width": 3, "stroke-opacity": 0.8},
            },
            separators=(",", ":"),
        )
        overlays.append(f"geojson({quote(geojson_str)})")

    overlay_str = ",".join(overlays)
    if overlay_str:
        return f"{base}/{overlay_str}/{center_lng},{center_lat},{zoom}/{width}x{height}?access_token={access_token}"
    return f"{base}/{center_lng},{center_lat},{zoom}/{width}x{height}?access_token={access_token}"


async def internal_get_static_map(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    center_lat: float = 0.0,
    center_lng: float = 0.0,
    zoom: int = 13,
    width: int = 800,
    height: int = 500,
    markers: list[dict[str, Any]] | None = None,
    path: list[dict[str, Any]] | None = None,
    style: str | None = None,
    _resolved_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a Mapbox static map image URL for display in chat.

    Optionally overlay vehicle markers or a route path on the map.
    The returned map_url is a direct image URL that can be rendered inline.

    Args:
        center_lat: Map centre latitude
        center_lng: Map centre longitude
        zoom: Zoom level 0–22 (13 = city block, 15 = street level)
        width: Image width in pixels (max 1280)
        height: Image height in pixels (max 1280)
        markers: List of {lat, lng, label?, color?} — up to 20 markers
        path: List of {lat, lng} ordered coordinates to draw a route line
        style: Mapbox style override (e.g. 'mapbox/satellite-v9'); uses configured default if omitted

    Returns:
        map_url: Static image URL
        embed_url: Interactive Mapbox GL JS embed URL
        center: {lat, lng}
        zoom: effective zoom level
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = _resolved_cfg or await _get_mapbox_config(runtime_context, "internal_get_static_map")
        token = cfg["access_token"]
        map_style = _normalize_style(style) if style else cfg["style"]
        zoom = max(0, min(int(zoom), 22))
        width = max(64, min(int(width), 1280))
        height = max(64, min(int(height), 1280))

        map_url = _build_static_map_url(token, map_style, center_lng, center_lat, zoom, width, height, markers, path)

        # Link to Google Maps — industry standard "open interactive map" pattern
        embed_url = f"https://maps.google.com/?q={center_lat},{center_lng}&z={zoom}"

        return {
            "success": True,
            "map_url": map_url,
            "embed_url": embed_url,
            "center": {"lat": center_lat, "lng": center_lng},
            "zoom": zoom,
            "marker_count": len(markers) if markers else 0,
        }
    except Exception as e:
        logger.error(f"internal_get_static_map failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_get_directions(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    origin_lat: float = 0.0,
    origin_lng: float = 0.0,
    dest_lat: float = 0.0,
    dest_lng: float = 0.0,
    profile: str = "driving",
    waypoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Get driving, cycling, or walking directions between two points via Mapbox Directions API.

    Returns route geometry, duration, and distance. Useful for planning ranger routes
    or calculating travel times for rebalancing operations.

    Args:
        origin_lat / origin_lng: Start coordinates
        dest_lat / dest_lng: End coordinates
        profile: Routing profile — 'driving', 'cycling', 'walking' (default: 'driving')
        waypoints: Optional intermediate stops [{lat, lng}]

    Returns:
        distance_km: Route distance in kilometres
        duration_min: Estimated travel time in minutes
        geometry: Encoded route geometry
        steps: Turn-by-turn instructions
        map_url: Static map of the route
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        import httpx

        cfg = await _get_mapbox_config(runtime_context, "internal_get_directions")
        token = cfg["access_token"]
        valid_profiles = {"driving", "cycling", "walking", "driving-traffic"}
        if profile not in valid_profiles:
            profile = "driving"

        # Build coordinate string: origin → waypoints → destination
        coords = [f"{origin_lng},{origin_lat}"]
        for wp in (waypoints or [])[:23]:  # Mapbox limit: 25 total (incl. origin+dest)
            coords.append(f"{float(wp['lng'])},{float(wp['lat'])}")
        coords.append(f"{dest_lng},{dest_lat}")
        coord_str = ";".join(coords)

        url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coord_str}"
        params = {
            "access_token": token,
            "geometries": "geojson",
            "steps": "true",
            "overview": "full",
        }

        async with httpx.AsyncClient(timeout=cfg["timeout"]) as client:
            resp = await client.get(url, params=params)

        if not resp.is_success:
            return {"success": False, "error": f"Mapbox Directions error {resp.status_code}"}

        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return {"success": False, "error": "No route found between the given coordinates."}

        route = routes[0]
        distance_km = round(route["distance"] / 1000, 2)
        duration_min = round(route["duration"] / 60, 1)

        # Extract turn-by-turn steps
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                steps.append(
                    {
                        "instruction": maneuver.get("instruction", ""),
                        "distance_m": round(step.get("distance", 0)),
                        "duration_s": round(step.get("duration", 0)),
                    }
                )

        # Build static map of the route
        route_coords = route.get("geometry", {}).get("coordinates", [])
        path_points = [{"lng": c[0], "lat": c[1]} for c in route_coords[:: max(1, len(route_coords) // 50)]]

        mid_lat = (origin_lat + dest_lat) / 2
        mid_lng = (origin_lng + dest_lng) / 2

        # Build marker list: origin (A), optional waypoints (numbered), destination (B)
        map_markers: list[dict[str, Any]] = [
            {"lat": origin_lat, "lng": origin_lng, "label": "a", "color": "4caf50"},
        ]
        for i, wp in enumerate((waypoints or [])[:8], start=1):
            map_markers.append({"lat": float(wp["lat"]), "lng": float(wp["lng"]), "label": str(i), "color": "2196f3"})
        map_markers.append({"lat": dest_lat, "lng": dest_lng, "label": "b", "color": "f44336"})

        map_url_result = await internal_get_static_map(
            config=config,
            runtime_context=runtime_context,
            center_lat=mid_lat,
            center_lng=mid_lng,
            zoom=13,
            width=800,
            height=500,
            markers=map_markers,
            path=path_points,
            _resolved_cfg=cfg,
        )

        resolved_map_url = map_url_result.get("map_url") if map_url_result.get("success") else None
        if not resolved_map_url:
            logger.warning(f"internal_get_directions: static map failed — {map_url_result.get('error')}")
        else:
            logger.info(f"internal_get_directions: static map url built ({len(resolved_map_url)} chars)")

        # Google Maps directions URL — shows interactive route with all waypoints
        gmaps_parts = (
            [f"{origin_lat},{origin_lng}"]
            + [f"{float(w['lat'])},{float(w['lng'])}" for w in (waypoints or [])]
            + [f"{dest_lat},{dest_lng}"]
        )
        embed_url = "https://www.google.com/maps/dir/" + "/".join(gmaps_parts)

        return {
            "success": True,
            "profile": profile,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "steps": steps,
            "map_url": resolved_map_url,
            "embed_url": embed_url,
            "origin": {"lat": origin_lat, "lng": origin_lng},
            "destination": {"lat": dest_lat, "lng": dest_lng},
        }
    except Exception as e:
        logger.error(f"internal_get_directions failed: {e}")
        return {"success": False, "error": str(e)}
