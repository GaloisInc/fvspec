"""Generate the benchmark"""

from inspect_ai import eval
from benchmark.config import load_config
from benchmark.scaffold.task import fvspec
from benchmark.templates.registry import VariantRegistry
from typer import Typer, Option

cfg = load_config()
# if cfg.meta.logging:
#     setup_logfire()

app = Typer()


@app.command()
def generate(
    datafile: str = "scrapedtests.json",
    no_mcp: bool = False,
    variant: str = Option(
        None,
        help="Prompt variant name from registry.toml (e.g., 'control-functional', 'terse-functional'). If not specified, uses default from registry or config.toml.",
    ),
    list_variants: bool = Option(
        False, "--list-variants", help="List all available prompt variants and exit"
    ),
) -> None:
    """Evaluate the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools (use simple generate instead)
        variant: Prompt variant name (overrides config.toml)
        list_variants: List available variants and exit
    """
    # Handle --list-variants flag
    if list_variants:
        registry = VariantRegistry()
        print("Available prompt variants:\n")
        for name in registry.list_variants():
            info = registry.get_variant_info(name)
            print(f"  {name}")
            print(f"    Style: {info['style']}")
            print(f"    Description: {info['description']}")
            print(f"    Tags: {', '.join(info.get('tags', []))}")
            print()
        return

    # Determine variant: CLI arg > config > registry default
    use_variant = variant or cfg.prompt.variant

    eval(
        fvspec(datafile, use_mcp=not no_mcp, variant=use_variant),
        model=cfg.agent.model,
    )


def main() -> None:
    app()
