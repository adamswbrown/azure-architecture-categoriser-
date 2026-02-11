"""
Agent dependencies

This provides the AgentDeps model which will handle any thread-specific contextual information.
See https://ai.pydantic.dev/dependencies/ for how agent dependencies work in pydantic-ai.

Also see https://ai.pydantic.dev/ui/ag-ui/#state-management for how AG-UI StateDeps are implemented
if we ever want to integrate shared state into the frontend.

The pydantic-ai library will do most of the heavy lifting if we make AgentState a pydantic.BaseModel,
see [here](https://github.com/pydantic/pydantic-ai/blob/6c01b5258fb37f82386b1668a4f4a98f1b56f257/pydantic_ai_slim/pydantic_ai/ui/_adapter.py#L239)
for implementation details.
"""
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel

from .virtual_database import VirtualDatabase



@dataclass
class SuggestionItem:
    pill_text: str
    suggestion: str

    def format_suggestion_line(self) -> str:
        return f"**{self.pill_text}**: {self.suggestion}"

class AgentState(BaseModel):
    """
    The state for the agent synchronized between the backend and frontend.

    - This dataclass **must** be JSON serializable so ensure that all fields are of JSON-compatible types.
    - See https://ai.pydantic.dev/ui/ag-ui/#state-management for implementation details
    - See https://docs.ag-ui.com/concepts/state for the explicit protocol docs

    Attributes:
        persona (str): The active persona for the agent.
        auto_specialist (bool): Whether to delegate before each response.
        user_id (Optional[str]): User identifier for usage tracking and quota enforcement.
    """
    persona: str  # The active persona
    auto_specialist: bool  # Whether to delegate before each response
    suggestions: list[SuggestionItem] = []  # Suggested follow-up questions or actions
    user_id: Optional[str] = None  # User ID for usage tracking

@dataclass
class AgentDeps:
    """
    Agent dependencies for thread-scoped state.

    Implements the [StateHandler protocol](https://ai.pydantic.dev/api/ag_ui/#pydantic_ai.ag_ui.StateHandler)

    Attributes:
        state (AgentState): The AG-UI synchronized state for the agent.
        thread_id (str): Unique identifier for the conversation thread.
        database (VirtualDatabase): Virtual database instance for the thread.
        migration_target (str): Target cloud provider for migration (e.g., "Azure", "AWS", "GCP").
            Used for prompt variable replacement: {{MIGRATION_TARGET}} -> migration_target
        llm_provider (Literal["openai", "claude", "gemini"]): LLM provider for prompt customization.
            Enables loading provider-specific prompt files (e.g., prompts/core/gemini/STYLE.md)
    """
    # AG-UI State
    state: AgentState

    # Used for tools, prompt values, etc
    thread_id: str
    database: VirtualDatabase
    migration_target: str

    # Used for prompt config
    llm_provider: Literal["openai", "claude", "gemini"]

    def format_prompt(self, template: str) -> str:
        """
        Format a prompt template by replacing placeholders with dependency values.

        Supported placeholders:
        - {{MIGRATION_TARGET}}: Replaced with self.migration_target

        Args:
            template (str): The prompt template containing placeholders.

        Returns:
            str: The formatted prompt with placeholders replaced.
        """
        formatted = template.replace("{{MIGRATION_TARGET}}", self.migration_target)
        return formatted
