"""
Common agent tools

All of the tools here should have no agent dependencies so that they can be used in any agent.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic_ai.toolsets import FunctionToolset

# A common toolset that has no agent dependencies
common_tools = FunctionToolset[Any]()


@common_tools.tool
def get_current_utc_time() -> str:
    """Get the current UTC time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
