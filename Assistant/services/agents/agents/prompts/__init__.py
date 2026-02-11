"""
The prompts module for agents
"""
from .prompts import _Prompts
from .templates import Template, _Templates

Prompts = _Prompts()
Templates = _Templates()

__all__ = [
    "Prompts",
    "Template",
    "Templates",
]
