"""
Agent Prompts Module - Dynamic Prompt Loading System

This module provides a hierarchical, LLM-provider-aware system for loading agent prompt
instructions from markdown files. It allows you to customize prompts per agent persona
and per LLM provider (OpenAI, Claude, Gemini, etc.).

===============================================================================
HOW TO ADD NEW PROMPT FILES
===============================================================================

1. DIRECTORY STRUCTURE:

   agents/prompts/
   ├── core/                    # Default prompts (used as fallback)
   │   ├── ROLE.md
   │   ├── RESPONSIBILITIES.md
   │   ├── TOOLS.md
   │   ├── DATA.md
   │   ├── STYLE.md
   │   ├── openai/              # OpenAI-specific overrides
   │   │   └── ROLE.md
   │   ├── claude/              # Claude-specific overrides
   │   │   └── RESPONSIBILITIES.md
   │   └── gemini/              # Gemini-specific overrides
   │       └── STYLE.md
   ├── financial_planner/       # Custom persona prompts
   │   ├── ROLE.md
   │   ├── RESPONSIBILITIES.md
   │   └── openai/              # Persona + LLM provider overrides
   │       └── ROLE.md
   └── migration_engineer/      # Another custom persona
       └── openai/
           └── RESPONSIBILITIES.md

2. AVAILABLE SECTION NAMES (case-sensitive):
   - ROLE.md             : Defines the agent's role and identity
   - RESPONSIBILITIES.md : Lists what the agent is responsible for
   - TOOLS.md            : Documents available tools and how to use them
   - DATA.md             : Explains data access patterns and schemas
   - STYLE.md            : Defines communication style and formatting
   - FINAL_NOTE.md       : Final instructions or important reminders

Note that the sections will be concatenated in the above order to form the full
INSTRUCTIONS for the agent.

3. SUPPORTED LLM PROVIDERS (subdirectory names):
   - openai   : For OpenAI models
   - claude   : For Anthropic Claude models
   - gemini   : For Google Gemini models

===============================================================================
FILE LOOKUP PRIORITY ORDER
===============================================================================

When the system looks for a prompt section (e.g., "ROLE"), it searches in this
EXACT order and returns the FIRST file found:

Given:
  - persona = "financial_planner"
  - llm_provider = "openai"
  - section_name = "ROLE"

Priority order:
  1. agents/prompts/financial_planner/openai/ROLE.md
     ↑ Most specific: persona + LLM provider

  2. agents/prompts/financial_planner/ROLE.md
     ↑ Persona-specific, provider-agnostic

  3. agents/prompts/core/openai/ROLE.md
     ↑ Default persona, provider-specific

  4. agents/prompts/core/ROLE.md
     ↑ Most generic: default fallback

  If none exist: Returns None (section omitted from final instructions)

This priority system allows you to:
- Create provider-specific prompts (e.g., Claude needs different formatting)
- Override specific sections for certain personas
- Maintain a common baseline in "core/" that applies to all agents
- Have complete flexibility: override everything or just what you need

===============================================================================
TEMPLATE VARIABLES
===============================================================================

You can use these placeholders in your markdown files:

- {{MIGRATION_TARGET}}  : Replaced with ctx.deps.migration_target
- {{DATA_SCHEMA}}       : Replaced with database schema (DATA.md only)

Example in ROLE.md:
  "You are migrating systems to {{MIGRATION_TARGET}} cloud platform."

===============================================================================
USAGE EXAMPLES
===============================================================================

pydantic_ai Agents will inject the ctx vars at runtime, see /agent/deps/ for
how these dependencies are defined.

# Default core prompts:
Prompts.INSTRUCTIONS(ctx)

# Use a specific persona:
Prompts.persona("financial_planner").INSTRUCTIONS(ctx)

# Get a single section:
Prompts.ROLE(ctx)
Prompts.persona("migration_engineer").RESPONSIBILITIES(ctx)

===============================================================================
"""

from pathlib import Path
from typing import Optional

from pydantic_ai import RunContext

from ..deps import AgentDeps


class _Prompts:
    """
    The main interface for getting agent instructions.

    We will break down the instructions into the following chunks:
    1. Role
    2. Responsibilities
    3. Tools
    4. Data
    5. Style
    6. Final note
    and concatenate them together to form the INSTRUCTIONS property.
    """

    # Default folder for markdown files
    DEFAULT_FOLDER = "core"

    # Cache the instructions so that it only calculates them upon first request
    CACHED = True

    # Some consts
    ENCODING = "utf-8"

    def __init__(self, _persona: Optional[str] = None):
        self._persona: str = _persona if _persona else "core"
        self._instructions: str | None = None
        self._cached_database_schema: str | None = None

    def persona(self, persona: str):
        return _Prompts(_persona=persona)

    def _get_md(self, section_name: str, ctx: RunContext[AgentDeps]) -> str | None:
        """
        Get the markdown content for a given section name.

        The priority order of lookup is:
        1. persona/llm_provider/section_name.md
        2. persona/section_name.md
        3. core/llm_provider/section_name.md
        4. core/section_name.md

        Valid LLM providers are: `openai`, `claude`, `gemini`

        If no file is found, return None.
        """
        base_path = Path(__file__).parent
        md_paths = [
            # Check persona + llm provider
            base_path / self._persona / ctx.deps.llm_provider,
            # Check persona only
            base_path / self._persona,
            # Check default folder + llm provider
            base_path / self.DEFAULT_FOLDER / ctx.deps.llm_provider,
            # Check default folder only
            base_path / self.DEFAULT_FOLDER,
        ]

        for md_path in md_paths:
            if (file_path := md_path / f"{section_name}.md").exists():
                return file_path.read_text(encoding=self.ENCODING).strip()

        return None

    def ROLE(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("ROLE", ctx)

    def RESPONSIBILITIES(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("RESPONSIBILITIES", ctx)

    def TOOLS(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("TOOLS", ctx)

    def DATA(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("DATA", ctx)

    def STYLE(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("STYLE", ctx)

    def FINAL_NOTE(self, ctx: RunContext[AgentDeps]) -> str | None:
        return self._get_md("FINAL_NOTE", ctx)

    def INSTRUCTIONS(self, ctx: RunContext[AgentDeps]) -> str:
        """
        INSTRUCTIONS property that concatenates all sections together.

        The sections are calculated once and reused if CACHED is True.

        Replace all instances of:
        - {{MIGRATION_TARGET}} with the value in ctx.deps.migration_target.
        """
        # Build or retrieve cached instructions
        if self.CACHED and self._instructions:
            instructions = self._instructions
        else:
            instructions = ""

            # Concatenate sections in order: ROLE, RESPONSIBILITIES, TOOLS, DATA, STYLE, FINAL_NOTE
            sections = []
            for section in [
                self.ROLE(ctx),
                self.RESPONSIBILITIES(ctx),
                self.TOOLS(ctx),
                self.DATA(ctx),
                self.STYLE(ctx),
                self.FINAL_NOTE(ctx),
            ]:
                if section:
                    sections.append(section)
            instructions = "\n\n".join(sections)

            # Final output
            self._instructions = instructions.strip()
            # Replace placeholders
            self._instructions = self._format_prompt(self._instructions, ctx)
            instructions = self._instructions

        return instructions

    def _format_prompt(self, prompt: str, ctx: RunContext[AgentDeps]) -> str:
        """
        Format the prompt by replacing placeholders with context values.
        """
        # Replace {{MIGRATION_TARGET}}
        prompt = prompt.replace(r"{{MIGRATION_TARGET}}", ctx.deps.migration_target)
        # Replace {{DATA_SCHEMA}}
        DATA_SCHEMA = self._database_schema(ctx)
        prompt = prompt.replace(r"{{DATA_SCHEMA}}", DATA_SCHEMA)
        # Return formatted prompt
        return prompt

    def _database_schema(self, ctx: RunContext[AgentDeps]) -> str:
        if self._cached_database_schema is None:
            self._cached_database_schema = ctx.deps.database.list_database_views()
        return self._cached_database_schema


Prompts = _Prompts()
