"""graphs — fvspec visualization CLI.

Usage:
    uv run graphs benchmark   # FVSpec benchmark dataset characterization
    uv run graphs baselines   # Baseline model evaluation charts
    uv run graphs all         # Run all subcommands
"""

import typer

app = typer.Typer(help="fvspec graphs CLI", add_completion=False)


@app.command()
def realpbt() -> None:
    """RealPBT corpus characterization plots."""
    from graphs.realpbt import main
    main()


@app.command()
def benchmark() -> None:
    """FVSpec benchmark dataset characterization plots (HuggingFace + RealPBT)."""
    from graphs.benchmark import main

    main()


@app.command()
def baselines() -> None:
    """Baseline model evaluation charts from .eval files in data/."""
    from graphs.baselines import main

    main()


@app.command()
def all() -> None:
    """Run all graph subcommands."""
    from graphs.realpbt import main as rpbt_main
    from graphs.benchmark import main as bm_main
    from graphs.baselines import main as bl_main

    rpbt_main()
    bm_main()
    bl_main()


def main() -> None:
    app()
