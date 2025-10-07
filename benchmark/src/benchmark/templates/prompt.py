from jinja2 import Environment, PackageLoader
from typing import Literal

env = Environment(loader=PackageLoader("benchmark"))

# Style types for type safety
PromptStyle = Literal["functional", "mvcgen"]

# Always available
initial = env.get_template("initial.prompt.template")


def get_system_prompt(style: PromptStyle = "functional"):
    """Load the appropriate system prompt based on the verification style.

    Args:
        style: Either "functional" (FVAPPS-style) or "mvcgen" (imperative with Hoare logic)

    Returns:
        The rendered system prompt template
    """
    if style == "mvcgen":
        return env.get_template("mvcgen.system.prompt")
    elif style == "functional":
        return env.get_template("functional.system.prompt")
    else:
        raise ValueError(
            f"Unknown prompt style: {style}. Use 'functional' or 'mvcgen'."
        )


# Backwards compatibility: default to functional style
system = get_system_prompt("functional")
