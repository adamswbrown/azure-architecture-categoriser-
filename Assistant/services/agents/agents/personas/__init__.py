"""
Agent Personas with Thread-Scoped Dependencies

This module defines the Persona enum and imports all specialized agent personalities.
Each persona is a Pydantic AI Agent configured with AgentDeps for thread-scoped state.

Available Personas:
- CORE: Default generalist agent for cross-cutting queries
- PROJECT_MANAGER: Project management and coordination specialist
- SYSTEM_ARCHITECT: Technical architecture and design expert
- FINANCIAL_PLANNER: Cost optimization and financial analysis
- NETWORK_SPECIALIST: Network infrastructure and connectivity
- MIGRATION_ENGINEER: Migration execution and technical implementation

All agents use AgentDeps (thread_id + database) for proper multi-user isolation.

Usage:
    persona = Persona.CORE
    agent = persona.agent  # Returns Agent[AgentDeps, str]
    description = persona.description  # Returns persona's docstring
"""
from enum import Enum

from pydantic_ai import Agent

# Agent dependencies
from ..deps import AgentDeps

# The core agent which is the default
from .core import agent as core_agent, __doc__ as core_doc

# Additional personas
# This is the pattern to follow for adding new personas
from .project_manager    import agent as project_manager_agent,    __doc__ as project_manager_doc
from .system_architect   import agent as system_architect_agent,   __doc__ as system_architect_doc
from .financial_planner  import agent as financial_planner_agent,  __doc__ as financial_planner_doc
from .network_specialist import agent as network_specialist_agent, __doc__ as network_specialist_doc
from .migration_engineer import agent as migration_engineer_agent, __doc__ as migration_engineer_doc


class Persona(Enum):
    """
    Persona Enum with additional properties and methods for utils
    """
    # The default core agent
    CORE = "core"

    # The specialist agents
    PROJECT_MANAGER = "project manager"
    SYSTEM_ARCHITECT = "system architect"
    FINANCIAL_PLANNER = "financial planner"
    NETWORK_SPECIALIST = "network specialist"
    MIGRATION_ENGINEER = "migration engineer"

    @property
    def agent(self) -> Agent[AgentDeps, str]:
        return {
            Persona.CORE: core_agent,
            Persona.PROJECT_MANAGER: project_manager_agent,
            Persona.SYSTEM_ARCHITECT: system_architect_agent,
            Persona.FINANCIAL_PLANNER: financial_planner_agent,
            Persona.NETWORK_SPECIALIST: network_specialist_agent,
            Persona.MIGRATION_ENGINEER: migration_engineer_agent,
        }[self]

    @property
    def description(self) -> str:
        doc = {
            Persona.CORE: core_doc,
            Persona.PROJECT_MANAGER: project_manager_doc,
            Persona.SYSTEM_ARCHITECT: system_architect_doc,
            Persona.FINANCIAL_PLANNER: financial_planner_doc,
            Persona.NETWORK_SPECIALIST: network_specialist_doc,
            Persona.MIGRATION_ENGINEER: migration_engineer_doc,
        }[self]
        assert doc is not None, "Persona docstring is None"
        return doc

    @classmethod
    def brief(cls) -> str:
        """
        A brief of the available personas.
        
        This gets used to improve the description of the delegation tool at runtime.
        """        
        return (
            "The available agents are:\n"
            f"- **{Persona.CORE.value}**: {Persona.CORE.description}\n"
            f"- **{Persona.PROJECT_MANAGER.value}**: {Persona.PROJECT_MANAGER.description}\n"
            f"- **{Persona.SYSTEM_ARCHITECT.value}**: {Persona.SYSTEM_ARCHITECT.description}\n"
            f"- **{Persona.FINANCIAL_PLANNER.value}**: {Persona.FINANCIAL_PLANNER.description}\n"
            f"- **{Persona.NETWORK_SPECIALIST.value}**: {Persona.NETWORK_SPECIALIST.description}\n"
            f"- **{Persona.MIGRATION_ENGINEER.value}**: {Persona.MIGRATION_ENGINEER.description}\n"
            "Choose the agent that is best suited to answer the user's question based on their description. "
            "If you are unsure, choose the core agent."
        )


if __name__ == "__main__":
    pass
