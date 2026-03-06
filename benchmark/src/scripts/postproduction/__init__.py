"""Unified CLI for post-production pipeline.

Usage (from benchmark/ directory):
    uv run postprod merge runs.txt
    uv run postprod grader fvspec.jsonl
    uv run postprod metrics fvspec.jsonl
    uv run postprod turncount artifacts/runs/
"""

import typer

from scripts.postproduction.grader import app as grader_app
from scripts.postproduction.merge import main as merge_main
from scripts.postproduction.metrics import main as metrics_main
from scripts.postproduction.turncount import main as turncount_main

app = typer.Typer(
    name="postprod",
    help="Post-production pipeline for benchmark data",
    no_args_is_help=True,
)

# Single-command tools registered directly as subcommands
app.command(name="merge")(merge_main)
app.command(name="metrics")(metrics_main)
app.command(name="turncount")(turncount_main)

# Multi-command tools registered as sub-typers
app.add_typer(grader_app, name="grader")
