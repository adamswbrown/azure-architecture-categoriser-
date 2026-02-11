"""
Analyze costs, optimize budgets, and provide financial migration insights
"""
from pydantic_ai import Agent

from .. import tools
from ..deps import AgentDeps
from ..prompts import Prompts


agent = Agent(
    name="Financial Planner",
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset,
    ],
    instructions=Prompts.persona("financial_planner").INSTRUCTIONS,
)
