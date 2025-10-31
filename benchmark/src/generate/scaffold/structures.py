"""Shared simple data structures used across multiple subsystems.

This module contains lightweight Pydantic models (DTOs, value objects) that
are used by 2+ subsystems. Domain-specific models should live in their
respective subsystem modules.

Rule: Only add models here if they're genuinely shared AND simple (<50 lines total).
"""

from pydantic import BaseModel


class Prompt(BaseModel, frozen=True):
    """A simplified prompt containing the property-based test and its dependencies.

    Used by both dataset and template subsystems for generating initial prompts.
    """

    pbt: str
    deps: list[str]
