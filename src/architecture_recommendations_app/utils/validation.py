"""Validation utilities for uploaded context files."""

import json
from typing import Tuple, List, Any, Optional


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

# LLM Prompt for Dr. Migrate users
DRMIGRATE_LLM_PROMPT = '''For the application "{app_name}", please extract and return the following data as a JSON object.

Return the data in this exact JSON structure:

{{
  "application_overview": {{
    "application": "",
    "number_of_machines": null,
    "number_of_environments": null,
    "environment_names": "",
    "complexity_rating": "",
    "app_function": "",
    "app_type": "",
    "app_owner": "",
    "business_critical": "",
    "inherent_risk": "",
    "high_availability": "",
    "disaster_recovery": "",
    "pii_data": "",
    "unique_operating_systems": "",
    "sql_server_count": "",
    "non_sql_databases": "",
    "other_tech_stack_components": "",
    "assigned_migration_strategy": "",
    "detected_app_components": "",
    "app_component_modernization_options": ""
  }},
  "server_overviews": [
    {{
      "machine": "",
      "application": "",
      "environment": "",
      "OperatingSystem": "",
      "os_support_status": "",
      "CloudVMReadiness": "",
      "AllocatedMemoryInGB": null,
      "Cores": null,
      "CPUUsageInPct": null,
      "MemoryUsageInPct": null,
      "StorageGB": null,
      "DiskReadOpsPerSec": null,
      "DiskWriteOpsPerSec": null,
      "NetworkInMBPS": "",
      "NetworkOutMBPS": ""
    }}
  ],
  "installed_applications": [
    {{
      "machine": "",
      "key_software": "",
      "key_software_category": "",
      "key_software_type": ""
    }}
  ],
  "key_software": [
    {{
      "application": "",
      "key_software": "",
      "key_software_category": ""
    }}
  ],
  "cloud_server_costs": [
    {{
      "machine": "",
      "application": "",
      "assigned_treatment": "",
      "assigned_target": "",
      "cloud_total_cost_annual": null
    }}
  ],
  "app_mod_candidates": [
    {{
      "application": "",
      "app_mod_candidate_technology": "",
      "number_of_machines_with_tech": null
    }}
  ],
  "cost_comparison": {{
    "application": "",
    "current_total_cost_annual": null,
    "cloud_total_cost_annual": null,
    "Currency": "",
    "Symbol": ""
  }}
}}

Query the following data sources:
- Application_Overview for application details
- Server_Overview_Current for all servers
- InstalledApplications for software on each server
- Key_Software for detected key software
- Cloud_Server_Cost for cloud cost projections
- App_Modernization_Candidates if available
- Application_Cost_Comparison for cost comparison

Return ONLY the JSON object, no additional text.'''


def detect_file_format(data: dict) -> str:
    """Detect whether the data is App Cat format or Dr. Migrate format.

    Returns:
        'appcat' - Traditional App Cat context file format
        'drmigrate' - Dr. Migrate LLM export format
        'unknown' - Unrecognized format
    """
    # App Cat format has: app_overview (array), detected_technology_running, server_details
    if isinstance(data, dict):
        if "app_overview" in data and isinstance(data.get("app_overview"), list):
            if "detected_technology_running" in data or "server_details" in data:
                return "appcat"

        # Dr. Migrate format has: application_overview (object), server_overviews
        if "application_overview" in data and isinstance(data.get("application_overview"), dict):
            return "drmigrate"

    return "unknown"


def convert_drmigrate_to_context(data: dict) -> List[dict]:
    """Convert Dr. Migrate format to App Cat context format.

    Args:
        data: Dr. Migrate format data

    Returns:
        Context file format as list with one dict
    """
    # Import here to avoid circular imports
    from architecture_scorer.drmigrate_generator import DrMigrateContextGenerator
    from architecture_scorer.drmigrate_schema import DrMigrateApplicationData

    # Validate and convert using the generator
    app_data = DrMigrateApplicationData.model_validate(data)
    generator = DrMigrateContextGenerator()
    context = generator.generate_context(app_data)

    return context


def get_drmigrate_prompt(app_name: str = "YOUR_APPLICATION_NAME") -> str:
    """Get the LLM prompt for extracting Dr. Migrate data.

    Args:
        app_name: Application name to include in prompt

    Returns:
        Formatted prompt string
    """
    return DRMIGRATE_LLM_PROMPT.format(app_name=app_name)


def validate_uploaded_file(uploaded_file) -> Tuple[bool, str, dict | None, List[str]]:
    """Validate an uploaded context file.

    Supports both traditional App Cat context files and Dr. Migrate LLM exports.
    Dr. Migrate format is automatically converted to context format.

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

    # Handle array wrapper
    original_was_array = isinstance(data, list)
    if original_was_array:
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

    # Detect format
    file_format = detect_file_format(data)

    # Handle Dr. Migrate format - auto-convert
    if file_format == "drmigrate":
        try:
            context_data = convert_drmigrate_to_context(data)
            return (True, "", context_data, [])
        except Exception as e:
            return (
                False,
                f"Error converting Dr. Migrate data: {str(e)}",
                None,
                [
                    "Ensure all required fields are present in the Dr. Migrate export",
                    "Check that application_overview contains the application name",
                    "Verify server_overviews is a valid array",
                ],
            )

    # Handle App Cat format - validate structure
    if file_format == "appcat":
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

    # Unknown format - provide helpful guidance
    return (
        False,
        "Unrecognized file format. Please upload either an App Cat context file or Dr. Migrate data export.",
        None,
        get_format_help_suggestions(data),
    )


def get_format_help_suggestions(data: dict) -> List[str]:
    """Generate helpful suggestions based on what's in the data."""
    suggestions = []

    # Check what fields exist to give targeted advice
    has_app_overview = "app_overview" in data
    has_application_overview = "application_overview" in data
    has_server_details = "server_details" in data
    has_server_overviews = "server_overviews" in data

    if has_application_overview and not has_server_overviews:
        suggestions.append("Dr. Migrate format detected but missing 'server_overviews' - ensure you export server data")
    elif has_app_overview and not has_server_details:
        suggestions.append("App Cat format detected but missing 'server_details'")
    else:
        suggestions.extend([
            "For App Cat context files: Ensure app_overview, detected_technology_running, and server_details are present",
            "For Dr. Migrate exports: Ensure application_overview and server_overviews are present",
            "Use the LLM prompt below to generate correct Dr. Migrate data",
        ])

    return suggestions


def get_application_name(data: List[dict]) -> str:
    """Extract application name from validated context data."""
    if data and data[0].get("app_overview"):
        return data[0]["app_overview"][0].get("application", "Unknown Application")
    return "Unknown Application"


def format_validation_error_with_prompt(
    error_message: str,
    suggestions: List[str],
    app_name: str = "YOUR_APPLICATION_NAME"
) -> dict:
    """Format a validation error with the LLM prompt for Dr. Migrate users.

    Returns:
        Dict with error_message, suggestions, and llm_prompt
    """
    return {
        "error_message": error_message,
        "suggestions": suggestions,
        "llm_prompt": get_drmigrate_prompt(app_name),
        "prompt_instructions": (
            "If you're using Dr. Migrate, copy the prompt below and paste it into "
            "the Dr. Migrate AI Advisor to generate the correct data format:"
        ),
    }
