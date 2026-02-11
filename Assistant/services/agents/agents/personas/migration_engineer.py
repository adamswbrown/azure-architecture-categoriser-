"""
Execute technical migrations, troubleshoot issues, and ensure smooth transitions to the cloud
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="Migration Engineer",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset
        # *tools.mcp_servers,
    ],
    instructions=Prompts.persona("migration_engineer").INSTRUCTIONS,
)
