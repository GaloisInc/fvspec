"""Execution harness for the dependency autoformalization agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.log import EvalLog, EvalSample
from inspect_ai.model import ChatMessageAssistant
from inspect_ai.solver import basic_agent, system_message, use_tools

from generate.scaffold.depmock.agent import autoformalize_dependency_tool
from generate.scaffold.depmock.autoformalizer import (
    DependencyExecutionRequest,
    DependencyFatalError,
    DependencyRecoverableError,
)
from generate.scaffold.depmock.models import DependencyResult
from generate.scaffold.tools.declaration import lean_compile


_SUPERVISOR_PROMPT = (
    "You coordinate dependency autoformalization. Use the "
    "`autoformalize_dependency_tool` to translate the provided Python helper "
    "into Lean code. When you obtain Lean code, immediately wrap it in "
    "<code>...</code> tags and verify it with the `lean_compile` tool. If "
    "`lean_compile` reports diagnostics, revise the Lean module by invoking the "
    "autoformalizer again. Only call `submit()` after the Lean module compiles, "
    "and submit the final Lean code (still wrapped in <code> tags) with no "
    "additional commentary."
)

_CODE_BLOCK_PATTERN = re.compile(r"(?s)<code>(.*?)</code>")


@dataclass(frozen=True)
class DependencyAgentRun:
    """Container for agent execution artifacts."""

    log: EvalLog
    completion: str
    code: str
    attempts: int


def _extract_completion(sample: EvalSample) -> str:
    """Extract the assistant completion from a completed sample."""
    completion = (sample.output.completion or "").strip()
    if completion:
        return completion

    for message in reversed(sample.messages):
        if isinstance(message, ChatMessageAssistant):
            text = message.text.strip()
            if text:
                return text
    return ""


def _extract_code_block(text: str) -> str | None:
    """Extract the Lean code block from the model completion."""
    match = _CODE_BLOCK_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).strip()


def _run_agent_once(
    request: DependencyExecutionRequest,
    *,
    variant: str | None,
    model: str,
    max_attempts: int,
    display: str | None,
    message_limit: int | None,
) -> DependencyAgentRun:
    """Execute the dependency autoformalizer task once via inspect_ai."""
    payload = request.spec.payload

    sample_metadata: dict[str, Any] = {
        "dep_name": payload.dep_name,
        "cache_key": request.spec.cache_key,
        "dependency_index": request.spec.dependency_index,
        "datapoint_id": request.spec.datapoint_id,
        "sample_id": request.spec.sample_id,
        "attempt": request.attempt,
        "diagnostics": request.diagnostics,
        "variant": variant,
    }

    dataset = MemoryDataset(
        [
            Sample(
                id=f"{request.spec.cache_key}:{request.attempt}",
                input="Autoformalize dependency.",
                metadata=sample_metadata,
            )
        ]
    )

    tool_stack = [
        autoformalize_dependency_tool(
            payload=payload,
            diagnostics=request.diagnostics,
            variant=variant,
        ),
        lean_compile(),
    ]

    solver_plan = [
        system_message(_SUPERVISOR_PROMPT),
        use_tools(tool_stack),
        basic_agent(max_attempts=max_attempts, message_limit=message_limit),
    ]

    task = Task(dataset=dataset, solver=solver_plan)

    try:
        logs = inspect_eval(
            task,
            model=model,
            display=display or "none",
            trace=False,
            log_samples=False,
            fail_on_error=True,
            continue_on_fail=False,
        )
    except Exception as exc:  # pragma: no cover - safety net for inspect_ai errors
        raise DependencyFatalError(f"inspect.ai evaluation failed: {exc}") from exc

    if not logs or logs[0].samples is None or not logs[0].samples:
        raise DependencyFatalError("autoformalizer produced no samples.")

    log = logs[0]
    samples = cast(list[EvalSample], log.samples)
    sample = samples[0]
    completion = _extract_completion(sample)
    code = _extract_code_block(completion)
    if code is None:
        raise DependencyRecoverableError(
            "autoformalizer response did not include Lean code",
            diagnostics=completion or "missing <code> block",
        )

    attempts = sample.metadata.get("AgentAttempts:attempts")
    if isinstance(attempts, int):
        attempt_count = attempts
    else:
        attempt_count = request.attempt

    return DependencyAgentRun(
        log=log,
        completion=completion,
        code=code,
        attempts=attempt_count,
    )


def run_dependency_agent(
    request: DependencyExecutionRequest,
    *,
    variant: str | None,
    model: str,
    max_attempts: int,
    display: str | None = "none",
    message_limit: int | None = 20,
) -> DependencyResult:
    """Run the dependency autoformalizer agent and return Lean output.

    Args:
        request: Execution request containing dependency metadata.
        variant: Optional prompt variant for the dependency translator.
        model: Model identifier used for inspect_ai evaluation.
        max_attempts: Maximum submissions allowed within the agent loop.
        display: Inspect display mode (defaults to ``"none"``).
        message_limit: Optional cap on messages exchanged within the agent.

    Returns:
        DependencyResult containing the generated Lean code.

    Raises:
        DependencyRecoverableError: When the agent returns malformed output suitable for retry.
        DependencyFatalError: When the agent run fails irrecoverably.
    """
    run = _run_agent_once(
        request,
        variant=variant,
        model=model,
        max_attempts=max_attempts,
        display=display,
        message_limit=message_limit,
    )

    return DependencyResult(
        lean_module=request.spec.payload.lean_module_name,
        lean_code=run.code,
        variant=variant,
        status="ok",
        diagnostics=None,
    )
