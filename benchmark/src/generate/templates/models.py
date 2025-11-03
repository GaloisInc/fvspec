"""Shared data models for template subsystem.

This module contains lightweight Pydantic models (DTOs, value objects) used
by the template subsystem for spec and dependency generation.
"""

from pydantic import BaseModel


class Prompt(BaseModel, frozen=True):
    """A simplified prompt containing the property-based test and its dependencies.

    Used by both dataset and template subsystems for generating initial prompts.
    """

    pbt: str
    deps: list[str]
