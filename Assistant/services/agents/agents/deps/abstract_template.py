"""
Abstract template definition for agent template.

Defined here to avoid circular imports.
"""
from dataclasses import dataclass

@dataclass
class AbstractTemplate:
    name: str
    description: str
    template: str
