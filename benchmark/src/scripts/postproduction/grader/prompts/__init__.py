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


def load_system_prompt() -> str:
    """Load the shared system prompt.

    Returns:
        System prompt text
    """
    system_template = jinja_env.get_template("system.prompt")
    return system_template.render()


def render_difficulty_prompt(sample: dict[str, Any]) -> str:
    """Render the difficulty estimation prompt with sample data.

    Focuses only on the Lean formalization itself, not the Python provenance.

    Args:
        sample: Sample dictionary from merged JSONL

    Returns:
        Rendered difficulty prompt
    """
    template = jinja_env.get_template("difficulty.prompt.template")

    # Extract only Lean-related context
    spec_code = sample.get("spec")
    impl_code = sample.get("impl")

    context = {
        "spec_code": spec_code,
        "impl_code": impl_code,
        "num_theorems": sample.get("num_theorems", 0),
        "num_sorries": sample.get("num_sorries", 0),
        "success": sample.get("success", False),
        "lines_spec": spec_code.count("\n") if spec_code else 0,
        "lines_impl": impl_code.count("\n") if impl_code else 0,
    }

    return template.render(**context)


__all__ = ["load_system_prompt", "render_difficulty_prompt"]
