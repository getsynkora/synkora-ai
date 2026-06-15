"""
Micromobility Dashboard Tools.

Provides tools for managing a micromobility fleet via the Dashboard API.
Covers vehicles, trips, riders, ranger tasks, fleets, areas, and reports.

Auth: JWT Bearer token stored as api_token in OAuthApp (auth_method='api_token').
All endpoint paths are configurable via OAuthApp.config.endpoints.
"""

import base64
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# API endpoint defaults — all overridable via config.endpoints
ENDPOINT_DEFAULTS: dict[str, str] = {
    # Vehicles
    "list_vehicles": "/vehicles/",
    "get_vehicle": "/vehicles/{vehicle_id}/",
    # Trips
    "list_trips": "/trips/",
    "get_trip": "/trips/{trip_id}/",
    # Riders
    "list_riders": "/riders/",
    "get_rider": "/riders/{rider_id}/",
    # Operators
    "list_operators": "/operators/",
    # Ranger Tasks
    "list_tasks": "/tasks/",
    "get_task": "/tasks/{task_id}/",
    "create_task": "/tasks/",
    "update_task": "/tasks/{task_id}/",
    # Fleets
    "list_fleets": "/fleets/",
    # Areas
    "list_service_areas": "/service-areas/",
    "list_parking_areas": "/parking-areas/",
    # Reports
    "list_reports": "/reports/",
    "get_report": "/reports/{report_id}/",
}

# Validation
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_id(value: str, field_name: str) -> str:
    if not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid {field_name}: must contain only alphanumeric characters, hyphens, and underscores")
    return value


def _validate_endpoint_path(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError(f"Endpoint path must start with '/': {path!r}")
    if ".." in path:
        raise ValueError(f"Endpoint path must not contain '..': {path!r}")
    if "?" in path or "#" in path:
        raise ValueError(f"Endpoint path must not contain query params or fragments: {path!r}")
    return path


# ── Core helpers ─────────────────────────────────────────────────────────────


async def _get_micromobility_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    if not runtime_context:
        raise ValueError("No runtime context. Please configure the micromobility integration in OAuth Apps.")

    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    credentials = await resolver.get_micromobility_credentials(tool_name)
    if not credentials:
        raise ValueError("micromobility not configured. Please connect your account in OAuth Apps settings.")

    # If a previous call in this request refreshed the JWT, reuse it so we don't
    # hit another 401 on every paginated page (stale DB token would cause that).
    refreshed = runtime_context.get_state("_mm_refreshed_token")
    if refreshed:
        credentials["api_token"] = refreshed

    # Store runtime_context so _make_micromobility_request can cache refreshed tokens.
    credentials["_runtime_context"] = runtime_context
    return credentials


def _resolve_endpoint(mm_config: dict[str, Any], endpoint_key: str, **path_params: str) -> str:
    endpoints = mm_config.get("endpoints", {})
    raw_path = endpoints.get(endpoint_key) or ENDPOINT_DEFAULTS.get(endpoint_key)
    if not raw_path:
        raise ValueError(f"No endpoint configured for '{endpoint_key}'")
    _validate_endpoint_path(raw_path)
    safe_params = {k: _validate_id(v, k) for k, v in path_params.items()}
    try:
        return raw_path.format(**safe_params)
    except KeyError as e:
        raise ValueError(f"Missing path parameter {e} for endpoint '{endpoint_key}'") from e


async def _make_micromobility_request(
    method: str,
    endpoint: str,
    mm_config: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from src.services.agents.internal_tools.web_tools import _is_url_safe

    base_url = mm_config.get("base_url", "").rstrip("/")
    auth_type = mm_config.get("auth_type")
    timeout = float(mm_config.get("request_timeout_seconds", 30))
    url = f"{base_url}{endpoint}"

    is_safe, ssrf_error = await _is_url_safe(url)
    if not is_safe:
        raise ValueError(f"Request blocked (SSRF protection): {ssrf_error}")
    if not url.startswith("https://"):
        raise ValueError("API base_url must use HTTPS")

    # For form data requests let httpx set Content-Type (multipart boundary)
    headers: dict[str, str] = {"Accept": "application/json"}
    if not form_data:
        headers["Content-Type"] = "application/json"

    if auth_type == "oauth":
        access_token = mm_config.get("access_token")
        if not access_token:
            raise ValueError("OAuth access token not available")
        headers["Authorization"] = f"Bearer {access_token}"
    elif auth_type == "api_key":
        api_token = mm_config.get("api_token")
        if not api_token:
            raise ValueError("API token not available")
        key_header = mm_config.get("api_key_header", "Authorization")
        key_format = mm_config.get("api_key_format", "Bearer {token}")
        headers[key_header] = key_format.format(token=api_token)
    elif auth_type == "basic_auth":
        username = mm_config.get("username")
        password = mm_config.get("password")
        if not username or not password:
            raise ValueError("Basic auth credentials not available")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    else:
        raise ValueError(f"Unsupported auth_type: {auth_type!r}")

    for k, v in mm_config.get("custom_headers", {}).items():
        if k.lower() != "authorization":
            headers[k] = v

    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, data=form_data, timeout=timeout
        )

    if response.status_code == 429:
        return {
            "success": False,
            "error": f"Rate limit exceeded. Retry after: {response.headers.get('Retry-After', 'unknown')}",
            "status_code": 429,
        }

    # 401 with basic_auth: cached JWT has expired — re-login and retry once
    if response.status_code == 401 and mm_config.get("_login_url"):
        login_url = mm_config["_login_url"]
        username = mm_config["_login_username"]
        password = mm_config["_login_password"]
        token_field = mm_config["_login_token_field"]
        username_field = mm_config.get("_login_username_field", "username")
        password_field = mm_config.get("_login_password_field", "password")
        timeout = float(mm_config.get("request_timeout_seconds", 30))
        logger.info(f"JWT expired (401) — re-logging in via {login_url}")
        try:
            async with httpx.AsyncClient(follow_redirects=True) as refresh_client:
                login_resp = await refresh_client.post(
                    login_url,
                    json={username_field: username, password_field: password},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=timeout,
                )
            if not login_resp.is_success:
                return {"success": False, "error": "JWT expired and re-login failed", "status_code": 401}
            new_token = login_resp.json().get(token_field)
            if not new_token:
                return {"success": False, "error": "JWT expired and re-login returned no token", "status_code": 401}
            # Update in-memory config and retry the original request once
            mm_config["api_token"] = new_token
            key_format = mm_config.get("api_key_format", "Bearer {token}")
            key_header = mm_config.get("api_key_header", "Authorization")
            headers[key_header] = key_format.format(token=new_token)
            # Cache on runtime_context.shared_state so subsequent paginated calls reuse
            # this token without hitting another 401 (avoids repeated re-login per page)
            _ctx = mm_config.get("_runtime_context")
            if _ctx is not None:
                _ctx.set_state("_mm_refreshed_token", new_token)
            async with httpx.AsyncClient(follow_redirects=False) as retry_client:
                response = await retry_client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    data=form_data,
                    timeout=timeout,
                )
            if not response.is_success:
                return {
                    "success": False,
                    "error": f"API request failed with status {response.status_code} after token refresh",
                    "status_code": response.status_code,
                }
        except Exception as retry_err:
            logger.error(f"401 retry failed: {retry_err}")
            return {"success": False, "error": f"JWT expired and retry failed: {retry_err}", "status_code": 401}

    if not response.is_success:
        # Include response body for 4xx errors (small, structured JSON) so the LLM
        # can understand what was wrong. Skip for 5xx (large Django traceback HTML).
        error_detail = ""
        if 400 <= response.status_code < 500 and len(response.content) < 2000:
            try:
                error_detail = f": {response.json()}"
            except Exception:
                error_detail = f": {response.text[:500]}"
        return {
            "success": False,
            "error": f"API request failed with status {response.status_code}{error_detail}",
            "status_code": response.status_code,
        }
    try:
        return {"success": True, "data": response.json(), "status_code": response.status_code}
    except Exception:
        return {"success": True, "data": response.text, "status_code": response.status_code}


# ── Vehicle Tools ─────────────────────────────────────────────────────────────


async def internal_micromobility_list_vehicles(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    # Search & identity
    search: str | None = None,
    fleet_id: str | None = None,
    bike_category: str | None = None,
    user: str | None = None,
    country: str | None = None,
    geofence: str | None = None,
    # Battery / heartbeat range filters
    min_power_level: int | None = None,
    max_power_level: int | None = None,
    min_last_heartbeat_time: int | None = None,
    max_last_heartbeat_time: int | None = None,
    # Date range
    start_date: str | None = None,
    end_date: str | None = None,
    # Boolean state flags — only sent when True
    locked: bool | None = None,
    active: bool | None = None,
    damaged: bool | None = None,
    on_ride: bool | None = None,
    on_reservation: bool | None = None,
    parking: bool | None = None,
    missing: bool | None = None,
    iot_fault: bool | None = None,
    geofence_alert: bool | None = None,
    low_battery: bool | None = None,
    rebalance: bool | None = None,
    charging_pick: bool | None = None,
    in_task: bool | None = None,
    is_charging: bool | None = None,
    is_rebalancing: bool | None = None,
    in_maintainance: bool | None = None,
    has_lock: bool | None = None,
    # Pagination
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List fleet vehicles. Test vehicles excluded by default (fetch_test_vehicles not sent)."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_vehicles")
        endpoint = _resolve_endpoint(mm_config, "list_vehicles")
        params: dict[str, Any] = {}

        # Search & identity
        if search:
            params["search"] = search
        if fleet_id:
            params["fleet"] = _validate_id(fleet_id, "fleet_id")
        if bike_category:
            params["bike_category"] = bike_category
        if user:
            params["user"] = _validate_id(user, "user")
        if country:
            params["country"] = country
        if geofence:
            params["geofence"] = geofence

        # Battery / heartbeat range
        if min_power_level is not None:
            params["min_power_level"] = min_power_level
        if max_power_level is not None:
            params["max_power_level"] = max_power_level
        if min_last_heartbeat_time is not None:
            params["min_last_heartbeat_time"] = min_last_heartbeat_time
        if max_last_heartbeat_time is not None:
            params["max_last_heartbeat_time"] = max_last_heartbeat_time

        # Date range
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # Boolean flags — only add when explicitly True
        for flag, key in [
            (locked, "locked"),
            (active, "active"),
            (damaged, "damaged"),
            (on_ride, "on_ride"),
            (on_reservation, "on_reservation"),
            (parking, "parking"),
            (missing, "missing"),
            (iot_fault, "iot_fault"),
            (geofence_alert, "geofence_alert"),
            (low_battery, "low_battery"),
            (rebalance, "rebalance"),
            (charging_pick, "charging_pick"),
            (in_task, "in_task"),
            (is_charging, "is_charging"),
            (is_rebalancing, "is_rebalancing"),
            (in_maintainance, "in_maintainance"),
            (has_lock, "has_lock"),
        ]:
            if flag is True:
                params[key] = "true"

        # Do NOT send fetch_test_vehicles — omitting it returns only real vehicles by default

        # Pagination
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params)
        # Normalize Micromobility paginated response:
        # {"meta": {"count": {"total": N, "page": P}, "summary": {...}}, "data": [...]}
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("vehicles") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["count"] = total
                result["vehicles"] = items
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = (offset or 0) + len(items) < total
            elif isinstance(raw, list):
                result["vehicles"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_vehicles failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_get_vehicle(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    vehicle_id: str = "",
) -> dict[str, Any]:
    """Get full details for a specific vehicle."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_get_vehicle")
        endpoint = _resolve_endpoint(mm_config, "get_vehicle", vehicle_id=vehicle_id)
        return await _make_micromobility_request("GET", endpoint, mm_config)
    except Exception as e:
        logger.error(f"get_vehicle failed: {e}")
        return {"success": False, "error": str(e)}


# ── Trip Tools ────────────────────────────────────────────────────────────────


async def internal_micromobility_list_trips(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    status: str | None = None,
    vehicle_id: str | None = None,
    rider_id: str | None = None,
    fleet_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    search: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    preferred_currency: str | None = None,
    franchise_user: str | None = None,
) -> dict[str, Any]:
    """List trips with optional filtering.

    Status codes: 'C'=completed, 'A'=active/on-trip. Cancelled code unknown.
    Zone identified by bike.fleet.address. Duration in riding_time (seconds).
    Revenue in invoiced_charges.amount (string). Start time in pick_up_time.
    """
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_trips")
        endpoint = _resolve_endpoint(mm_config, "list_trips")
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if vehicle_id:
            params["vehicle"] = _validate_id(vehicle_id, "vehicle_id")
        if rider_id:
            params["user"] = _validate_id(rider_id, "rider_id")
        if fleet_id:
            params["fleet"] = _validate_id(fleet_id, "fleet_id")
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if preferred_currency:
            params["preferred_currency"] = preferred_currency
        if franchise_user:
            params["franchise_user"] = franchise_user
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params or None)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("trips") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["count"] = total
                result["trips"] = items
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = (offset or 0) + len(items) < total
            elif isinstance(raw, list):
                result["trips"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_trips failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_get_trip(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    trip_id: str = "",
) -> dict[str, Any]:
    """Get full details for a specific trip."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_get_trip")
        endpoint = _resolve_endpoint(mm_config, "get_trip", trip_id=trip_id)
        return await _make_micromobility_request("GET", endpoint, mm_config)
    except Exception as e:
        logger.error(f"get_trip failed: {e}")
        return {"success": False, "error": str(e)}


# ── Rider Tools ───────────────────────────────────────────────────────────────


async def internal_micromobility_list_riders(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    search: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    trip_status: str | None = None,
    min_balance: float | None = None,
    max_balance: float | None = None,
    fraud_status: str | None = None,
) -> dict[str, Any]:
    """List riders with optional filters.

    Args:
        search: Search by name, email, or phone.
        status: Rider status filter (e.g. "A" for active).
        limit: Page size.
        offset: Page offset.
        order: Sort order field.
        start_date: Filter by join/activity date from (YYYY-MM-DD).
        end_date: Filter by join/activity date to (YYYY-MM-DD).
        trip_status: Filter by last trip status (e.g. "N" for no trip).
        min_balance: Minimum wallet balance filter.
        max_balance: Maximum wallet balance filter.
        fraud_status: Fraud flag filter (e.g. "N" for non-fraud).
    """
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_riders")
        endpoint = _resolve_endpoint(mm_config, "list_riders")
        params: dict[str, Any] = {}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if order is not None:
            params["order"] = order
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trip_status is not None:
            params["trip_status"] = trip_status
        if min_balance is not None:
            params["min_balance"] = min_balance
        if max_balance is not None:
            params["max_balance"] = max_balance
        if fraud_status is not None:
            params["fraud_status"] = fraud_status
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params or None)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("riders") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["count"] = total
                result["riders"] = items
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = (offset or 0) + len(items) < total
            elif isinstance(raw, list):
                result["riders"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_riders failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_get_rider(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    rider_id: str = "",
) -> dict[str, Any]:
    """Get full details for a specific rider including balance and status."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_get_rider")
        endpoint = _resolve_endpoint(mm_config, "get_rider", rider_id=rider_id)
        return await _make_micromobility_request("GET", endpoint, mm_config)
    except Exception as e:
        logger.error(f"get_rider failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_list_operators(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    limit: int = 10,
    offset: int = 0,
    search: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    is_active: bool | None = None,
    user_status: str | None = None,
    ranger_job_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """List operators/rangers registered on the platform."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_operators")
        endpoint = _resolve_endpoint(mm_config, "list_operators")
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if is_active is not None:
            params["is_active"] = str(is_active).lower()
        if user_status:
            params["user_status"] = user_status
        if ranger_job_type:
            params["ranger_job_type"] = ranger_job_type
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("operators") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["operators"] = items
                result["count"] = total
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = offset + len(items) < total
            elif isinstance(raw, list):
                result["operators"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_operators failed: {e}")
        return {"success": False, "error": str(e)}


# ── Ranger Task Tools ─────────────────────────────────────────────────────────


async def internal_micromobility_list_tasks(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    task_status: str | None = None,
    task_type: str | None = None,
    assigned_to: str | None = None,
    operator_id: str | None = None,
    vehicle_tag: str | None = None,
    vehicle_mode: str | None = None,
    search: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    export: bool | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List ranger tasks (charging, rebalancing, maintenance) with optional filters.

    task_status values: 'TODO', 'PICKED' (in progress), 'DROPPED' (completed), 'CANCELLED'.
    task_type values: 'CHARGING', 'REBALANCING', 'MAINTENANCE', 'UNAVAILABLE'.
    Ranger assigned in: user.id / user.full_name. Filter by assigned_to (ranger user ID).
    Duration: picked_at → dropped_at.
    """
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_tasks")
        endpoint = _resolve_endpoint(mm_config, "list_tasks")
        params: dict[str, Any] = {}
        if task_status:
            params["task_status"] = task_status
        if task_type:
            params["task_type"] = task_type
        if assigned_to:
            params["assigned_to"] = _validate_id(assigned_to, "assigned_to")
        if operator_id:
            params["operator"] = _validate_id(operator_id, "operator_id")
        if vehicle_tag:
            params["vehicle_tag"] = _validate_id(vehicle_tag, "vehicle_tag")
        if vehicle_mode:
            params["vehicle_mode"] = vehicle_mode
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if export is not None:
            params["export"] = "true" if export else "false"
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params or None)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("tasks") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["count"] = total
                result["tasks"] = items
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = (offset or 0) + len(items) < total
            elif isinstance(raw, list):
                result["tasks"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_tasks failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_get_task(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    task_id: str = "",
) -> dict[str, Any]:
    """Get details for a specific ranger task."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_get_task")
        endpoint = _resolve_endpoint(mm_config, "get_task", task_id=task_id)
        return await _make_micromobility_request("GET", endpoint, mm_config)
    except Exception as e:
        logger.error(f"get_task failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_create_task(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    task_type: str = "",
    task_status: str = "TODO",
    title: str | None = None,
    description: str | None = None,
    vehicle_id: str | None = None,
    user: str | None = None,
    priority: str | None = None,
    due_by: str | None = None,
) -> dict[str, Any]:
    """Create a new ranger task. Submitted as multipart form data. Requires HITL approval."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_create_task")
        endpoint = _resolve_endpoint(mm_config, "create_task")
        form: dict[str, Any] = {"task_type": task_type, "task_status": task_status}
        if title:
            form["title"] = title
        if description:
            form["description"] = description
        if vehicle_id:
            form["vehicle"] = _validate_id(vehicle_id, "vehicle_id")
        if user:
            form["user"] = _validate_id(user, "user")
        if priority:
            form["priority"] = priority
        if due_by:
            form["due_by"] = due_by
        return await _make_micromobility_request("POST", endpoint, mm_config, form_data=form)
    except Exception as e:
        logger.error(f"create_task failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_update_task(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    task_id: str = "",
    status: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update a ranger task status or notes. Requires HITL approval."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_update_task")
        endpoint = _resolve_endpoint(mm_config, "update_task", task_id=task_id)
        body: dict[str, Any] = {}
        if status:
            body["status"] = status
        if notes:
            body["notes"] = notes
        return await _make_micromobility_request("PATCH", endpoint, mm_config, json_data=body)
    except Exception as e:
        logger.error(f"update_task failed: {e}")
        return {"success": False, "error": str(e)}


# ── Fleet & Area Tools ────────────────────────────────────────────────────────


async def internal_micromobility_list_fleets(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """List all fleets in the organization.

    Key fields: name, address, status_active, total_vehicles,
    currency.code_alpha, geofence.name (service area), pricing_plans (list),
    visibility, is_default_fleet_for_organization.
    No meta.summary on this endpoint.
    """
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_fleets")
        endpoint = _resolve_endpoint(mm_config, "list_fleets")
        result = await _make_micromobility_request("GET", endpoint, mm_config)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("fleets") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["count"] = total
                result["fleets"] = items
                result["meta"] = meta
            elif isinstance(raw, list):
                result["fleets"] = raw
                result["count"] = len(raw)
        return result
    except Exception as e:
        logger.error(f"list_fleets failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_list_service_areas(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """List service areas (operational zones) with boundaries."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_service_areas")
        endpoint = _resolve_endpoint(mm_config, "list_service_areas")
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("service_areas") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["service_areas"] = items
                result["count"] = total
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = offset + len(items) < total
            elif isinstance(raw, list):
                result["service_areas"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_service_areas failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_list_parking_areas(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """List all designated parking areas with boundaries and compliance stats."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_parking_areas")
        endpoint = _resolve_endpoint(mm_config, "list_parking_areas")
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("parking_areas") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["parking_areas"] = items
                result["count"] = total
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = offset + len(items) < total
            elif isinstance(raw, list):
                result["parking_areas"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_parking_areas failed: {e}")
        return {"success": False, "error": str(e)}


# ── Report Tools ──────────────────────────────────────────────────────────────


async def internal_micromobility_list_reports(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    limit: int = 10,
    offset: int = 0,
    search: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    report_category: str | None = None,
    report_type: str | None = None,
    status: str | None = None,
    fleet: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """List vehicle/trip reports submitted by riders or rangers."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_list_reports")
        endpoint = _resolve_endpoint(mm_config, "list_reports")
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if report_category:
            params["report_category"] = report_category
        if report_type:
            params["report_type"] = report_type
        if status:
            params["status"] = status
        if fleet:
            params["fleet"] = fleet
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        result = await _make_micromobility_request("GET", endpoint, mm_config, params=params)
        if result.get("success"):
            raw = result.get("data")
            if isinstance(raw, dict):
                meta = raw.get("meta") or {}
                count_obj = meta.get("count") or {}
                items = raw.get("data") or raw.get("results") or raw.get("reports") or []
                total = (count_obj.get("total") if isinstance(count_obj, dict) else None) or raw.get(
                    "count", len(items)
                )
                result["reports"] = items
                result["count"] = total
                result["meta"] = meta
                result["summary"] = meta.get("summary") or {}
                result["has_more"] = offset + len(items) < total
            elif isinstance(raw, list):
                result["reports"] = raw
                result["count"] = len(raw)
                result["has_more"] = False
        return result
    except Exception as e:
        logger.error(f"list_reports failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_micromobility_get_report(
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
    report_id: str = "",
) -> dict[str, Any]:
    """Get details and data for a specific report."""
    try:
        mm_config = await _get_micromobility_credentials(runtime_context, "internal_micromobility_get_report")
        endpoint = _resolve_endpoint(mm_config, "get_report", report_id=report_id)
        return await _make_micromobility_request("GET", endpoint, mm_config)
    except Exception as e:
        logger.error(f"get_report failed: {e}")
        return {"success": False, "error": str(e)}
