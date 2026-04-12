"""Prompt loading and rendering for grader.

This module manages Jinja2 template loading and rendering for system prompts
and difficulty assessment prompts.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

# Template loading
TEMPLATES_DIR = Path(__file__).parent
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _spec_impl_context(sample: dict[str, Any]) -> dict[str, Any]:
    """Extract Lean-related context from a sample."""
    spec_code = sample.get("spec")
    impl_code = sample.get("impl")
    return {
        "spec_code": spec_code,
        "impl_code": impl_code,
        "num_theorems": sample.get("num_theorems", 0),
        "num_sorries": spec_code.count("sorry") if spec_code else 0,
        "lines_spec": spec_code.count("\n") + 1 if spec_code else 0,
        "lines_impl": impl_code.count("\n") + 1 if impl_code else 0,
    }


def load_system_prompt() -> str:
    """Load the v1 system prompt.

    Returns:
        System prompt text
    """
    system_template = jinja_env.get_template("system.prompt")
    return system_template.render()


def load_system_prompt_v2() -> str:
    """Load the v2 system prompt (binary classification).

    Returns:
        System prompt text
    """
    system_template = jinja_env.get_template("system_v2.prompt")
    return system_template.render()


def render_difficulty_prompt(sample: dict[str, Any]) -> str:
    """Render the v1 difficulty estimation prompt with sample data.

    Args:
        sample: Sample dictionary from merged JSONL

    Returns:
        Rendered difficulty prompt
    """
    template = jinja_env.get_template("difficulty.prompt.template")
    context = _spec_impl_context(sample)
    context["success"] = sample.get("success", False)
    return template.render(**context)


def render_difficulty_prompt_v2(sample: dict[str, Any]) -> str:
    """Render the v2 binary difficulty prompt with calibration examples.

    Args:
        sample: Sample dictionary from merged JSONL

    Returns:
        Rendered difficulty prompt
    """
    template = jinja_env.get_template("difficulty_v2.prompt.template")
    context = _spec_impl_context(sample)
    return template.render(**context)


__all__ = [
    "load_system_prompt",
    "load_system_prompt_v2",
    "render_difficulty_prompt",
    "render_difficulty_prompt_v2",
]
