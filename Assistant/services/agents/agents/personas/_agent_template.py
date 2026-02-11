"""
Describe your agent inside the docstring to help the delegator understand its purpose.
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts

# Create a basic template agent that's connected to all the common tools and MCP servers
agent = Agent(
    name="Template Agent",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,  # You may want to add more tools here
    ],
    instructions=Prompts.INSTRUCTIONS,
)
