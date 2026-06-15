"""
Micromobility Tools Registry

Registers all Dashboard micromobility tools with the ADK tool registry.
Covers vehicles, trips, riders, ranger tasks, fleets, areas, and reports.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_micromobility_tools(registry):
    """
    Register all micromobility tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.micromobility_tools import (
        internal_micromobility_create_task,
        internal_micromobility_get_report,
        internal_micromobility_get_rider,
        internal_micromobility_get_task,
        internal_micromobility_get_trip,
        internal_micromobility_get_vehicle,
        internal_micromobility_list_fleets,
        internal_micromobility_list_operators,
        internal_micromobility_list_parking_areas,
        internal_micromobility_list_reports,
        internal_micromobility_list_riders,
        internal_micromobility_list_service_areas,
        internal_micromobility_list_tasks,
        internal_micromobility_list_trips,
        internal_micromobility_list_vehicles,
        internal_micromobility_update_task,
    )

    # ── Vehicle Wrappers ──────────────────────────────────────────────────────

    async def internal_micromobility_list_vehicles_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_vehicles(
            config=config,
            runtime_context=runtime_context,
            search=kwargs.get("search"),
            fleet_id=kwargs.get("fleet_id"),
            bike_category=kwargs.get("bike_category"),
            user=kwargs.get("user"),
            country=kwargs.get("country"),
            geofence=kwargs.get("geofence"),
            min_power_level=kwargs.get("min_power_level"),
            max_power_level=kwargs.get("max_power_level"),
            min_last_heartbeat_time=kwargs.get("min_last_heartbeat_time"),
            max_last_heartbeat_time=kwargs.get("max_last_heartbeat_time"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            locked=kwargs.get("locked"),
            active=kwargs.get("active"),
            damaged=kwargs.get("damaged"),
            on_ride=kwargs.get("on_ride"),
            on_reservation=kwargs.get("on_reservation"),
            parking=kwargs.get("parking"),
            missing=kwargs.get("missing"),
            iot_fault=kwargs.get("iot_fault"),
            geofence_alert=kwargs.get("geofence_alert"),
            low_battery=kwargs.get("low_battery"),
            rebalance=kwargs.get("rebalance"),
            charging_pick=kwargs.get("charging_pick"),
            in_task=kwargs.get("in_task"),
            is_charging=kwargs.get("is_charging"),
            is_rebalancing=kwargs.get("is_rebalancing"),
            in_maintainance=kwargs.get("in_maintainance"),
            has_lock=kwargs.get("has_lock"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )

    async def internal_micromobility_get_vehicle_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_get_vehicle(
            config=config,
            runtime_context=runtime_context,
            vehicle_id=kwargs.get("vehicle_id", ""),
        )

    # ── Trip Wrappers ─────────────────────────────────────────────────────────

    async def internal_micromobility_list_trips_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_trips(
            config=config,
            runtime_context=runtime_context,
            status=kwargs.get("status"),
            vehicle_id=kwargs.get("vehicle_id"),
            rider_id=kwargs.get("rider_id"),
            fleet_id=kwargs.get("fleet_id"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
            search=kwargs.get("search"),
            sort=kwargs.get("sort"),
            order=kwargs.get("order"),
            preferred_currency=kwargs.get("preferred_currency"),
            franchise_user=kwargs.get("franchise_user"),
        )

    async def internal_micromobility_get_trip_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_get_trip(
            config=config,
            runtime_context=runtime_context,
            trip_id=kwargs.get("trip_id", ""),
        )

    # ── Rider Wrappers ────────────────────────────────────────────────────────

    async def internal_micromobility_list_riders_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_riders(
            config=config,
            runtime_context=runtime_context,
            search=kwargs.get("search"),
            status=kwargs.get("status"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
            order=kwargs.get("order"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            trip_status=kwargs.get("trip_status"),
            min_balance=kwargs.get("min_balance"),
            max_balance=kwargs.get("max_balance"),
            fraud_status=kwargs.get("fraud_status"),
        )

    async def internal_micromobility_get_rider_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_get_rider(
            config=config,
            runtime_context=runtime_context,
            rider_id=kwargs.get("rider_id", ""),
        )

    # ── Operator Wrappers ─────────────────────────────────────────────────────

    async def internal_micromobility_list_operators_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_operators(
            config=config,
            runtime_context=runtime_context,
            limit=kwargs.get("limit", 10),
            offset=kwargs.get("offset", 0),
            search=kwargs.get("search"),
            sort=kwargs.get("sort"),
            order=kwargs.get("order"),
            is_active=kwargs.get("is_active"),
            user_status=kwargs.get("user_status"),
            ranger_job_type=kwargs.get("ranger_job_type"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        )

    # ── Ranger Task Wrappers ──────────────────────────────────────────────────

    async def internal_micromobility_list_tasks_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_tasks(
            config=config,
            runtime_context=runtime_context,
            task_status=kwargs.get("task_status"),
            task_type=kwargs.get("task_type"),
            assigned_to=kwargs.get("assigned_to"),
            operator_id=kwargs.get("operator_id"),
            vehicle_tag=kwargs.get("vehicle_tag"),
            vehicle_mode=kwargs.get("vehicle_mode"),
            search=kwargs.get("search"),
            sort=kwargs.get("sort"),
            order=kwargs.get("order"),
            export=kwargs.get("export"),
            limit=kwargs.get("limit"),
            offset=kwargs.get("offset"),
        )

    async def internal_micromobility_get_task_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_get_task(
            config=config,
            runtime_context=runtime_context,
            task_id=kwargs.get("task_id", ""),
        )

    async def internal_micromobility_create_task_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        # Normalize priority: LLM may send full words instead of single-letter codes
        _priority_map = {"high": "H", "medium": "M", "low": "L", "urgent": "U"}
        raw_priority = kwargs.get("priority")
        priority = _priority_map.get(str(raw_priority).lower(), raw_priority) if raw_priority else None
        return await internal_micromobility_create_task(
            config=config,
            runtime_context=runtime_context,
            task_type=kwargs.get("task_type", ""),
            task_status=kwargs.get("task_status", "TODO"),
            title=kwargs.get("title"),
            description=kwargs.get("description"),
            vehicle_id=kwargs.get("vehicle_id"),
            user=kwargs.get("user"),
            priority=priority,
            due_by=kwargs.get("due_by"),
        )

    async def internal_micromobility_update_task_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_update_task(
            config=config,
            runtime_context=runtime_context,
            task_id=kwargs.get("task_id", ""),
            status=kwargs.get("status"),
            notes=kwargs.get("notes"),
        )

    # ── Fleet & Area Wrappers ─────────────────────────────────────────────────

    async def internal_micromobility_list_fleets_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_fleets(config=config, runtime_context=runtime_context)

    async def internal_micromobility_list_service_areas_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_service_areas(
            config=config,
            runtime_context=runtime_context,
            limit=kwargs.get("limit", 10),
            offset=kwargs.get("offset", 0),
        )

    async def internal_micromobility_list_parking_areas_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_parking_areas(
            config=config,
            runtime_context=runtime_context,
            limit=kwargs.get("limit", 10),
            offset=kwargs.get("offset", 0),
        )

    # ── Report Wrappers ───────────────────────────────────────────────────────

    async def internal_micromobility_list_reports_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_list_reports(
            config=config,
            runtime_context=runtime_context,
            limit=kwargs.get("limit", 10),
            offset=kwargs.get("offset", 0),
            search=kwargs.get("search"),
            sort=kwargs.get("sort"),
            order=kwargs.get("order"),
            report_category=kwargs.get("report_category"),
            report_type=kwargs.get("report_type"),
            status=kwargs.get("status"),
            fleet=kwargs.get("fleet"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        )

    async def internal_micromobility_get_report_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_micromobility_get_report(
            config=config,
            runtime_context=runtime_context,
            report_id=kwargs.get("report_id", ""),
        )

    # ── Register Vehicle Tools ────────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_vehicles",
        description=(
            "List vehicles in the micromobility fleet. Test vehicles are never included unless explicitly requested. "
            "Response includes 'count' (total matching) and 'results' (current page). "
            "Always paginate: use limit + offset when count > limit."
        ),
        parameters={
            "type": "object",
            "properties": {
                # Search & identity
                "search": {"type": "string", "description": "Search by vehicle ID, serial number, or QR code"},
                "fleet_id": {"type": "string", "description": "Filter by fleet ID"},
                "bike_category": {
                    "type": "string",
                    "description": "Filter by vehicle category (e.g. 'P' for pedal, 'E' for electric)",
                },
                "user": {
                    "type": "string",
                    "description": "Filter by rider/user UUID — vehicles last unlocked by this user",
                },
                "country": {"type": "string", "description": "Filter by country code"},
                "geofence": {
                    "type": "string",
                    "description": "Filter by service area UUID (the 'id' field from list_service_areas). Must be a UUID — NOT the service area name or fleet name. Passing a name instead of a UUID causes a 500 error.",
                },
                # Battery & heartbeat range
                "min_power_level": {"type": "integer", "description": "Minimum battery level (0–100)"},
                "max_power_level": {"type": "integer", "description": "Maximum battery level (0–100)"},
                "min_last_heartbeat_time": {"type": "integer", "description": "Minimum hours since last IoT heartbeat"},
                "max_last_heartbeat_time": {"type": "integer", "description": "Maximum hours since last IoT heartbeat"},
                # Date range
                "start_date": {"type": "string", "description": "Filter from date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Filter to date (YYYY-MM-DD)"},
                # Boolean state flags — set true to filter to matching vehicles only
                "locked": {"type": "boolean", "description": "Only vehicles that are locked"},
                "active": {"type": "boolean", "description": "Only active (deployed) vehicles"},
                "damaged": {"type": "boolean", "description": "Only damaged vehicles"},
                "on_ride": {"type": "boolean", "description": "Only vehicles currently on an active trip"},
                "on_reservation": {"type": "boolean", "description": "Only vehicles currently reserved"},
                "parking": {"type": "boolean", "description": "Only vehicles in a parking zone"},
                "missing": {"type": "boolean", "description": "Only vehicles flagged as missing"},
                "iot_fault": {"type": "boolean", "description": "Only vehicles with an IoT fault"},
                "geofence_alert": {"type": "boolean", "description": "Only vehicles with an active geofence alert"},
                "low_battery": {"type": "boolean", "description": "Only low-battery vehicles"},
                "rebalance": {"type": "boolean", "description": "Only vehicles flagged for rebalancing"},
                "charging_pick": {"type": "boolean", "description": "Only vehicles flagged for charging pickup"},
                "in_task": {"type": "boolean", "description": "Only vehicles currently assigned to a ranger task"},
                "is_charging": {"type": "boolean", "description": "Only vehicles currently being charged"},
                "is_rebalancing": {"type": "boolean", "description": "Only vehicles currently being rebalanced"},
                "in_maintainance": {"type": "boolean", "description": "Only vehicles currently in maintenance"},
                "has_lock": {"type": "boolean", "description": "Only vehicles that have a physical lock attached"},
                # Pagination
                "limit": {"type": "integer", "description": "Page size — number of vehicles per page"},
                "offset": {
                    "type": "integer",
                    "description": "Pagination offset (skip N results). offset = page_number * limit",
                },
            },
            "required": [],
        },
        function=internal_micromobility_list_vehicles_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_get_vehicle",
        description=(
            "Get full details for a specific vehicle including battery level, GPS coordinates, "
            "lock status, fleet assignment, and recent trip history."
        ),
        parameters={
            "type": "object",
            "properties": {
                "vehicle_id": {"type": "string", "description": "Vehicle ID"},
            },
            "required": ["vehicle_id"],
        },
        function=internal_micromobility_get_vehicle_wrapper,
    )

    # ── Register Trip Tools ───────────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_trips",
        description=(
            "List trips with optional filtering by status, vehicle, rider, fleet, or date range. "
            "Key fields: status ('C'=completed, 'A'=active), pick_up_time, drop_off_time, "
            "riding_time (seconds), distance (string km), invoiced_charges.amount (string, base fare), "
            "bike.id, bike.qr_code, bike.fleet.address (zone grouping — list endpoint only, no fleet name), "
            "user.id, user.full_name, vehicle_was_legally_parked (bool), was_paused, "
            "went_outside_geofence, status_forced, is_refunded. "
            "NOTE: for full cost breakdown, zone name, battery levels use get_trip on individual IDs. "
            "Summary (meta.summary): completed, cancelled, on_trip, force_completed, "
            "good_feedback, bad_feedback, total."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status code: 'C'=completed, 'A'=active/on-trip. Omit for all.",
                },
                "vehicle_id": {"type": "string", "description": "Filter by vehicle ID"},
                "rider_id": {"type": "string", "description": "Filter by rider/user ID"},
                "fleet_id": {"type": "string", "description": "Filter by fleet ID"},
                "start_date": {"type": "string", "description": "Filter from date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Filter to date (YYYY-MM-DD)"},
                "limit": {"type": "integer", "description": "Page size"},
                "offset": {"type": "integer", "description": "Pagination offset"},
                "search": {"type": "string", "description": "Search trips (e.g. by QR code or rider name)"},
                "sort": {"type": "string", "description": "Sort field"},
                "order": {"type": "string", "description": "Sort direction ('asc' or 'desc')"},
                "preferred_currency": {"type": "string", "description": "Currency UUID for charge amounts"},
                "franchise_user": {"type": "string", "description": "Filter by franchise user ID"},
            },
            "required": [],
        },
        function=internal_micromobility_list_trips_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_get_trip",
        description=(
            "Get full details for a specific trip. "
            "Key fields: status ('C'=completed), pick_up_time, drop_off_time, riding_time (seconds), "
            "trip_duration (human string e.g. '1 min'), distance (string km), "
            "cost (float, base fare in local currency), total_cost (float, with fees+tax), "
            "currency.code_alpha, tax_amount, tax_rate, additional_fees (list), "
            "start_power_level / end_power_level (string %, battery at trip start/end — only available here not in list), "
            "geofence.name (service area e.g. 'Niketan-HQ'), geofence.fleet.name (fleet e.g. 'Micromobility-HQ'), "
            "bike.battery_charge (current %), bike.qr_code, bike.current_loc_coord, "
            "user.full_name, user.email, user.phone_number, "
            "vehicle_was_legally_parked, was_paused, went_outside_geofence, "
            "invoice (full payment record with amount, currency, payment_method, refund status), "
            "penalties (list of penalty charges), notes (list of billing audit notes), "
            "rating, received_good_feedback, is_refunded, src_coord, dest_coord."
        ),
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "Trip ID"},
            },
            "required": ["trip_id"],
        },
        function=internal_micromobility_get_trip_wrapper,
    )

    # ── Register Rider Tools ──────────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_riders",
        description=(
            "List riders registered on the platform. Supports search and multiple filters. "
            "Returns rider profile, wallet balance (field: 'balance'), status (field: 'user_status', "
            "'A'=active), nearby fleet (field: 'nearby_fleet.name'), is_test_user, joining_date, "
            "last_login, last_trip_status. Summary includes total, active, negative_balance counts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Search by name, email, or phone number"},
                "status": {
                    "type": "string",
                    "description": "Filter by rider user_status: 'A' for active",
                },
                "limit": {"type": "integer", "description": "Page size"},
                "offset": {"type": "integer", "description": "Pagination offset"},
                "order": {"type": "string", "description": "Sort order field (e.g. '-joining_date' for newest first)"},
                "start_date": {"type": "string", "description": "Filter from date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Filter to date (YYYY-MM-DD)"},
                "trip_status": {"type": "string", "description": "Filter by last trip status ('N' = no trip)"},
                "min_balance": {"type": "number", "description": "Minimum wallet balance filter"},
                "max_balance": {"type": "number", "description": "Maximum wallet balance filter"},
                "fraud_status": {"type": "string", "description": "Fraud flag filter ('N' = non-fraud)"},
            },
            "required": [],
        },
        function=internal_micromobility_list_riders_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_get_rider",
        description=(
            "Get full profile for a specific rider including wallet balance, trip history, "
            "account status, and payment methods."
        ),
        parameters={
            "type": "object",
            "properties": {
                "rider_id": {"type": "string", "description": "Rider ID"},
            },
            "required": ["rider_id"],
        },
        function=internal_micromobility_get_rider_wrapper,
    )

    # ── Register Operator Tools ───────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_operators",
        description=(
            "List operators (rangers) registered on the platform. "
            "Response includes 'operators' (array), 'count' (total), 'has_more' (boolean), "
            "'summary' (total, total_completed_task, total_ongoing_task). "
            "Each operator has: id, full_name, username, phone_number, "
            "user_status ('A'=active), last_login, total_points."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Page size (default 10)"},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
                "search": {"type": "string", "description": "Search by name, username, or phone number"},
                "sort": {"type": "string", "description": "Field to sort by"},
                "order": {"type": "string", "description": "Sort direction: 'asc' or 'desc'"},
                "is_active": {"type": "boolean", "description": "Filter by active status"},
                "user_status": {"type": "string", "description": "Filter by user_status: 'A' for active"},
                "ranger_job_type": {
                    "type": "string",
                    "description": "Filter by job type: 'FULLTIME' or 'PARTTIME'",
                },
                "start_date": {"type": "string", "description": "Filter from date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Filter to date (YYYY-MM-DD)"},
            },
            "required": [],
        },
        function=internal_micromobility_list_operators_wrapper,
    )

    # ── Register Ranger Task Tools ────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_tasks",
        description=(
            "List ranger/operator tasks. "
            "Key fields: task_status ('TODO'=not started, 'PICKED'=in progress, 'DROPPED'=completed, 'CANCELLED'), "
            "task_type ('CHARGING', 'REBALANCING', 'MAINTENANCE', 'UNAVAILABLE'), "
            "title, description, due_by, created_at, "
            "picked_at (when ranger started), dropped_at (when completed), "
            "picked_charge / dropped_charge (string amounts), "
            "user.id / user.full_name (assigned ranger), "
            "created_by.full_name (who created the task), "
            "vehicle.qr_code / vehicle.name / vehicle.location. "
            "Summary (meta.summary): done, ongoing, charging, rebalancing, total."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task_status": {
                    "type": "string",
                    "description": "Filter by task_status: 'TODO', 'PICKED' (in progress), 'DROPPED' (completed), 'CANCELLED'",
                },
                "task_type": {
                    "type": "string",
                    "description": "Filter by task_type: 'CHARGING', 'REBALANCING', 'MAINTENANCE', 'UNAVAILABLE'",
                },
                "assigned_to": {"type": "string", "description": "Filter by assigned ranger user ID"},
                "operator_id": {"type": "string", "description": "Filter by org-level operator ID"},
                "vehicle_tag": {"type": "string", "description": "Filter by vehicle tag/group UUID"},
                "vehicle_mode": {"type": "string", "description": "Filter by vehicle mode (e.g. 'CHARGING')"},
                "search": {"type": "string", "description": "Search tasks by keyword"},
                "sort": {"type": "string", "description": "Sort field"},
                "order": {"type": "string", "description": "Sort direction ('asc' or 'desc')"},
                "export": {"type": "boolean", "description": "Set true to export results"},
                "limit": {"type": "integer", "description": "Page size"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "required": [],
        },
        function=internal_micromobility_list_tasks_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_get_task",
        description=(
            "Get full details for a specific ranger task. "
            "Key fields (beyond list): priority ('H'=high, 'M'=medium, 'L'=low, 'U'=urgent), "
            "picked_by.full_name (who picked it up), dropped_by.full_name (who completed it), "
            "cancelled_at, payment_status ('UNPAID'/'PAID'), "
            "earned_amount, earned_point, files, tags, dropped_photo, dropped_parking. "
            "Response is a flat object (no meta wrapper)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
            },
            "required": ["task_id"],
        },
        function=internal_micromobility_get_task_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_create_task",
        description=(
            "Create a new ranger task and assign it to an operator. Requires confirmation before submitting. "
            "PRE-FLIGHT CHECKLIST — you MUST complete all steps before calling this tool:\n"
            "1. OPERATOR ID: 'user' is required. If you do not have a real operator UUID from this session, "
            "call internal_micromobility_list_operators first and use the 'id' field from the result. "
            "Never guess or fabricate a UUID.\n"
            "2. VEHICLE ID: If the task involves a specific vehicle, use the vehicle's actual UUID "
            "(from list_vehicles or a previous tool result). Never fabricate a UUID.\n"
            "3. PRIORITY CODE: Must be a single letter — 'H' (high), 'M' (medium), 'L' (low), 'U' (urgent). "
            "Never send the full word (e.g. 'high' will be rejected by the API).\n"
            "4. TASK TYPE: Must be exactly 'CHARGING', 'REBALANCING', 'MAINTENANCE', or 'UNAVAILABLE'.\n"
            "If any required value is missing, gather it via the appropriate list tool first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "description": "Task type — exactly one of: 'CHARGING', 'REBALANCING', 'MAINTENANCE', 'UNAVAILABLE'",
                },
                "user": {
                    "type": "string",
                    "description": "REQUIRED. Operator/ranger user UUID to assign the task to. Must come from internal_micromobility_list_operators — never fabricate.",
                },
                "task_status": {
                    "type": "string",
                    "description": "Initial status: 'TODO' (default), 'PICKED', 'DROPPED', 'CANCELLED'",
                },
                "title": {"type": "string", "description": "Short title for the task"},
                "description": {
                    "type": "string",
                    "description": "Detailed task description or instructions for the ranger",
                },
                "vehicle_id": {
                    "type": "string",
                    "description": "Vehicle UUID to assign the task to. Must come from list_vehicles — never fabricate.",
                },
                "priority": {
                    "type": "string",
                    "description": "Single-letter priority code: 'H' (high), 'M' (medium), 'L' (low), 'U' (urgent). Do NOT send full words.",
                },
                "due_by": {
                    "type": "string",
                    "description": "Due date/time in ISO 8601 format (e.g. 2026-04-30T10:00:00Z)",
                },
            },
            "required": ["task_type", "user"],
        },
        function=internal_micromobility_create_task_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_micromobility_update_task",
        description="Update a ranger task's status or notes. Use to mark tasks as started, completed, or cancelled. Requires confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to update"},
                "status": {
                    "type": "string",
                    "description": "New status: 'TODO' (not started), 'PICKED' (in progress), 'DROPPED' (completed), 'CANCELLED'",
                },
                "notes": {"type": "string", "description": "Updated notes or comments"},
            },
            "required": ["task_id"],
        },
        function=internal_micromobility_update_task_wrapper,
        tool_category="action",
    )

    # ── Register Fleet & Area Tools ───────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_fleets",
        description=(
            "List all fleets in the organization. "
            "Key fields: name (fleet name e.g. 'Micromobility-HQ'), address (physical location), "
            "status_active (bool), total_vehicles (int), currency.code_alpha, "
            "geofence.name (associated service area name), "
            "pricing_plans (list of {name, bike_category_display_text}), "
            "visibility ('PU'=public), is_default_fleet_for_organization. "
            "Results in result['fleets']. No summary in meta."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=internal_micromobility_list_fleets_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_list_service_areas",
        description=(
            "List operational service areas (geofenced zones). "
            "Response includes 'service_areas' (array), 'count' (total), "
            "'summary' (total, vehicles_assigned, vehicles_inside, vehicles_outside), 'has_more'. "
            "Each area has: id, name, is_active, is_default_service_area_for_swapping, "
            "vehicles_inside (int — vehicles currently inside this zone), "
            "exit_speed_mode ('L'=low, 'M'=medium, 'H'=high), reset_speed_mode_for_exiting (bool), "
            "coords (polygon boundary as a string of lat/lon pairs), "
            "fleet.id, fleet.name, fleet.city.name, fleet.city.timezone, "
            "fleet.country.name, fleet.country.code2, fleet.country.currency_code_alpha, "
            "fleet.high_speed_limit, fleet.low_speed_limit, fleet.medium_speed_limit."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Page size (default 10)"},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
            },
            "required": [],
        },
        function=internal_micromobility_list_service_areas_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_list_parking_areas",
        description=(
            "List all designated parking areas (hubs) within service zones. "
            "Response includes 'parking_areas' (array), 'count' (total), 'has_more', "
            "'summary' (total, legally_parked, illegally_parked — vehicle counts across all areas). "
            "Each area has: id, name, is_active, address (nullable), "
            "center_coords (string 'lat,lon'), coords (polygon boundary string), "
            "end_ride_picture (bool — whether photo is required on park), "
            "geofence.id, geofence.name (parent service area name), "
            "geofence.fleet.id, geofence.fleet.name, "
            "geofence.speed_limit.speed_choice ('Low'/'Medium'/'High'), geofence.speed_limit.speed_value."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Page size (default 10)"},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
            },
            "required": [],
        },
        function=internal_micromobility_list_parking_areas_wrapper,
    )

    # ── Register Report Tools ─────────────────────────────────────────────────

    registry.register_tool(
        name="internal_micromobility_list_reports",
        description=(
            "List vehicle/trip reports submitted by riders or rangers. "
            "Response includes 'reports' (array), 'count' (total), 'summary' (pending/verified/total counts), "
            "'has_more' (boolean), and 'meta'. "
            "Each report has: id, created_at, report_date, "
            "report_category ('Damaged Vehicle' or 'Wrongly Parked'), "
            "report_moment ('After Trip', 'Before Trip', 'On Feedback'), "
            "report_type ('Trip' or 'Non-Trip'), "
            "status ('Unverified' or 'Verified'), "
            "subject (free text description), "
            "vehicle_parts (array of affected parts: 'BATTERY', 'LIGHTS', 'THROTTLE', 'TIRE', 'NOISE', 'SLOW', 'HANDLEBAR', 'CHASSIS', 'BRAKE', 'KICKSTAND', 'OTHER'), "
            "bike (vehicle object with qr_code, bike_short_id, battery_charge), "
            "user (reporter: id, full_name, role_name), "
            "prev_trip_user (previous trip rider: id, full_name, role_name)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of results per page (default 10)"},
                "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
                "search": {"type": "string", "description": "Search by vehicle tag, subject, or reporter name"},
                "sort": {"type": "string", "description": "Field to sort by"},
                "order": {"type": "string", "description": "Sort direction: 'asc' or 'desc'"},
                "report_category": {
                    "type": "string",
                    "description": "Filter by category: 'Damaged Vehicle' or 'Wrongly Parked'",
                },
                "report_type": {"type": "string", "description": "Filter by type: 'Trip' or 'Non-Trip'"},
                "status": {"type": "string", "description": "Filter by status: 'Unverified' or 'Verified'"},
                "fleet": {"type": "string", "description": "Filter by fleet ID"},
                "start_date": {"type": "string", "description": "Filter reports from this date (ISO 8601)"},
                "end_date": {"type": "string", "description": "Filter reports up to this date (ISO 8601)"},
            },
            "required": [],
        },
        function=internal_micromobility_list_reports_wrapper,
    )

    registry.register_tool(
        name="internal_micromobility_get_report",
        description=(
            "Get full details for a specific report by ID. Response is a flat object (no data wrapper). "
            "Top-level fields: id, created_at, updated_at, report_date, report_category, status ('Unverified'/'Verified'), "
            "description (free text), admin_remarks (nullable), "
            "vehicle_qr (QR code e.g. 'LDYLVW7'), vehicle_short_id, vehicle_id, "
            "vehicle_parts (array e.g. ['BATTERY']), report_images (array of image URLs), "
            "user (reporter: id, full_name, role_name, add_point), "
            "prev_trip_user (previous trip rider: id, full_name, role_name, deduct_point), "
            "user_point / prev_trip_user_point (nullable point adjustments), "
            "trip (full inline trip object for the trip associated with the report — includes status, "
            "pick_up_time via created_at, riding_time, distance, total_cost, rating, trip_short_id, "
            "vehicle_was_legally_parked, start_power_level, end_power_level, parking_pic), "
            "prev_trip (full inline object for the previous trip — same structure as trip), "
            "trip_invoice (inline invoice: amount, currency.code_alpha, currency.symbol, "
            "status, is_refunded, finalized_refund_status_display_text, payment_method), "
            "prev_trip_invoice_id, prev_trip_parking_pic."
        ),
        parameters={
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "description": "Report ID"},
            },
            "required": ["report_id"],
        },
        function=internal_micromobility_get_report_wrapper,
    )

    logger.info(
        "Registered 16 micromobility tools (2 vehicle + 2 trip + 2 rider + 1 operator + 4 task + 3 area + 2 report)"
    )
