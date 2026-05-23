"""Register interactive user input tools."""

from __future__ import annotations


def register_user_input_tools(registry) -> None:
    """Register tools that let agents collect structured user input inline."""
    from src.services.agents.internal_tools.user_input_tools import internal_request_user_input

    registry.register_tool(
        name="internal_request_user_input",
        description=(
            "Render an interactive form inside the chat so the user can answer structured questions without typing "
            "free-form text. Use this for checkboxes, true/false, single-choice, multi-select, numeric scales, "
            "short text, long text, and optional file or image uploads.\n\n"
            "Best practices:\n"
            "- Use when the next step depends on structured user input.\n"
            "- Keep forms short and focused, ideally 1-6 fields.\n"
            "- Prefer radio/select for single choice, checkbox_group for multi-select, and boolean for yes/no.\n"
            "- Use image_upload or file_upload only when attachments materially help.\n"
            "- After calling this tool, briefly tell the user what to fill in. Do not reproduce the schema in prose."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title shown at the top of the form.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional supporting text explaining why the form is needed.",
                },
                "submit_label": {
                    "type": "string",
                    "description": "Optional submit button label.",
                    "default": "Continue",
                },
                "form_id": {
                    "type": "string",
                    "description": "Optional stable id if you need to reference the form later.",
                },
                "fields": {
                    "type": "array",
                    "description": (
                        "Ordered list of form fields. Each field must include type and label. "
                        "Supported types: boolean, radio, checkbox_group, select, text, textarea, "
                        "number, scale, image_upload, file_upload."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": [
                                    "boolean",
                                    "true_false",
                                    "checkbox",
                                    "radio",
                                    "checkbox_group",
                                    "select",
                                    "text",
                                    "textarea",
                                    "number",
                                    "scale",
                                    "image_upload",
                                    "file_upload",
                                ],
                            },
                            "label": {"type": "string"},
                            "description": {"type": "string"},
                            "help_text": {"type": "string"},
                            "placeholder": {"type": "string"},
                            "required": {"type": "boolean"},
                            "default_value": {},
                            "options": {
                                "type": "array",
                                "items": {
                                    "anyOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "value": {"type": "string"},
                                            },
                                            "required": ["label", "value"],
                                        },
                                    ]
                                },
                            },
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                            "step": {"type": "number"},
                            "min_label": {"type": "string"},
                            "max_label": {"type": "string"},
                            "max_length": {"type": "integer"},
                            "max_files": {"type": "integer"},
                            "accept": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["type", "label"],
                    },
                },
            },
            "required": ["title", "fields"],
        },
        function=internal_request_user_input,
        tool_category="interaction",
    )
