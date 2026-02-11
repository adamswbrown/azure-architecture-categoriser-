"""
Design cloud architecture and migration strategies for optimal performance
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="System Architect",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset,
        tools.architecture_toolset,
        # *tools.mcp_servers,
    ],
    instructions=Prompts.persona("system_architect").INSTRUCTIONS,
)
