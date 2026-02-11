"""
Read templates and provide an interface to access them.

Each template md file 
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ag_ui.core import SystemMessage

from .. import config
from ..deps import AgentDeps

__all__ = ["_Templates", "Template"]

logger = config.get_logger('prompts.templates')

"""
Abstract template definition for agent template.

Defined here to avoid circular imports.
"""

@dataclass
class Template:
    name: str
    description: str
    prompt: str

    def to_system_message(self, deps: AgentDeps) -> SystemMessage:
        """Convert to SystemMessage."""
        return SystemMessage(
            id="template_system_message",
            content=deps.format_prompt(self.prompt),
        )


class _Templates:
    """
    Read templates and provide an interface to access them.

    Template files are stored in the `templates` folder as markdown files.
    Each template file should have a
    * Description section
    * Template section

    The name will be inferred from the filename.
    """

    TEMPLATE_DIR = Path(__file__).parent / "templates"
    ENCODING = "utf-8"

    def _get_md(self, path: Path) -> Template:
        name = path.stem
        text = path.read_text(encoding=self.ENCODING).strip()
        description, template = text.split("# RESPONSE TEMPLATE", 1)
        description = description.replace("# DESCRIPTION", "").strip()
        # Include the "# RESPONSE TEMPLATE" header in the template content
        template = "# RESPONSE TEMPLATE\n" + template.strip()

        return Template(
            name=name,
            description=description,
            prompt=template,
        )
    
    def __init__(self):
        self.templates: dict[str, Template] = {}
        for file_path in self.TEMPLATE_DIR.glob("*.md"):
            template = self._get_md(file_path)
            self.templates[template.name] = template
        self.enum_type = Enum("Templates", {name: name for name in self.templates.keys()} | {"null": "null"})
        # Display registered templates
        logger.info(f"Loaded templates: {list(self.templates.keys())}")
        logger.debug(f"enum_type: {[(item.name, item.value) for item in self.enum_type]}")
    
    def build_template_prompt(self) -> str:
        """
        Build a prompt listing all available templates with their descriptions.
        """
        prompt_lines = ["Available Templates:\n"]
        for template in self.templates.values():
            prompt_lines.append(f"### {template.name}\n{template.description}\n")
        return "\n".join(prompt_lines)

    def get_template(self, name: Optional[str]) -> Template | None:
        """
        Get a template by name.

        Returns None if the name is None or not found.
        """
        if name is None:
            return None
        return self.templates.get(name)
