"""Unified formalization orchestration for fvspec benchmark.

Architecture:
1. Function Discovery: Discover FUT source code from database
2. Dependency Formalization: Generate Lean implementations for dependencies
3. Unified Formalization: Single agent produces both Impl.lean and Spec.lean
4. Plausible Testing: Property testing of generated specifications
"""

import logging
import time
import tomllib
from datetime import datetime
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.model import ChatCompletionChoice, ChatMessageAssistant, ModelOutput
from inspect_ai.solver import Generate, Solver, TaskState, fork, solver
from pydantic import ValidationError

from generate.config import DATA_DIR, load_config
from generate.scaffold.dataset import Datapoint, mk_dataset
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.function_discovery import discover_function_code
from generate.scaffold.formalize.agent import (
    FormalizationPayload,
    FormalizationResult,
    formalization_agent,
)
from generate.scaffold.formalize.impl import (
    FunctionImplPayload,
    FunctionImplResult,
    function_impl_agent,
    payloads_from_datapoint,
)
from generate.scaffold.formalize.impl.lean_merger import append_to_lean_file
from generate.scaffold.formalize.plausible_runner import Plausibility, run_plausible
from generate.scaffold.quality_assessment import count_lean_theorems
from generate.scaffold.tools import utilio
from generate.scaffold.tools.declaration import write_to_disk
from generate.templates.formalize import FormalizationVariantRegistry

logger = logging.getLogger(__name__)


@solver
def impl_agent_solver(payload: FunctionImplPayload, workspace: Path) -> Solver:
    """Wrapper solver for implementation agent to use with fork().

    Enables conversation isolation via fork(). Used for dependency formalization.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        impl_solver = function_impl_agent(payload, workspace)
        state = await impl_solver(state, generate)

        # Migrate result from metadata to store
        impl_result = state.metadata.pop("impl_result", {})
        state.store.set("impl_result", impl_result)

        return state

    return solve


@solver
def formalization_agent_solver(
    payload: FormalizationPayload, workspace: Path
) -> Solver:
    """Wrapper solver for unified formalization agent to use with fork().

    Enables conversation isolation via fork().
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        agent = formalization_agent(payload, workspace)
        state = await agent(state, generate)
        return state

    return solve


@solver
def workspace_setup() -> Solver:
    """Create a per-sample workspace tmpdir for Lean files and LSP integration."""

    async def run(state: TaskState, generate: Generate) -> TaskState:
        workspace = utilio.create_sample_workspace(str(state.sample_id))
        state.metadata["workspace"] = str(workspace)
        return state

    return run


@solver
def pass_session_to_state(db_path: Path) -> Solver:
    """Inject database session into task state for function discovery."""

    async def run(state: TaskState, generate: Generate) -> TaskState:
        session = get_session(db_path)
        state.metadata["db_session"] = session
        return state

    return run


@solver
def orchestrate_subagents(variant: str | None = None) -> Solver:
    """Orchestrate unified formalization: discovery → deps → unified agent → plausible.

    Flow:
    1. Discover function code from database (if available)
    2. Generate dependency implementations → merged into Impl.lean
    3. Unified formalization agent → both Impl.lean and Spec.lean
    4. Plausible property testing (if enabled and spec compiled)

    Args:
        variant: Prompt variant name for formalization agent
    """

    async def run(state: TaskState, generate_fn: Generate) -> TaskState:
        start_time = time.time()

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            return state

        workspace = Path(workspace_path)
        datapoint = state.metadata.get("datapoint")
        if not isinstance(datapoint, Datapoint):
            return state

        # Determine function name from PBT name
        function_name = datapoint.name
        if function_name.startswith("test_"):
            function_name = function_name[5:]

        # Phase 0: Database work before fork() calls (deepcopy can't pickle sessions)
        db_session = state.metadata.get("db_session")

        # Discover function code
        function_code = None
        function_info = None
        if db_session:
            function_info = discover_function_code(datapoint, db_session)
            if function_info and function_info.confidence >= 0.5:
                function_name = function_info.name
                function_code = function_info.code
                state.store.set(
                    "function_discovery",
                    {
                        "discovered": True,
                        "method": function_info.discovery_method.value,
                        "confidence": function_info.confidence,
                        "original_name": datapoint.name,
                        "resolved_name": function_info.name,
                    },
                )
            else:
                state.store.set(
                    "function_discovery",
                    {
                        "discovered": False,
                        "method": function_info.discovery_method.value
                        if function_info
                        else "failed",
                        "confidence": function_info.confidence
                        if function_info
                        else 0.0,
                        "original_name": datapoint.name,
                        "resolved_name": function_name,
                    },
                )

        # Get dependency payloads — pass pre-discovered function_info to avoid redundant call
        all_payloads = payloads_from_datapoint(datapoint, function_info=function_info)

        # Close database session before fork() calls
        if db_session:
            db_session.close()
            state.metadata.pop("db_session", None)

        # Map variant to impl style for dep formalization
        formalize_variant_name = variant or "control-functional"
        formalize_registry = FormalizationVariantRegistry()
        formalize_variant = formalize_registry.get_variant(formalize_variant_name)
        impl_variant = formalize_variant.style  # functional or mvcgen

        impl_file = workspace / "Fvspec" / "Impl.lean"
        impl_file.parent.mkdir(parents=True, exist_ok=True)

        # Phase 1: Generate dependency implementations
        dependency_implementations: dict[str, str] = {}
        dep_processing_details = []
        phase1_start = time.time()

        for payload in all_payloads:
            # Skip FUT — handled by unified agent
            if payload.is_function_under_test:
                continue

            dep_impl_payload = FunctionImplPayload(
                function_name=payload.dep_name,
                function_code=payload.python_source,
                dependencies={},
                variant=impl_variant,
            )

            tokens_before_dep = state.token_usage
            dep_impl_solver = impl_agent_solver(dep_impl_payload, workspace)
            dep_impl_state = await fork(state, dep_impl_solver)

            dep_tokens = state.token_usage - tokens_before_dep
            dep_toolcalls = sum(
                1
                for msg in dep_impl_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )

            dep_token_usages = state.store.get("dep_token_usages", [])
            dep_token_usages.append(
                {
                    "subagent": "impl_dep",
                    "function_name": payload.dep_name,
                    "tokens_spent": dep_tokens,
                    "num_toolcalls": dep_toolcalls,
                }
            )
            state.store.set("dep_token_usages", dep_token_usages)

            dep_impl_result_data = dep_impl_state.store.get("impl_result", {})
            if isinstance(dep_impl_result_data, dict):
                dep_impl_result = FunctionImplResult(**dep_impl_result_data)
            else:
                dep_impl_result = dep_impl_result_data

            dep_processing_details.append(
                {
                    "function_name": payload.dep_name,
                    "order": len(dep_processing_details) + 1,
                    "success": dep_impl_result.success if dep_impl_result else False,
                    "compiles": dep_impl_result.compiles if dep_impl_result else False,
                    "tokens_spent": dep_tokens,
                    "toolcalls": dep_toolcalls,
                }
            )

            dep_conversations = state.store.get("dep_conversations", [])
            dep_conversations.append(
                {
                    "dep_name": payload.dep_name,
                    "messages": [msg.model_dump() for msg in dep_impl_state.messages],
                }
            )
            state.store.set("dep_conversations", dep_conversations)

            if dep_impl_result.success and dep_impl_result.lean_code:
                dependency_implementations[payload.dep_name] = dep_impl_result.lean_code
                if impl_file.exists():
                    current_content = impl_file.read_text()
                    merged_content = append_to_lean_file(
                        current_content, dep_impl_result.lean_code
                    )
                    impl_file.write_text(merged_content)
                else:
                    impl_file.write_text(dep_impl_result.lean_code)

        state.store.set("num_fns_impl", len(all_payloads))
        state.store.set("phase1_deps_duration", time.time() - phase1_start)
        state.store.set("phase1_num_deps", len(dep_processing_details))
        state.store.set("dependency_processing", dep_processing_details)

        # Skip samples with excessive function counts
        MAX_FUNCTIONS_IMPL = 50
        if len(all_payloads) > MAX_FUNCTIONS_IMPL:
            state.store.set("skipped", True)
            state.store.set(
                "skip_reason",
                {
                    "cause": "excessive_functions",
                    "num_functions": len(all_payloads),
                    "limit": MAX_FUNCTIONS_IMPL,
                    "message": f"Too many functions ({len(all_payloads)} > {MAX_FUNCTIONS_IMPL})",
                },
            )
            model_name = state.output.model if state.output else "unknown"
            state.output = ModelOutput(
                model=model_name,
                choices=[
                    ChatCompletionChoice(
                        message=ChatMessageAssistant(
                            content=f"Sample skipped: {len(all_payloads)} functions exceeds limit of {MAX_FUNCTIONS_IMPL}",
                            source="generate",
                        ),
                        stop_reason="stop",
                    )
                ],
                time=time.time() - start_time,
            )
            return state

        # Phase 2: Unified formalization agent
        phase2_start = time.time()
        formalization_payload = FormalizationPayload(
            function_name=function_name,
            function_code=function_code,  # None if discovery failed — that's fine
            pbt_code=datapoint.code,
            pbt_summary=datapoint.summary,
            dependencies=dependency_implementations,
            variant=formalize_variant_name,
        )

        tokens_before_formalize = state.token_usage
        formalize_solver = formalization_agent_solver(formalization_payload, workspace)
        formalize_state = await fork(state, formalize_solver)

        formalize_tokens = state.token_usage - tokens_before_formalize
        formalize_toolcalls = sum(
            1
            for msg in formalize_state.messages
            if msg.role == "assistant" and hasattr(msg, "tool_calls") and msg.tool_calls
        )

        state.store.set(
            "formalize_token_usage",
            {
                "subagent": "formalize",
                "tokens_spent": formalize_tokens,
                "num_toolcalls": formalize_toolcalls,
            },
        )
        state.store.set("phase2_formalize_duration", time.time() - phase2_start)

        # Extract result from isolated state
        formalize_result_data = formalize_state.store.get("formalization_result", {})
        if isinstance(formalize_result_data, dict):
            formalize_result = FormalizationResult(**formalize_result_data)
        else:
            formalize_result = formalize_result_data

        state.store.set(
            "formalize_conversation",
            [msg.model_dump() for msg in formalize_state.messages],
        )
        state.store.set("formalization_result", formalize_result_data)

        # Copy validation results from child state
        validation = formalize_state.store.get("validation", {})
        state.store.set("validation", validation)

        # Preserve model output
        state.output = formalize_state.output

        # Write files from result (agent already wrote via tools, but ensure final state)
        impl_file.parent.mkdir(parents=True, exist_ok=True)
        if formalize_result.impl_code:
            impl_file.write_text(formalize_result.impl_code)

        spec_file = workspace / "Fvspec" / "Spec.lean"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        if formalize_result.spec_code:
            spec_file.write_text(formalize_result.spec_code)
        else:
            spec_file.write_text(
                "import Fvspec.Impl\n\nnamespace Fvspec.Spec\n\nend Fvspec.Spec\n"
            )

        # Determine success from validation
        impl_compiles = validation.get("impl_compiles", False)
        impl_has_sorry = validation.get("impl_has_sorry", False)
        spec_compiles = validation.get("spec_compiles", False)
        spec_has_statements = validation.get("spec_has_statements", False)

        impl_autoform_success = impl_compiles and not impl_has_sorry
        spec_sig_success = spec_compiles and spec_has_statements

        # Track implementation level
        if function_code is not None:
            state.store.set("implementation_level", "provided")
        else:
            state.store.set("implementation_level", "signature")

        # Store results compatible with QA extraction
        state.store.set(
            "impl_result",
            {
                "success": impl_autoform_success,
                "lean_code": formalize_result.impl_code,
                "compiles": impl_compiles,
                "has_sorry": impl_has_sorry,
                "has_eval_stripped": False,
            },
        )
        state.store.set("impl_code", formalize_result.impl_code or "")
        state.store.set(
            "spec_result",
            {
                "success": spec_sig_success,
                "lean_code": formalize_result.spec_code,
                "compiles": spec_compiles,
                "has_statements": spec_has_statements,
            },
        )

        # Store token usage for spec subagent (QA expects this key)
        state.store.set(
            "spec_token_usage",
            {
                "subagent": "spec",
                "tokens_spent": formalize_tokens,
                "num_toolcalls": formalize_toolcalls,
            },
        )

        # Phase 3: Plausible property testing
        plausibility = Plausibility()
        if spec_sig_success and formalize_result.spec_code and spec_file.exists():
            try:
                config = load_config()
                if config.plausible.enabled:
                    theorem_count = count_lean_theorems(formalize_result.spec_code)
                    phase3_start = time.time()

                    plausibility = run_plausible(
                        spec_path=spec_file,
                        workspace_path=workspace,
                        timeout=config.plausible.timeout,
                        num_theorems=theorem_count,
                    )

                    state.store.set(
                        "phase3_plausibility_duration", time.time() - phase3_start
                    )
                    num_plausible = (
                        plausibility.num_theorems - plausibility.counterexamples
                    )
                    state.store.set(
                        "plausibility_summary",
                        {
                            "total_theorems": theorem_count,
                            "num_plausible": num_plausible,
                            "plausibility_rate": plausibility.success,
                            "counterexamples": plausibility.counterexamples,
                            "errors": len(plausibility.errors),
                            "time": plausibility.time,
                        },
                    )
            except (
                FileNotFoundError,
                OSError,
                tomllib.TOMLDecodeError,
                ValidationError,
            ) as e:
                plausibility = Plausibility(
                    ran=True,
                    success=0.0,
                    errors=[f"Error running plausible: {e}"],
                )

        state.store.set("plausibility", plausibility)

        # Set final output
        if plausibility.ran and spec_file.exists():
            output_text = spec_file.read_text()
        else:
            output_text = formalize_result.spec_code or ""

        if output_text:
            output_text = f"<code>\n{output_text}\n</code>"

        total_time = time.time() - start_time
        model_name = state.output.model if state.output else "unknown"

        state.output = ModelOutput(
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    message=ChatMessageAssistant(
                        content=output_text,
                        source="generate",
                    ),
                    stop_reason="stop",
                )
            ],
            time=total_time,
        )

        # Token accounting
        dep_token_usages_list = state.store.get("dep_token_usages", [])
        total_tokens = sum(d["tokens_spent"] for d in dep_token_usages_list)
        total_tokens += formalize_tokens

        total_duration = sum(
            [
                state.store.get("phase1_deps_duration", 0),
                state.store.get("phase2_formalize_duration", 0),
                state.store.get("phase3_plausibility_duration", 0),
            ]
        )

        config = load_config()
        state.store.set(
            "orchestration_summary",
            {
                "total_tokens": total_tokens,
                "total_duration_seconds": total_duration,
                "phases_completed": [
                    p
                    for p in [
                        "phase1_deps",
                        "phase2_formalize",
                        "phase3_plausibility"
                        if config.plausible.enabled and plausibility.ran
                        else None,
                    ]
                    if p is not None
                ],
                "num_functions_implemented": len(all_payloads) if all_payloads else 1,
            },
        )

        return state

    return run  # type: ignore[return-value]


@task
def fvspec(
    datafile: str,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    timestamp: datetime | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
    git_commit: str | None = None,
    model: str | None = None,
) -> Task:
    """Create fvspec benchmark task with unified formalization agent.

    Args:
        datafile: Path to pbts_full.db database file (relative to `./benchmark/data/`)
        variant: Prompt variant name from registry.toml
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints
        timestamp: Pre-created timestamp (defaults to now if None)
        start_idx: Starting index for sequential sampling (0-indexed, inclusive)
        end_idx: Ending index for sequential sampling (0-indexed, exclusive)
        git_commit: Git commit hash at generation time
        model: Model slug (e.g., "claude-sonnet-4-6")

    Returns:
        Task configured with unified formalization orchestration
    """
    now = timestamp or datetime.now()

    # Resolve variant
    registry = FormalizationVariantRegistry()
    resolved_variant = variant or registry.default_variant()

    # Load dataset
    db_path = DATA_DIR / datafile
    dataset = mk_dataset(
        db_path,
        now,
        variant=resolved_variant,
        sample_size=sample_size,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
        git_commit=git_commit,
        model=model,
    )

    return Task(
        dataset=dataset,
        setup=[
            workspace_setup(),
            pass_session_to_state(db_path),
        ],
        solver=[
            orchestrate_subagents(variant=resolved_variant),
        ],
        cleanup=write_to_disk,
    )
