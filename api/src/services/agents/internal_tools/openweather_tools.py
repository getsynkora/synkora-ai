"""
OpenWeather Tools.

Provides current weather and hourly forecast for any lat/lng.
Computes a demand_modifier (0.0–2.0) that can be used by any agent
— usable by any agent.

Auth: api_key stored in OAuthApp (provider='openweather', auth_method='api_token').
All thresholds are configurable via OAuthApp.config so operators can tune them.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default demand-modifier rules.
# Evaluated top-to-bottom; first match wins.
# Operators can override via OAuthApp.config["weather_demand_rules"].
_DEFAULT_DEMAND_RULES: list[dict[str, Any]] = [
    {"precip_pct_gte": 80, "modifier": 0.30},
    {"precip_pct_gte": 60, "modifier": 0.50},
    {"temp_c_lte": 0, "modifier": 0.45},
    {"temp_c_lte": 5, "modifier": 0.60},
    {"temp_c_gte": 38, "modifier": 0.65},
    {"temp_c_gte": 33, "modifier": 0.80},
    {"wind_mps_gte": 12, "modifier": 0.75},
    {"temp_c_between": [15, 27], "precip_pct_lt": 20, "modifier": 1.25},
    {"temp_c_between": [10, 32], "modifier": 1.0},
]


async def _get_openweather_config(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve OpenWeather credentials from the linked OAuthApp."""
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
                "Please connect an OpenWeather OAuth app in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike("openweather"),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError("No active OpenWeather OAuth app found. Check your integrations.")

        if not oauth_app.api_token:
            raise ValueError("OpenWeather API key is missing. Edit the OAuth app and add your API key.")

        config = oauth_app.config or {}
        return {
            "api_key": decrypt_value(oauth_app.api_token),
            "base_url": config.get("base_url", "https://api.openweathermap.org"),
            "units": config.get("units", "metric"),
            "demand_rules": config.get("weather_demand_rules", _DEFAULT_DEMAND_RULES),
            "timeout": float(config.get("timeout_seconds", 15)),
            "api_version": config.get("api_version", "3.0"),
        }


def _compute_demand_modifier(hour: dict[str, Any], rules: list[dict[str, Any]]) -> float:
    temp = float(hour.get("temp", 20))
    precip_pct = float(hour.get("pop", 0)) * 100
    wind = float(hour.get("wind_speed", 0))

    for rule in rules:
        if "precip_pct_gte" in rule and precip_pct >= rule["precip_pct_gte"]:
            return float(rule["modifier"])
        if "temp_c_lte" in rule and temp <= rule["temp_c_lte"]:
            return float(rule["modifier"])
        if "temp_c_gte" in rule and temp >= rule["temp_c_gte"]:
            return float(rule["modifier"])
        if "wind_mps_gte" in rule and wind >= rule["wind_mps_gte"]:
            return float(rule["modifier"])
        if "temp_c_between" in rule:
            lo, hi = rule["temp_c_between"]
            if lo <= temp <= hi:
                if "precip_pct_lt" in rule and precip_pct >= rule["precip_pct_lt"]:
                    continue
                return float(rule["modifier"])
    return 1.0


async def internal_get_weather_forecast(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    lat: float = 0.0,
    lng: float = 0.0,
    hours_ahead: int = 24,
) -> dict[str, Any]:
    """
    Get hourly weather forecast for any location.

    Returns per-hour temperature, precipitation, wind speed, and a demand_modifier
    that reflects how weather conditions affect outdoor activity / ridership.

    Args:
        lat: Latitude
        lng: Longitude
        hours_ahead: Number of hours to forecast (1–48)

    Returns:
        hours: list of hourly forecasts with demand_modifier
        overall_modifier: mean modifier over the window
        summary: human-readable weather summary
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await _get_openweather_config(runtime_context, "internal_get_weather_forecast")
        hours_ahead = max(1, min(int(hours_ahead), 48))
        api_key = cfg["api_key"]
        base_url = cfg["base_url"].rstrip("/")
        units = cfg["units"]
        rules = cfg["demand_rules"]
        api_version = cfg["api_version"]
        timeout = cfg["timeout"]

        # Try One Call 3.0 first, fall back to free 2.5 forecast
        hourly: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"{base_url}/data/{api_version}/onecall"
            resp = await client.get(
                url,
                params={
                    "lat": lat,
                    "lon": lng,
                    "appid": api_key,
                    "units": units,
                    "exclude": "minutely,daily,alerts",
                },
            )
            if resp.is_success:
                hourly = resp.json().get("hourly", [])[:hours_ahead]
            else:
                # Fallback to 2.5
                resp2 = await client.get(
                    f"{base_url}/data/2.5/forecast",
                    params={
                        "lat": lat,
                        "lon": lng,
                        "appid": api_key,
                        "units": units,
                        "cnt": min(hours_ahead, 40),
                    },
                )
                if resp2.is_success:
                    hourly = resp2.json().get("list", [])[:hours_ahead]
                else:
                    return {"success": False, "error": f"OpenWeather API error {resp2.status_code}"}

        result_hours = []
        modifiers = []
        for h in hourly:
            m = _compute_demand_modifier(h, rules)
            modifiers.append(m)
            result_hours.append(
                {
                    "dt_iso": datetime.fromtimestamp(h["dt"], tz=UTC).isoformat(),
                    "temp": h.get("temp"),
                    "feels_like": h.get("feels_like"),
                    "precip_pct": round(float(h.get("pop", 0)) * 100),
                    "wind_speed": h.get("wind_speed"),
                    "description": (h.get("weather") or [{}])[0].get("description", ""),
                    "demand_modifier": round(m, 2),
                }
            )

        overall = round(sum(modifiers) / len(modifiers), 2) if modifiers else 1.0
        if overall >= 1.15:
            summary = f"Favorable conditions — estimated demand +{round((overall - 1) * 100)}%"
        elif overall <= 0.65:
            summary = f"Poor conditions — estimated demand -{round((1 - overall) * 100)}%"
        else:
            summary = "Neutral conditions — no significant demand impact expected"

        return {
            "success": True,
            "lat": lat,
            "lng": lng,
            "units": units,
            "hours_ahead": hours_ahead,
            "hours": result_hours,
            "overall_modifier": overall,
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"internal_get_weather_forecast failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_get_current_weather(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    lat: float = 0.0,
    lng: float = 0.0,
) -> dict[str, Any]:
    """
    Get current weather conditions for any location.

    Returns temperature, precipitation, wind speed, and a demand_modifier.
    Useful for context in any query about outdoor conditions or activity levels.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await _get_openweather_config(runtime_context, "internal_get_current_weather")
        api_key = cfg["api_key"]
        base_url = cfg["base_url"].rstrip("/")
        units = cfg["units"]
        rules = cfg["demand_rules"]
        timeout = cfg["timeout"]

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base_url}/data/2.5/weather",
                params={
                    "lat": lat,
                    "lon": lng,
                    "appid": api_key,
                    "units": units,
                },
            )

        if not resp.is_success:
            return {"success": False, "error": f"OpenWeather error {resp.status_code}"}

        data = resp.json()
        rain_1h = data.get("rain", {}).get("1h", 0)
        synthetic = {
            "temp": data["main"]["temp"],
            "pop": min(rain_1h / 5.0, 1.0),
            "wind_speed": data["wind"]["speed"],
        }
        modifier = _compute_demand_modifier(synthetic, rules)

        return {
            "success": True,
            "lat": lat,
            "lng": lng,
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "description": (data.get("weather") or [{}])[0].get("description", ""),
            "wind_speed": data["wind"]["speed"],
            "humidity": data["main"]["humidity"],
            "rain_mm_1h": rain_1h,
            "units": units,
            "demand_modifier": round(modifier, 2),
        }
    except Exception as e:
        logger.error(f"internal_get_current_weather failed: {e}")
        return {"success": False, "error": str(e)}
