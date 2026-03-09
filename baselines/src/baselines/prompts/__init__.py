"""Prompt loading for fvspec baselines."""

from pathlib import Path

from jinja2 import Template

from baselines.models import FvspecSample

PROMPT_DIR = Path(__file__).parent


def load_system_prompt() -> str:
    """Load the proof agent system prompt."""
    return (PROMPT_DIR / "system.prompt").read_text()


def render_user_prompt(sample: FvspecSample) -> str:
    """Render the per-sample user prompt from the Jinja2 template."""
    template = Template((PROMPT_DIR / "user.prompt.template").read_text())
    return template.render(
        impl=sample.impl,
        spec=sample.spec,
        realpbt_code=sample.realpbt_code,
        realpbt_summary=sample.realpbt_summary,
        num_theorems=sample.num_theorems,
    )
