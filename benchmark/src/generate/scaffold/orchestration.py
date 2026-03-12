"""Three-agent orchestration for fvspec benchmark.

Architecture:
1. Implementation Agent: Generates function implementations (zero sorry required)
2. Specification Agent: Generates theorem statements (with sorry for proofs)
3. Units Agent: Generates LSpec test suites from Python property-based tests

The orchestration runs agents with conversation isolation via fork(). Spec and units
agents run in parallel since they both depend on impl agent but not on each other.
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
from generate.scaffold.formalize.impl import (
    FunctionImplPayload,
    FunctionImplResult,
    function_impl_agent,
    payloads_from_datapoint,
)
from generate.scaffold.formalize.impl.lean_merger import append_to_lean_file
from generate.scaffold.formalize.plausible_runner import Plausibility, run_plausible
from generate.scaffold.formalize.spec import (
    SpecPayload,
    SpecResult,
    spec_generation_agent,
)
from generate.scaffold.formalize.spec.validator import extract_signatures
from generate.scaffold.formalize.units import (
    UnitsPayload,
    UnitsResult,
    units_generation_agent,
)
from generate.scaffold.quality_assessment import count_lean_theorems
from generate.scaffold.tools import utilio
from generate.scaffold.tools.declaration import write_to_disk
from generate.templates.spec import VariantRegistry

logger = logging.getLogger(__name__)


def _generate_fut_stub(function_name: str, pbt_code: str) -> str:
    r"""Generate a stub implementation when FUT source code is not available.

    IMPORTANT: Do NOT use Unit type for stubs. This leads to trivial theorems
    that inflate plausibility metrics without verification value.

    Instead, infers signature from PBT if possible, or uses generic polymorphic
    signature that forces the spec agent to think about types.

    Args:
        function_name: Name of the function under test (test_ prefix removed)
        pbt_code: The property-based test code (for signature inference)

    Returns:
        Lean code with stub implementation using inferred or generic signature

    Examples:
        >>> _generate_fut_stub("sort_list", "def test(xs): sort_list(xs)")
        'def sort_list (input : α) : β := sorry'
        >>> _generate_fut_stub("add", "def test(x, y): add(x, y)")
        'def add (x : α) (y : β) : γ := sorry'
    """
    import re

    # Try to infer arity from PBT code by looking for function calls
    # Pattern: function_name(arg1, arg2, ...)
    call_pattern = rf"\b{re.escape(function_name)}\s*\(([^)]*)\)"
    matches = list(re.finditer(call_pattern, pbt_code))

    # Count arguments from first match
    num_args = 0
    if matches:
        args_str = matches[0].group(1)
        # Simple heuristic: count commas + 1 (if non-empty)
        if args_str.strip():
            num_args = args_str.count(",") + 1

    # Generate signature based on inferred arity
    # Use generic type parameters (α, β, γ) instead of Unit
    if num_args == 0:
        # No args detected - use generic nullary signature
        # Avoid Unit type - use generic α instead to encourage type inference
        signature = f"def {function_name} : α := sorry"
    elif num_args == 1:
        signature = f"def {function_name} (input : α) : β := sorry"
    elif num_args == 2:
        signature = f"def {function_name} (x : α) (y : β) : γ := sorry"
    else:
        # Multiple arguments - generate generic parameters
        params = " ".join(f"(x{i} : α{i})" for i in range(1, num_args + 1))
        signature = f"def {function_name} {params} : β := sorry"

    stub = f"""import Batteries

namespace Fvspec.Impl

/-- {function_name}: Implementation not available in source repository.

    This is a stub with an inferred signature from the property-based test.
    The actual implementation could not be discovered, so a generic signature
    is provided to guide the specification agent.

    IMPORTANT: This stub uses generic type parameters (α, β, γ) instead of Unit
    to encourage the specification agent to infer meaningful types from the PBT
    and avoid generating trivial tautologies.

    TODO: Implement this function based on the specification requirements. -/
{signature}

end Fvspec.Impl
"""
    return stub


@solver
def impl_agent_solver(payload: FunctionImplPayload, workspace: Path) -> Solver:
    """Wrapper solver for implementation agent to use with fork().

    This wrapper enables conversation isolation by:
    1. Running the impl agent with its own TaskState copy (via fork())
    2. Moving results from metadata to store (framework-recommended pattern)
    3. Preserving isolated conversation history in store

    Args:
        payload: Implementation generation parameters
        workspace: Per-sample tmpdir for Lean files

    Returns:
        Solver that runs impl agent and stores results in state.store
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Call existing function_impl_agent (writes to state.metadata)
        impl_solver = function_impl_agent(payload, workspace)
        state = await impl_solver(state, generate)

        # Migrate result from metadata to store (framework-recommended)
        impl_result = state.metadata.pop("impl_result", {})
        state.store.set("impl_result", impl_result)

        return state

    return solve


@solver
def spec_agent_solver(payload: SpecPayload, workspace: Path) -> Solver:
    """Wrapper solver for specification agent to use with fork().

    This wrapper enables conversation isolation by:
    1. Running the spec agent with its own TaskState copy (via fork())
    2. Moving results from metadata to store (framework-recommended pattern)
    3. Preserving isolated conversation history in store

    Args:
        payload: Specification generation parameters
        workspace: Per-sample tmpdir for Lean files

    Returns:
        Solver that runs spec agent and stores results in state.store
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Call existing spec_generation_agent (writes to state.metadata)
        spec_solver = spec_generation_agent(payload, workspace)
        state = await spec_solver(state, generate)

        # Migrate result from metadata to store (framework-recommended)
        spec_result = state.metadata.pop("spec_result", {})
        state.store.set("spec_result", spec_result)

        return state

    return solve


@solver
def units_agent_solver(payload: UnitsPayload, workspace: Path) -> Solver:
    """Wrapper solver for units agent to use with fork().

    This wrapper enables conversation isolation by:
    1. Running the units agent with its own TaskState copy (via fork())
    2. Moving results from metadata to store (framework-recommended pattern)
    3. Preserving isolated conversation history in store

    Args:
        payload: Units generation parameters
        workspace: Per-sample tmpdir for Lean files

    Returns:
        Solver that runs units agent and stores results in state.store
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Call units_generation_agent (writes to state.metadata)
        units_solver = units_generation_agent(payload, workspace)
        state = await units_solver(state, generate)

        # Migrate result from metadata to store (framework-recommended)
        units_result = state.metadata.pop("units_result", {})
        state.store.set("units_result", units_result)

        return state

    return solve


@solver
def workspace_setup() -> Solver:
    """Create a per-sample workspace tmpdir for Lean files and LSP integration.

    Tmpdir Lifecycle:
    1. Setup phase: Creates tmpdir via create_sample_workspace()
    2. Solver phase: Agents write Lean code to workspace
    3. Cleanup phase: write_to_disk removes tmpdir

    Thread safety: Uses locks for parallel execution

    Returns:
        Solver that creates workspace and stores path in metadata
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        workspace = utilio.create_sample_workspace(str(state.sample_id))
        state.metadata["workspace"] = str(workspace)
        return state

    return run


@solver
def pass_session_to_state(db_path: Path) -> Solver:
    """Inject database session into task state for function discovery.

    Args:
        db_path: Path to the pbts_full.db SQLite database

    Returns:
        Solver that stores db session in metadata
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        # Create session and store in metadata for function discovery
        session = get_session(db_path)
        state.metadata["db_session"] = session
        return state

    return run


@solver
def orchestrate_subagents(variant: str | None = None) -> Solver:
    """Orchestrate impl agent then spec agent sequentially.

    Flow:
    1. Discover function code from database (if available)
    2. Generate function implementation → Impl.lean (zero sorry)
    3. Extract type signatures from Impl.lean
    4. Generate theorem statements → Spec.lean (with sorry)

    Args:
        variant: Prompt variant for both agents (functional/mvcgen style)

    Returns:
        Solver that orchestrates both agents
    """

    async def run(state: TaskState, generate_fn: Generate) -> TaskState:
        # Track total time for both agents
        start_time = time.time()

        # Get workspace and datapoint
        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            return state

        workspace = Path(workspace_path)
        datapoint = state.metadata.get("datapoint")
        if not isinstance(datapoint, Datapoint):
            return state

        # Determine function name from PBT name (fallback)
        # Heuristic: test_foo → foo, test_bar_baz → bar_baz
        function_name = datapoint.name
        if function_name.startswith("test_"):
            function_name = function_name[5:]

        # Phase 0: Complete all database work before fork() calls
        # (fork() uses deepcopy which cannot pickle database sessions)
        db_session = state.metadata.get("db_session")

        # Try to discover function code using multi-strategy discovery
        function_code = None
        function_info = None
        if db_session:
            function_info = discover_function_code(datapoint, db_session)
            if function_info and function_info.confidence >= 0.5:
                # Accept discovery - use discovered function (threshold 0.5 includes name matches)
                function_name = function_info.name
                function_code = function_info.code
                # Store discovery metadata for qa.json
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
                # Low confidence or no discovery - track failure
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
                        "resolved_name": function_name,  # Fallback name
                    },
                )

        # Get all payloads (FUT + dependencies) - requires db_session for discovery
        all_payloads = payloads_from_datapoint(datapoint, db_session)

        # Get unit tests from datapoint (populated at load time)
        unit_tests_data = datapoint.unit_tests
        logger.info(f"Found {len(unit_tests_data)} unit tests for {function_name}")

        # Close database session before any fork() calls
        # This prevents "cannot pickle 'module' object" errors during deepcopy
        if db_session:
            db_session.close()
            state.metadata.pop("db_session", None)

        # Map spec variant to impl variant style (control-functional → functional)
        spec_variant_name = variant or "control-functional"
        spec_registry = VariantRegistry()
        spec_variant = spec_registry.get_variant(spec_variant_name)
        impl_variant = spec_variant.style  # Extract style: functional or mvcgen

        impl_file = workspace / "Fvspec" / "Impl.lean"
        impl_file.parent.mkdir(parents=True, exist_ok=True)

        # Phase 1: Generate implementation for function under test
        # Only process FUT if we have source code for it
        # Skip if function_code is None - Phase 1b will handle dependencies
        # This prevents hallucination when agent has no code to work from
        phase1_start = time.time()
        impl_fut_tokens = 0  # Initialize to 0, will be updated if function_code exists
        if function_code is not None:
            impl_payload = FunctionImplPayload(
                function_name=function_name,
                function_code=function_code,
                dependencies={},  # Dependencies handled separately if needed
                variant=impl_variant,
            )

            # Call impl agent solver with fork() for conversation isolation
            # Track token usage before fork
            tokens_before_fut = state.token_usage
            impl_solver = impl_agent_solver(impl_payload, workspace)
            impl_state = await fork(state, impl_solver)

            # Track token usage after fork and count tool calls
            impl_fut_tokens = state.token_usage - tokens_before_fut
            impl_fut_toolcalls = sum(
                1
                for msg in impl_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )

            # Store FUT token usage metrics
            state.store.set(
                "impl_fut_token_usage",
                {
                    "subagent": "impl_fut",
                    "function_name": function_name,
                    "tokens_spent": impl_fut_tokens,
                    "num_toolcalls": impl_fut_toolcalls,
                },
            )

            # Extract result from isolated state's store
            impl_result_data = impl_state.store.get("impl_result", {})
            if isinstance(impl_result_data, dict):
                impl_result = FunctionImplResult(**impl_result_data)
            else:
                impl_result = impl_result_data

            # Save isolated conversation to parent store for debugging/replay
            state.store.set(
                "impl_conversation",
                [msg.model_dump() for msg in impl_state.messages],
            )
            state.store.set("impl_result", impl_result_data)

            # Write Impl.lean - use extracted code from final message (orchestration is authoritative)
            # Agent uses tools for validation, but final message contains the canonical version
            if impl_result.lean_code:
                impl_file.write_text(impl_result.lean_code)
                # Track that we provided full implementation
                state.store.set("implementation_level", "provided")
            else:
                # No impl code - write empty file to clear any validation artifacts
                impl_file.write_text("namespace Fvspec.Impl\n\nend Fvspec.Impl\n")
                # Track as absent (agent failed to generate)
                state.store.set("implementation_level", "absent")
        else:
            # No FUT source code - generate stub implementation
            # This allows the spec agent to have a signature to work with
            stub_impl = _generate_fut_stub(function_name, datapoint.code)
            impl_file.write_text(stub_impl)
            # Track that we provided only a signature
            state.store.set("implementation_level", "signature")
            # Log stub generation details
            state.store.set(
                "stub_generated",
                {
                    "reason": "no_function_code",
                    "function_name": function_name,
                },
            )

        # Log Phase 1 duration
        state.store.set("phase1_fut_duration", time.time() - phase1_start)

        # Phase 1b: Generate implementations for all dependencies
        dependency_implementations: dict[str, str] = {}
        dep_processing_details = []
        phase1b_start = time.time()

        for payload in all_payloads:
            # Skip FUT - already processed in Phase 1
            if payload.is_function_under_test:
                continue

            # Create impl payload for this dependency
            dep_impl_payload = FunctionImplPayload(
                function_name=payload.dep_name,
                function_code=payload.python_source,
                dependencies={},  # Will be accumulated as we process
                variant=impl_variant,
            )

            # Run impl agent for this dependency with fork() for isolation
            # Track token usage before fork
            tokens_before_dep = state.token_usage
            dep_impl_solver = impl_agent_solver(dep_impl_payload, workspace)
            dep_impl_state = await fork(state, dep_impl_solver)

            # Track token usage after fork and count tool calls
            dep_tokens = state.token_usage - tokens_before_dep
            dep_toolcalls = sum(
                1
                for msg in dep_impl_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )

            # Store dependency token usage metrics (append to list)
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

            # Extract result from isolated state's store
            dep_impl_result_data = dep_impl_state.store.get("impl_result", {})
            if isinstance(dep_impl_result_data, dict):
                dep_impl_result = FunctionImplResult(**dep_impl_result_data)
            else:
                dep_impl_result = dep_impl_result_data

            # Collect dependency processing details for logging
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

            # Save isolated conversation for this dependency (append to list)
            dep_conversations = state.store.get("dep_conversations", [])
            dep_conversations.append(
                {
                    "dep_name": payload.dep_name,
                    "messages": [msg.model_dump() for msg in dep_impl_state.messages],
                }
            )
            state.store.set("dep_conversations", dep_conversations)

            # Store successful implementations
            if dep_impl_result.success and dep_impl_result.lean_code:
                dependency_implementations[payload.dep_name] = dep_impl_result.lean_code
                # Merge dependency into Impl.lean (intelligent merge, not naive append)
                # This deduplicates imports, maintains single namespace, prevents redefinitions
                if impl_file.exists():
                    current_content = impl_file.read_text()
                    merged_content = append_to_lean_file(
                        current_content, dep_impl_result.lean_code
                    )
                    impl_file.write_text(merged_content)
                else:
                    impl_file.write_text(dep_impl_result.lean_code)

        # Store dependency count for metrics
        state.store.set("num_fns_impl", len(all_payloads))

        # Log Phase 1b duration and dependency processing details
        state.store.set("phase1b_deps_duration", time.time() - phase1b_start)
        state.store.set("phase1b_num_deps", len(dep_processing_details))
        state.store.set("dependency_processing", dep_processing_details)

        # Skip samples with excessive function counts (>50)
        # Rationale: Samples with >50 functions are extreme outliers that:
        # 1. Generate excessively large prompts and specs (degraded quality)
        # 2. Take disproportionately long to process (hurt parallelism)
        # 3. Exceed practical limits for meaningful specification generation
        # Note: This is a secondary filter after MAX_DEPENDENCIES=100 (query-time filter).
        # Some samples with <=100 deps in metadata may have >50 actual implementations
        # when function discovery resolves them from the database.
        MAX_FUNCTIONS_IMPL = 50
        if len(all_payloads) > MAX_FUNCTIONS_IMPL:
            state.store.set("skipped", True)
            state.store.set(
                "skip_reason",
                {
                    "cause": "excessive_functions",
                    "num_functions": len(all_payloads),
                    "limit": MAX_FUNCTIONS_IMPL,
                    "message": f"Too many functions to implement ({len(all_payloads)} > {MAX_FUNCTIONS_IMPL})",
                },
            )
            # Set minimal output so write_to_disk knows this was intentionally skipped
            # Preserve model name from previous agent execution instead of hardcoding
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

        # Phase 2: Extract type signatures from Impl.lean
        impl_signatures = {}
        impl_code = ""
        if impl_file.exists():
            impl_code = impl_file.read_text()
            impl_signatures = extract_signatures(impl_code)

        # Store signatures and impl code for debugging and quality assessment
        state.store.set("impl_signatures", impl_signatures)
        state.store.set("impl_code", impl_code)  # For Unit stub detection

        # Phase 3+4: Generate theorem statements and unit tests (parallel if unit tests exist)
        # Spec agent uses PBT (datapoint.code), units agent uses concrete unit tests from DB
        # Only invoke units agent if database has unit tests for this function
        has_unit_tests = len(unit_tests_data) > 0

        # Log parallel execution decision
        state.store.set(
            "parallel_execution_decision",
            {
                "has_unit_tests": has_unit_tests,
                "unit_test_count": len(unit_tests_data),
                "execution_mode": "parallel" if has_unit_tests else "spec_only",
                "reason": "Unit tests available in database"
                if has_unit_tests
                else "No unit tests available",
            },
        )

        if has_unit_tests:
            logger.info("Phase 3+4: Running spec and units agents in parallel")
        else:
            logger.info("Phase 3: Running spec agent only (no unit tests in DB)")

        # Build spec payload (always needed)
        spec_payload = SpecPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            function_name=function_name,
            impl_signatures=impl_signatures,
            variant=spec_variant_name,
        )

        # Create spec solver
        spec_solver = spec_agent_solver(spec_payload, workspace)

        # Conditionally create and run units agent in parallel with spec
        if has_unit_tests:
            # Concatenate all unit test code
            unit_test_code = "\n\n".join(
                ut["code"] for ut in unit_tests_data if ut.get("code")
            )
            # Use first test name as representative (or create descriptive name)
            unit_test_name = (
                unit_tests_data[0]["name"]
                if unit_tests_data
                else f"test_{function_name}"
            )

            units_payload = UnitsPayload(
                unit_test_code=unit_test_code,
                unit_test_name=unit_test_name,
                function_name=function_name,
                impl_signatures=impl_signatures,
            )
            units_solver = units_agent_solver(units_payload, workspace)

            # Run both agents in parallel with fork() for conversation isolation
            # fork() natively supports parallel execution when passed a list of solvers
            phase34_start = time.time()
            spec_state, units_state = await fork(state, [spec_solver, units_solver])

            # Track token usage after parallel fork
            # Note: parallel fork accumulates all tokens, so we calculate per-agent from individual states
            spec_tokens = spec_state.token_usage  # Spec state has its own token count
            units_tokens = (
                units_state.token_usage
            )  # Units state has its own token count

            # Count tool calls for each agent
            spec_toolcalls = sum(
                1
                for msg in spec_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )
            units_toolcalls = sum(
                1
                for msg in units_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )

            # Store token usage metrics for both agents
            state.store.set(
                "spec_token_usage",
                {
                    "subagent": "spec",
                    "tokens_spent": spec_tokens,
                    "num_toolcalls": spec_toolcalls,
                },
            )
            state.store.set(
                "units_token_usage",
                {
                    "subagent": "units",
                    "tokens_spent": units_tokens,
                    "num_toolcalls": units_toolcalls,
                },
            )

            # Log phase 3+4 duration
            state.store.set("phase34_parallel_duration", time.time() - phase34_start)

            # Log agent execution summaries
            spec_result_dict = spec_state.store.get("spec_result")
            state.store.set(
                "spec_agent_summary",
                {
                    "success": spec_result_dict.get("success", False)
                    if spec_result_dict
                    else False,
                    "lean_code_lines": len(
                        spec_result_dict.get("lean_code", "").splitlines()
                    )
                    if spec_result_dict
                    else 0,
                    "tokens_spent": spec_tokens,
                    "toolcalls": spec_toolcalls,
                },
            )

            units_result_dict = units_state.store.get("units_result")
            state.store.set(
                "units_agent_summary",
                {
                    "success": units_result_dict.get("success", False)
                    if units_result_dict
                    else False,
                    "test_count": units_result_dict.get("test_count", 0)
                    if units_result_dict
                    else 0,
                    "tokens_spent": units_tokens,
                    "toolcalls": units_toolcalls,
                },
            )
        else:
            # Only run spec agent
            # Track token usage before fork
            tokens_before_spec = state.token_usage
            phase3_start = time.time()
            spec_state = await fork(state, spec_solver)
            units_state = None

            # Track token usage after fork and count tool calls
            spec_tokens = state.token_usage - tokens_before_spec
            spec_toolcalls = sum(
                1
                for msg in spec_state.messages
                if msg.role == "assistant"
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            )

            # Store spec token usage metrics
            state.store.set(
                "spec_token_usage",
                {
                    "subagent": "spec",
                    "tokens_spent": spec_tokens,
                    "num_toolcalls": spec_toolcalls,
                },
            )

            # Log phase 3 duration (spec-only)
            state.store.set("phase3_spec_only_duration", time.time() - phase3_start)

            # Log spec agent summary
            spec_result_dict = spec_state.store.get("spec_result")
            state.store.set(
                "spec_agent_summary",
                {
                    "success": spec_result_dict.get("success", False)
                    if spec_result_dict
                    else False,
                    "lean_code_lines": len(
                        spec_result_dict.get("lean_code", "").splitlines()
                    )
                    if spec_result_dict
                    else 0,
                    "tokens_spent": spec_tokens,
                    "toolcalls": spec_toolcalls,
                },
            )

        # Extract spec result from isolated state's store
        spec_result_data = spec_state.store.get("spec_result", {})
        if isinstance(spec_result_data, dict):
            spec_result = SpecResult(**spec_result_data)
        else:
            spec_result = spec_result_data

        # Save spec isolated conversation to parent store for debugging/replay
        state.store.set(
            "spec_conversation", [msg.model_dump() for msg in spec_state.messages]
        )
        state.store.set("spec_result", spec_result_data)

        # Preserve spec agent's output for final state
        state.output = spec_state.output

        # Write Spec.lean - orchestration has authoritative version (clears validation artifacts)
        spec_file = workspace / "Fvspec" / "Spec.lean"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        if spec_result.lean_code:
            spec_file.write_text(spec_result.lean_code)
        else:
            # No spec code - write empty file to clear any validation artifacts
            spec_file.write_text(
                "import Fvspec.Impl\n\nnamespace Fvspec.Spec\n\nend Fvspec.Spec\n"
            )

        # Extract units result (from agent if ran, otherwise create skipped result)
        if units_state is not None:
            units_result_data = units_state.store.get("units_result", {})
            if isinstance(units_result_data, dict):
                units_result = UnitsResult(**units_result_data)
            else:
                units_result = units_result_data

            # Save units isolated conversation to parent store for debugging/replay
            state.store.set(
                "units_conversation", [msg.model_dump() for msg in units_state.messages]
            )
            state.store.set("units_result", units_result_data)

            # Log units generation result
            if units_result.success:
                logger.info(
                    f"Units generation succeeded: {units_result.test_count} tests"
                )
            else:
                logger.warning(f"Units generation failed: {units_result.error}")
        else:
            # No unit tests in DB - create skipped result
            units_result = UnitsResult(
                success=False,
                error="No unit tests in database for this function",
            )
            units_result_data = units_result.model_dump()
            state.store.set("units_conversation", [])
            state.store.set("units_result", units_result_data)
            logger.info("Units generation skipped: no unit tests in database")

        # Phase 5: Run plausible property testing (if enabled and spec compiled)
        plausibility = Plausibility()
        if spec_result.success and spec_result.lean_code and spec_file.exists():
            try:
                config = load_config()
                if config.plausible.enabled:
                    theorem_count = count_lean_theorems(spec_result.lean_code)
                    phase5_start = time.time()

                    plausibility = run_plausible(
                        spec_path=spec_file,
                        workspace_path=workspace,
                        timeout=config.plausible.timeout,
                        num_theorems=theorem_count,
                    )

                    # Log phase 5 duration and plausibility summary
                    state.store.set(
                        "phase5_plausibility_duration", time.time() - phase5_start
                    )
                    # Calculate plausible count (theorems without counterexamples)
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
                # If config loading or plausible execution fails, record error but continue
                plausibility = Plausibility(
                    ran=True,
                    success=0.0,
                    errors=[f"Error running plausible: {e}"],
                )

        # Store plausibility results in store for quality assessment
        state.store.set("plausibility", plausibility)

        # Set state.output so write_to_disk can persist the files
        # If plausible ran, read back the modified Spec.lean (with plausible instead of sorry)
        # Otherwise, use the original spec_result.lean_code
        if plausibility.ran and spec_file.exists():
            output_text = spec_file.read_text()
        else:
            output_text = spec_result.lean_code if spec_result.lean_code else ""

        if output_text:
            output_text = f"<code>\n{output_text}\n</code>"

        # Calculate total time for both agents
        total_time = time.time() - start_time

        # Preserve model name from the last agent execution (spec agent)
        # instead of hardcoding "orchestrated"
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

        # Calculate total tokens across all agents
        total_tokens = impl_fut_tokens
        dep_token_usages_list = state.store.get("dep_token_usages", [])
        for dep_usage in dep_token_usages_list:
            total_tokens += dep_usage["tokens_spent"]
        if has_unit_tests:
            total_tokens += spec_tokens + units_tokens
        else:
            total_tokens += spec_tokens

        # Calculate total duration across all phases
        total_duration = sum(
            [
                state.store.get("phase1_fut_duration", 0),
                state.store.get("phase1b_deps_duration", 0),
                state.store.get("phase34_parallel_duration", 0)
                if has_unit_tests
                else state.store.get("phase3_spec_only_duration", 0),
                state.store.get("phase5_plausibility_duration", 0),
            ]
        )

        # Store orchestration summary
        config = load_config()
        state.store.set(
            "orchestration_summary",
            {
                "total_tokens": total_tokens,
                "total_duration_seconds": total_duration,
                "phases_completed": [
                    p
                    for p in [
                        "phase1_fut",
                        "phase1b_deps",
                        "phase2_signatures",
                        "phase34_parallel" if has_unit_tests else "phase3_spec_only",
                        "phase5_plausibility"
                        if config.plausible.enabled and plausibility.ran
                        else None,
                    ]
                    if p is not None
                ],
                "num_functions_implemented": len(all_payloads) if all_payloads else 1,
                "execution_mode": "parallel" if has_unit_tests else "spec_only",
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
    require_unit_tests: bool = False,
    git_commit: str | None = None,
    model: str | None = None,
) -> Task:
    """Create fvspec benchmark task with two-agent architecture.

    Args:
        datafile: Path to pbts_full.db database file (relative to `./benchmark/data/`)
        variant: Prompt variant name from registry.toml (functional/mvcgen style)
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints
        timestamp: Pre-created timestamp (defaults to now if None)
        start_idx: Starting index for sequential sampling (0-indexed, inclusive)
        end_idx: Ending index for sequential sampling (0-indexed, exclusive)
        require_unit_tests: If True, only sample datapoints that have unit tests (default: False)
        git_commit: Git commit hash at generation time, forwarded to each sample's metadata.
        model: Model slug (e.g., "claude-sonnet-4-6"), forwarded to each sample's metadata for artifact path naming.

    Returns:
        Task configured with two-agent orchestration
    """
    now = timestamp or datetime.now()

    # Resolve variant to get consistent style for both agents
    registry = VariantRegistry()
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
        require_unit_tests=require_unit_tests,
        git_commit=git_commit,
        model=model,
    )

    # Three-agent architecture: impl → spec & units
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
