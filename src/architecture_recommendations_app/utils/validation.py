"""Validation utilities for uploaded context files."""

import json
from typing import Tuple, List, Any


# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Error message suggestions
FILE_FORMAT_SUGGESTIONS = [
    "Ensure the file is a valid JSON document",
    "Check that the file is UTF-8 encoded",
    "Verify the file was exported correctly from Dr. Migrate",
]

STRUCTURE_SUGGESTIONS = [
    "Context file must be a JSON array with one object: [{...}]",
    "Ensure the file contains application context data",
]

MISSING_FIELD_SUGGESTIONS = [
    "Ensure your context file includes the app_overview section",
    "Verify the file contains detected_technology_running data",
    "Re-run the assessment tool if data is missing",
]


def validate_uploaded_file(uploaded_file) -> Tuple[bool, str, dict | None, List[str]]:
    """Validate an uploaded context file.

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        Tuple of (is_valid, error_message, parsed_data, suggestions)
    """
    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        return (
            False,
            f"File too large ({uploaded_file.size / 1024 / 1024:.1f}MB). Maximum size is 10MB.",
            None,
            ["Try reducing the file size or removing unnecessary data"],
        )

    # Try to parse JSON
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        data = json.loads(content)
    except UnicodeDecodeError:
        return (
            False,
            "File encoding error. Please ensure the file is UTF-8 encoded.",
            None,
            FILE_FORMAT_SUGGESTIONS,
        )
    except json.JSONDecodeError as e:
        return (
            False,
            f"Invalid JSON format: {e.msg} at line {e.lineno}",
            None,
            FILE_FORMAT_SUGGESTIONS,
        )

    # Validate structure - should be array with one object
    if isinstance(data, list):
        if len(data) == 0:
            return (
                False,
                "Context file is empty.",
                None,
                STRUCTURE_SUGGESTIONS,
            )
        if len(data) > 1:
            return (
                False,
                "Context file should contain exactly one application context.",
                None,
                STRUCTURE_SUGGESTIONS,
            )
        data = data[0]

    if not isinstance(data, dict):
        return (
            False,
            "Context file must be a JSON object or array with one object.",
            None,
            STRUCTURE_SUGGESTIONS,
        )

    # Check required fields
    missing_fields = []

    if "app_overview" not in data:
        missing_fields.append("app_overview")
    elif not data["app_overview"] or not isinstance(data["app_overview"], list):
        return (
            False,
            "app_overview must be a non-empty array",
            None,
            MISSING_FIELD_SUGGESTIONS,
        )
    elif "application" not in data["app_overview"][0]:
        missing_fields.append("app_overview[0].application (application name)")

    if "detected_technology_running" not in data:
        missing_fields.append("detected_technology_running")

    if "server_details" not in data:
        missing_fields.append("server_details")

    if missing_fields:
        return (
            False,
            f"Missing required field(s): {', '.join(missing_fields)}",
            None,
            MISSING_FIELD_SUGGESTIONS,
        )

    # Wrap back in array for compatibility with scorer
    return (True, "", [data], [])


def get_application_name(data: List[dict]) -> str:
    """Extract application name from validated context data."""
    if data and data[0].get("app_overview"):
        return data[0]["app_overview"][0].get("application", "Unknown Application")
    return "Unknown Application"
