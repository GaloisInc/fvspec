"""inspect_ai Task, solvers, and scorer for fvspec baselines."""

import logging
import re
import subprocess
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import ChatMessageSystem
from inspect_ai.scorer import Score, Target, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver

from baselines.dataset import load_and_sample, to_inspect_dataset
from baselines.prompts import load_system_prompt
from baselines.tools import baselines_tools
from baselines.workspace import cleanup_workspace, create_workspace, populate_workspace

logger = logging.getLogger(__name__)


@solver
def workspace_setup() -> Solver:
    """Create a per-sample workspace from HF dataset metadata."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        workspace = create_workspace(str(state.sample_id))

        impl = state.metadata.get("impl", "")
        spec = state.metadata.get("spec", "")
        populate_workspace(workspace, impl, spec)

        state.metadata["workspace"] = str(workspace)
        return state

    return solve


@solver
def proof_solver() -> Solver:
    """Main proof-writing solver: sets system prompt and generates with tool loop."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        system_prompt = load_system_prompt()
        state.messages.insert(0, ChatMessageSystem(content=system_prompt))
        state.tools = baselines_tools()
        state = await generate(state, tool_calls="loop")
        return state

    return solve


@scorer(metrics=[])
def lake_build_scorer():
    """Score by counting remaining sorry and running lake build.

    Returns both a binary proved score and partial credit based on sorry removal.
    Note: sorry count can increase when a proof is closer to solved (each sorry
    becomes less load-bearing), so partial credit clamps at 0.
    """

    async def score(state: TaskState, target: Target) -> Score:
        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            return Score(
                value=0.0,
                explanation="No workspace found",
                metadata={"error": "missing_workspace"},
            )

        workspace = Path(workspace_path)
        spec_file = workspace / "Fvspec" / "Spec.lean"

        if not spec_file.exists():
            return Score(
                value=0.0,
                explanation="Spec.lean not found",
                metadata={"error": "missing_spec"},
            )

        spec_content = spec_file.read_text()

        # Count remaining sorry placeholders
        sorries = len(re.findall(r"\bsorry\b", spec_content))
        original_spec = state.metadata.get("spec", "")
        sorries_original = len(re.findall(r"\bsorry\b", original_spec))

        # Run lake build
        compiles = False
        has_sorry_warnings = False
        build_error = None
        build_stdout = ""
        build_stderr = ""
        try:
            result = subprocess.run(
                ["lake", "build"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            compiles = result.returncode == 0
            build_stdout = result.stdout
            build_stderr = result.stderr
            # Check for sorry warnings in output (lake may compile but warn)
            combined_output = build_stdout + build_stderr
            has_sorry_warnings = "declaration uses 'sorry'" in combined_output
            if not compiles:
                build_error = build_stderr[:500]
        except subprocess.TimeoutExpired:
            build_error = "lake build timed out (120s)"
        except Exception as e:
            build_error = str(e)

        # Binary: proved iff zero sorry in source AND compiles AND no sorry warnings
        proved = sorries == 0 and compiles and not has_sorry_warnings

        # Partial credit: fraction of sorries removed (clamped to [0, 1])
        sorries_removed = sorries_original - sorries
        if sorries_original > 0:
            partial_credit = max(0.0, sorries_removed / sorries_original)
        else:
            # No sorries to begin with — full credit if it compiles
            partial_credit = 1.0 if compiles else 0.0

        # Binary score as the primary value
        value = 1.0 if proved else 0.0

        metadata = {
            "sorries_remaining": sorries,
            "sorries_original": sorries_original,
            "sorries_removed": sorries_removed,
            "sorries_increased": sorries > sorries_original,
            "partial_credit": round(partial_credit, 4),
            "compiles": compiles,
            "has_sorry_warnings": has_sorry_warnings,
            "proved": proved,
            "difficulty_bucket": state.metadata.get("difficulty_bucket", "unknown"),
        }
        if build_error:
            metadata["build_error"] = build_error

        explanation = (
            f"sorry: {sorries}/{sorries_original}, "
            f"compiles: {compiles}, sorry_warnings: {has_sorry_warnings}, "
            f"proved: {proved}, partial_credit: {partial_credit:.2f}"
        )

        return Score(value=value, explanation=explanation, metadata=metadata)

    return score


async def cleanup_fn(state: TaskState) -> None:
    """Clean up workspace after sample completes."""
    workspace_path = state.metadata.get("workspace")
    if workspace_path:
        cleanup_workspace(Path(workspace_path))


@task
def fvspec_baselines(
    ranseed: int = 42,
    num_samples: int = 75,
    data_source: str = "data/fvspec-mar27.jsonl",
    name: str | None = None,
) -> Task:
    """Create the fvspec baselines evaluation task.

    Args:
        ranseed: Random seed for stratified sampling
        num_samples: Total number of samples (split equally across buckets)
        data_source: Path to JSONL file or "huggingface"
        name: Optional task name override (used to include model in .eval filename)

    Returns:
        Task configured with proof-writing agent and lake build scorer
    """
    samples = load_and_sample(
        ranseed=ranseed, num_samples=num_samples, data_source=data_source
    )
    dataset = to_inspect_dataset(samples)

    return Task(
        name=name,
        dataset=dataset,
        setup=[workspace_setup()],
        solver=[proof_solver()],
        scorer=lake_build_scorer(),
        cleanup=cleanup_fn,
        message_limit=50,
    )
