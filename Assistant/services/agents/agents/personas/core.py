"""
Cloud migration generalist
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="core",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset
        # *tools.mcp_servers,
    ],
    instructions=Prompts.INSTRUCTIONS,
)
