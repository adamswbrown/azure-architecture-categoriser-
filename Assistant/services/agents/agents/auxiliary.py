"""
Auxiliary Agents for Request Processing

This module provides lightweight agents that support the main persona agents:

1. **Delegator Agent**: Routes user requests to the most appropriate persona.
   - Analyzes question content, intent, and persona specialties
   - Returns a Persona enum value for request routing

2. **Template Agent**: Selects response formatting templates based on user intent.
   - Returns a Templates enum value (or null if no template applies)
   - Selected template is injected into agent prompts via AgentDeps

3. **Suggestions Agent**: Generates contextual follow-up suggestions for the user.
   - Produces 3 SuggestionItems based on recent interactions
   - Leverages available data views and templates to guide users

The delegator and template agents run concurrently during request pre-processing
in DrMChatApp._pre_process_request() to minimize latency overhead.
"""

from pydantic_ai import Agent, RunContext
from . import config
from .deps import AgentDeps, SuggestionItem
from .personas import Persona
from .prompts import Templates


logger = config.get_logger("delegator")

delegator_agent = Agent(
    name="delegator",
    output_type=Persona,
    instructions=(
        "You are the **Delegation Agent**. "
        "Your task is to decide which of the available agents is best suited to respond to a user request."
        f"\n\n{Persona.brief()}"
    ),
)

template_agent = Agent(
    name="template",
    output_type=Templates.enum_type,
    instructions=(
        "You are the **Template Agent**. "
        "Your task is to decide whether there is an appropriate template to apply to the next response based "
        "upon the available templates. Return either the name of the template or `null` if no template is appropriate."
        f"\n\n{Templates.build_template_prompt()}"
    ),
)

suggestions_agent = Agent(
    name="suggestions", output_type=list[SuggestionItem], deps_type=AgentDeps
)


@suggestions_agent.instructions
async def build_suggestions_instructions(ctx: RunContext[AgentDeps]) -> str:
    """Build the instructions for the suggestions agent."""
    previous_suggestions = "\n  -".join(item.format_suggestion_line() for item in ctx.deps.state.suggestions)
    available_views = ctx.deps.database.list_database_views(short=True)
    available_templates = Templates.build_template_prompt()

    return f"""\
You are the **Suggestions Agent** inside a chat application for migration assistance.
Your task is to suggest **3** SuggestionItems based on the user's recent interactions.

## SuggestionItem Format
- `pill_text`: Will display in a pill above the chat input box
- `suggestion`: Will be submitted as the user's next request when selected if pill is clicked

**Important**: Write BOTH fields from the user's perspective (as if the user wrote them).
The `pill_text` should clearly indicate what action the suggestion will trigger.
The `suggestion` should read like a natural user query or command.

## Guidelines
- Use context to suggest helpful follow-up questions or actions
- Avoid repeating previous suggestions (formatted as **pill_text**: suggestion): 
  -{previous_suggestions}
- Leverage available data (applications, servers, costs)
- Steer users toward templates when relevant
  - Do not use the name of the template itself; instead, suggest actions that align with the template's purpose
  - Make sure the template has the required context (e.g. an application name mentioned) before suggesting it
- Other available chat features:
  - Agent is able to query data to construct custom tables or summaries as needed
  - Agent can create charts to visualise data

## Available Data Views
{available_views}

## Available Templates
{available_templates}
"""
