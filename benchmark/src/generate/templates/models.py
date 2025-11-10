"""Shared data models for template subsystem.

This module contains lightweight Pydantic models (DTOs, value objects) used
by the template subsystem for spec and dependency generation.
"""

from pydantic import BaseModel


class Prompt(BaseModel, frozen=True):
    """A simplified prompt containing the property-based test and its dependencies.

    Used by both dataset and template subsystems for generating initial prompts.

    Attributes:
        pbt: The property-based test code
        pbt_name: The name of the test function
        function_name: The name of the function under test (inferred from pbt_name)
        deps: List of dependency source code
    """

    pbt: str
    pbt_name: str
    function_name: str
    deps: list[str]
