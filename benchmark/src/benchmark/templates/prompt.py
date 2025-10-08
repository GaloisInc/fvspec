from jinja2 import Environment, PackageLoader

from benchmark.config import PromptStyle

env = Environment(loader=PackageLoader("benchmark"))

# Always available
initial = env.get_template("initial.prompt.template")


def get_system_prompt(style: PromptStyle = "functional"):
    """Load the appropriate system prompt based on the verification style.

    Args:
        style: Either "functional" (FVAPPS-style) or "mvcgen" (imperative with Hoare logic)

    Returns:
        The rendered system prompt template
    """
    return env.get_template(f"{style}.system.prompt")
