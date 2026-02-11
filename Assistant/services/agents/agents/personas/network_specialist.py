"""
Configure networking, security and connectivity for cloud infrastructure
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="Network Specialist",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset
        # *tools.mcp_servers,
    ],
    instructions=Prompts.persona("network_specialist").INSTRUCTIONS,
)
