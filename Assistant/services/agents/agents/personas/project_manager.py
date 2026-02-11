"""
Get app overviews, plan timelines, manage resources, and coordinate migration activities
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="Project Manager",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset,
    ],
    instructions=Prompts.persona("project_manager").INSTRUCTIONS,
)
