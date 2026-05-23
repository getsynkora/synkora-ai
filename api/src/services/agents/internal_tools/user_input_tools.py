"""Interactive user input tools for structured chat forms."""

from __future__ import annotations

import re
import uuid
from typing import Any

SUPPORTED_FIELD_TYPES = {
    "boolean",
    "radio",
    "checkbox_group",
    "select",
    "text",
    "textarea",
    "number",
    "scale",
    "image_upload",
    "file_upload",
}

FIELD_TYPE_ALIASES = {
    "checkbox": "boolean",
    "dropdown": "select",
    "multiple_choice": "radio",
    "multi_select": "checkbox_group",
    "short_text": "text",
    "long_text": "textarea",
    "true_false": "boolean",
}

OPTION_FIELD_TYPES = {"radio", "checkbox_group", "select"}
UPLOAD_FIELD_TYPES = {"image_upload", "file_upload"}


def _slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or fallback


def _normalize_option(option: Any, index: int) -> dict[str, str]:
    if isinstance(option, str):
        return {"label": option, "value": _slugify(option, f"option_{index + 1}")}

    if not isinstance(option, dict):
        raise ValueError(f"Option #{index + 1} must be a string or object.")

    label = str(option.get("label") or option.get("value") or "").strip()
    value = str(option.get("value") or label or "").strip()
    if not label or not value:
        raise ValueError(f"Option #{index + 1} must include a label and value.")

    return {"label": label, "value": value}


def _coerce_number(value: Any, field_name: str) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc

    return int(parsed) if parsed.is_integer() else parsed


def _normalize_field(field: Any, index: int) -> dict[str, Any]:
    if not isinstance(field, dict):
        raise ValueError(f"Field #{index + 1} must be an object.")

    field_type_raw = str(field.get("type") or "").strip().lower()
    field_type = FIELD_TYPE_ALIASES.get(field_type_raw, field_type_raw)
    if field_type not in SUPPORTED_FIELD_TYPES:
        supported = ", ".join(sorted(SUPPORTED_FIELD_TYPES))
        raise ValueError(f"Field #{index + 1} has unsupported type '{field_type_raw}'. Supported: {supported}.")

    label = str(field.get("label") or "").strip()
    if not label:
        raise ValueError(f"Field #{index + 1} is missing a label.")

    field_id = str(field.get("id") or "").strip() or _slugify(label, f"field_{index + 1}")

    normalized: dict[str, Any] = {
        "id": field_id,
        "type": field_type,
        "label": label,
        "required": bool(field.get("required", False)),
    }

    optional_string_keys = ["description", "placeholder", "help_text", "submit_hint"]
    for key in optional_string_keys:
        value = field.get(key)
        if value is not None and str(value).strip():
            normalized[key] = str(value).strip()

    if field_type in OPTION_FIELD_TYPES:
        raw_options = field.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            raise ValueError(f"Field '{field_id}' requires a non-empty options array.")
        normalized["options"] = [
            _normalize_option(option, option_index) for option_index, option in enumerate(raw_options)
        ]

    if field_type in {"text", "textarea"}:
        max_length = _coerce_number(field.get("max_length"), "max_length")
        if max_length is not None:
            normalized["max_length"] = int(max_length)

    if field_type == "number":
        for key in ["min", "max", "step"]:
            numeric_value = _coerce_number(field.get(key), key)
            if numeric_value is not None:
                normalized[key] = numeric_value

    if field_type == "scale":
        min_value = _coerce_number(field.get("min"), "min")
        max_value = _coerce_number(field.get("max"), "max")
        step_value = _coerce_number(field.get("step"), "step")
        normalized["min"] = int(min_value if min_value is not None else 1)
        normalized["max"] = int(max_value if max_value is not None else 5)
        normalized["step"] = int(step_value if step_value is not None else 1)
        if normalized["max"] <= normalized["min"]:
            raise ValueError(f"Field '{field_id}' must have max greater than min.")
        if normalized["step"] <= 0:
            raise ValueError(f"Field '{field_id}' must have a positive step.")
        if field.get("min_label"):
            normalized["min_label"] = str(field["min_label"]).strip()
        if field.get("max_label"):
            normalized["max_label"] = str(field["max_label"]).strip()

    if field_type in UPLOAD_FIELD_TYPES:
        max_files = _coerce_number(field.get("max_files"), "max_files")
        normalized["max_files"] = max(1, int(max_files if max_files is not None else 1))
        if field_type == "image_upload":
            normalized["accept"] = ["image/*"]
        else:
            raw_accept = field.get("accept")
            if isinstance(raw_accept, list) and raw_accept:
                normalized["accept"] = [str(item).strip() for item in raw_accept if str(item).strip()]

    default_value = field.get("default_value")
    if default_value is not None:
        normalized["default_value"] = default_value

    return normalized


async def internal_request_user_input(
    title: str,
    fields: list[dict[str, Any]],
    description: str | None = None,
    submit_label: str = "Continue",
    form_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a structured form for the user to complete inline in chat."""
    del config  # Tool is generic and does not currently need runtime config.

    title_value = str(title or "").strip()
    if not title_value:
        return {"success": False, "error": "Form title is required."}

    if not isinstance(fields, list) or not fields:
        return {"success": False, "error": "At least one form field is required."}

    if len(fields) > 12:
        return {"success": False, "error": "Forms are limited to 12 fields for usability."}

    try:
        normalized_fields = [_normalize_field(field, index) for index, field in enumerate(fields)]
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    seen_ids: set[str] = set()
    for field in normalized_fields:
        if field["id"] in seen_ids:
            return {"success": False, "error": f"Duplicate field id '{field['id']}'."}
        seen_ids.add(field["id"])

    generated_form_id = str(form_id).strip() if form_id else f"form_{uuid.uuid4().hex[:10]}"
    normalized_form = {
        "form_id": generated_form_id,
        "title": title_value,
        "description": str(description).strip() if description else "",
        "submit_label": str(submit_label or "Continue").strip() or "Continue",
        "status": "pending",
        "fields": normalized_fields,
    }

    return {
        "success": True,
        "message": "Interactive form prepared for inline user input.",
        "form": normalized_form,
    }
