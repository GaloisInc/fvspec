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
        state = await generate(state, tool_calls="loop")
        return state

    return solve


@scorer(metrics=[])
def lake_build_scorer():
    """Score by counting remaining sorry and running lake build."""

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
        build_error = None
        try:
            result = subprocess.run(
                ["lake", "build"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            compiles = result.returncode == 0
            if not compiles:
                build_error = result.stderr[:500]
        except subprocess.TimeoutExpired:
            build_error = "lake build timed out (120s)"
        except Exception as e:
            build_error = str(e)

        proved = sorries == 0 and compiles
        value = 1.0 if proved else 0.0

        metadata = {
            "sorries_remaining": sorries,
            "sorries_original": sorries_original,
            "sorries_removed": sorries_original - sorries,
            "compiles": compiles,
            "proved": proved,
            "difficulty_bucket": state.metadata.get("difficulty_bucket", "unknown"),
        }
        if build_error:
            metadata["build_error"] = build_error

        explanation = (
            f"sorry: {sorries}/{sorries_original}, "
            f"compiles: {compiles}, proved: {proved}"
        )

        return Score(value=value, explanation=explanation, metadata=metadata)

    return score


async def cleanup_fn(state: TaskState) -> None:
    """Clean up workspace after sample completes."""
    workspace_path = state.metadata.get("workspace")
    if workspace_path:
        cleanup_workspace(Path(workspace_path))


@task
def fvspec_baselines(ranseed: int = 42, num_samples: int = 1000) -> Task:
    """Create the fvspec baselines evaluation task.

    Args:
        ranseed: Random seed for stratified sampling
        num_samples: Total number of samples (split across buckets by ratio)

    Returns:
        Task configured with proof-writing agent and lake build scorer
    """
    samples = load_and_sample(ranseed=ranseed, num_samples=num_samples)
    dataset = to_inspect_dataset(samples)

    return Task(
        dataset=dataset,
        setup=[workspace_setup()],
        solver=[proof_solver()],
        scorer=lake_build_scorer(),
        tools=baselines_tools(),
        cleanup=cleanup_fn,
    )
