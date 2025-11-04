# Phase 2 Refactor: Implementation Plan (In Progress)

**Status**: Phase 1 ✅ Complete | Phase 2 🔄 In Progress (50%) | Phase 3-5 ⏳ Pending
**Branch**: `q/analyze-deps-2`
**Commits**: 348852c1 (Phase 1), cbe60a54 (Phase 2 partial)

## Overview

Two-agent architecture: **Implementation Agent** (formalize function + deps) → **Spec Agent** (generate theorem statements).
- Implementation: ZERO sorry (fully computable)
- Spec: sorry expected (stating theorems, not proving)
- Orchestrator: Pure Python logic (no LLM)

---

## ✅ Phase 1: Rename (COMPLETE)

**Goal**: Rename directories and update all imports.

**Completed**:
- ✅ Renamed `depmock/` → `formalize_impl/`
- ✅ Renamed `deps/` templates → `impl/`
- ✅ Updated all Python imports and function names
- ✅ All 155 tests passing
- ✅ Commit: 348852c1

---

## 🔄 Phase 2: Function Discovery Integration (50% COMPLETE)

**Goal**: Integrate function discovery into formalize_impl agent.

### ✅ Completed (Step 1/4)

**dataset.py integration** (commit cbe60a54):
- Added `discover_function_code()` call in `payloads_from_datapoint()`
- Discovered function becomes first payload when confidence > 0.7
- Tagged as "function_under_test" + discovery_method
- Session parameter optional (backward compatible)
- All tests passing

### ⏳ Remaining Tasks

#### Step 2: Update agent.py for Discovery Tracking

**File**: `src/generate/scaffold/formalize_impl/agent.py`

**Changes needed**:
```python
# Around line 50-70 where payloads are processed
async def implementation_formalization_agent(...):
    # Log discovery results
    if payloads and "function_under_test" in payloads[0].tags:
        logger.info(
            f"Discovered function: {payloads[0].dep_name} "
            f"(confidence: {payloads[0].confidence}, "
            f"method: {payloads[0].tags[1]})"
        )

    # Track discovery in agent metadata
    state.metadata["function_discovered"] = bool(
        payloads and "function_under_test" in payloads[0].tags
    )
```

**Testing**:
- Run single sample with known discoverable function
- Verify log message appears
- Check metadata populated

#### Step 3: Add Discovery Metadata to Models

**File**: `src/generate/scaffold/formalize_impl/models.py`

**Changes needed**:

1. Update `DependencyPayload` to track confidence:
```python
class DependencyPayload(BaseModel):
    # ... existing fields ...
    confidence: float | None = None  # NEW: discovery confidence

    @computed_field
    @property
    def is_function_under_test(self) -> bool:
        """Check if this is the discovered function under test."""
        return "function_under_test" in self.tags
```

2. Update `DependencyResult` to include discovery info:
```python
class DependencyResult(BaseModel):
    # ... existing fields ...
    function_discovery: FunctionDiscoveryInfo | None = None  # NEW

class FunctionDiscoveryInfo(BaseModel):
    """Metadata about function discovery."""
    discovered: bool
    function_name: str | None
    confidence: float | None
    method: str | None  # DiscoveryMethod value
```

3. Update dataset.py to pass confidence:
```python
# In payloads_from_datapoint(), add:
payloads.append(
    DependencyPayload(
        # ... existing fields ...
        confidence=function_info.confidence,  # NEW
    )
)
```

**Testing**:
- Unit tests for new fields
- Serialization/deserialization tests

#### Step 4: Create Implementation Templates

**File**: `src/generate/templates/impl/common/fragments/function_under_test.prompt`

**New template**:
```jinja2
{% if is_function_under_test %}
## Primary Function Under Test

This is the MAIN function being tested by the property-based test.

**Discovery Metadata:**
- Confidence: {{ confidence * 100 }}%
- Method: {{ tags[1] }}

### Python Implementation

```python
{{ python_source }}
```

### Test Usage Example

```python
{{ usage_example }}
```

**CRITICAL REQUIREMENTS:**
1. This function MUST be fully computable (NO sorry allowed)
2. Use `def`, never `axiom`
3. All dependencies must also be fully computable
4. This is an IMPLEMENTATION, not a specification

This is different from spec generation where sorry is acceptable.
Here we need EXECUTABLE code that actually computes results.
{% endif %}
```

**File**: `src/generate/templates/impl/variants/functional/translate.prompt.template`

**Update to include fragment**:
```jinja2
# Near the top, after system context:

{% include "impl/common/fragments/function_under_test.prompt" %}

# Then existing dependency translation content...
```

**Same for**: `impl/variants/mvcgen/translate.prompt.template`

**Testing**:
- Render template with function_under_test payload
- Verify conditional includes work
- Check formatting

#### Step 5: Integration Testing

**Test script**: `src/tests/test_phase2_integration.py`

```python
import pytest
from sqlmodel import Session, create_engine

from generate.scaffold.dataset import Datapoint, get_session
from generate.scaffold.formalize_impl.dataset import payloads_from_datapoint

def test_function_discovery_integration():
    """Test that discovered function appears as first payload."""
    # Use test database
    engine = create_engine("sqlite:///data/pbts_full.db")
    with Session(engine) as session:
        # Get a sample we know has discoverable function
        datapoint = session.get(Datapoint, 5)

        # Generate payloads WITH session
        payloads = payloads_from_datapoint(datapoint, session=session)

        # Assertions
        assert len(payloads) > 0, "Should have at least one payload"

        first = payloads[0]
        assert "function_under_test" in first.tags, "First should be discovered function"
        assert first.confidence is not None, "Should have confidence score"
        assert first.confidence > 0.7, "Should meet confidence threshold"
        assert first.code is not None, "Should have function code"
        assert first.usage_example is not None, "Should have PBT as usage example"

def test_function_discovery_backward_compat():
    """Test that without session, discovery is skipped."""
    datapoint = Datapoint(
        id=1,
        code="def test_foo(): pass",
        deps='["helper"]',
        dep_names='["helper"]',
    )

    # WITHOUT session
    payloads = payloads_from_datapoint(datapoint, session=None)

    # Should only have explicit dependencies
    assert all("function_under_test" not in p.tags for p in payloads)
```

**Run**:
```bash
uv run pytest src/tests/test_phase2_integration.py -v
```

#### Step 6: Commit Phase 2

```bash
git add -A
git commit -m "feat(phase2): complete function discovery integration

Remaining changes for Phase 2:
- Add discovery tracking in agent.py
- Add discovery metadata to models.py
- Create function_under_test.prompt template
- Integration tests with real database

All implementation agent payloads now include discovered function first
when confidence > 0.7, fully tagged and tracked.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## ⏳ Phase 3: Spec Agent (PENDING)

**Goal**: Create separate agent for spec generation from PBT.

### Step 1: Create Directory Structure

```bash
mkdir -p src/generate/scaffold/formalize_spec
touch src/generate/scaffold/formalize_spec/{__init__,agent,runner,models,validator}.py
```

### Step 2: Implement Validator

**File**: `src/generate/scaffold/formalize_spec/validator.py`

```python
"""Validation utilities for spec agent."""

from __future__ import annotations

import re

from pydantic import BaseModel


class SpecValidation(BaseModel):
    """Result of spec validation."""

    compiles: bool  # No type errors
    has_statements: bool  # Has theorem/def statements
    has_sorry: bool  # Has sorry (this is GOOD for specs!)
    valid: bool  # Overall: compiles AND has_statements
    errors: list[str] = []


def validate_spec_output(lean_code: str, diagnostics: str) -> SpecValidation:
    """
    Validate spec agent output.

    Checks:
    1. Code compiles (no type errors)
    2. Has theorem/def statements
    3. Has sorry (tracked but not required - sorry is GOOD for specs!)

    Args:
        lean_code: Generated Lean code
        diagnostics: Output from lean_diagnostic_messages

    Returns:
        Validation result
    """
    has_errors = "error:" in diagnostics.lower()
    has_theorem = bool(
        re.search(r'\b(theorem|def|lemma)\b', lean_code)
    )
    has_sorry = bool(re.search(r'\bsorry\b', lean_code))

    errors = []
    if has_errors:
        errors.append("Code has type errors")
    if not has_theorem:
        errors.append("No theorem/def statements found")

    return SpecValidation(
        compiles=not has_errors,
        has_statements=has_theorem,
        has_sorry=has_sorry,
        valid=not has_errors and has_theorem,
        errors=errors,
    )


def extract_signatures(impl_lean: str) -> dict[str, str]:
    """
    Extract function signatures from Impl.lean.

    Parses lines like:
        def foo (x : Nat) : Nat := ...

    Returns:
        {"foo": "def foo (x : Nat) : Nat"}
    """
    signatures = {}
    pattern = re.compile(
        r'^(def|structure|inductive|class)\s+(\w+)\s*([^:]*:\s*[^:=]+)',
        re.MULTILINE
    )

    for match in pattern.finditer(impl_lean):
        keyword, name, sig = match.groups()
        signatures[name] = f"{keyword} {name} {sig}".strip()

    return signatures
```

### Step 3: Implement Models

**File**: `src/generate/scaffold/formalize_spec/models.py`

```python
"""Data models for spec agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpecPayload(BaseModel):
    """Input to spec generation agent."""

    pbt_code: str = Field(..., description="Property-based test code")
    pbt_name: str = Field(..., description="Test name")
    impl_signatures: dict[str, str] = Field(
        default_factory=dict,
        description="Function signatures from Impl.lean"
    )
    unit_tests: list[dict[str, str]] = Field(
        default_factory=list,
        description="Extracted unit tests"
    )
    function_name: str = Field(..., description="Main function name")
    variant: str = Field(..., description="Spec variant (control-functional, etc)")


class SpecResult(BaseModel):
    """Output from spec generation agent."""

    success: bool
    lean_code: str | None = None
    attempts: int = 0
    compiles: bool = False
    has_sorry: bool = False  # Track but don't require absence
    has_statements: bool = False
    error: str | None = None

    # Metrics
    tool_calls: int = 0
    refinement_iterations: int = 0


class SpecExecutionRequest(BaseModel):
    """Request to run spec agent."""

    payload: SpecPayload
    workspace: str  # Path to workspace
    max_attempts: int = 16
```

### Step 4: Implement Spec Agent

**File**: `src/generate/scaffold/formalize_spec/agent.py`

**Key implementation** (400 lines):
```python
"""Spec generation agent using LSP tools."""

from __future__ import annotations

import logging
from pathlib import Path

from inspect_ai import Agent
from inspect_ai.agent import agent
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, ModelOutput
from inspect_ai.solver import TaskState, Generate

from generate.scaffold.formalize_spec.models import (
    SpecPayload,
    SpecResult,
)
from generate.scaffold.formalize_spec.validator import validate_spec_output
from generate.scaffold.tools.declaration import lean_lsp_mcp_tools
from generate.templates.spec import SpecTemplateRegistry

logger = logging.getLogger(__name__)


@agent
async def spec_generation_agent(
    payload: SpecPayload,
    workspace: Path,
) -> SpecResult:
    """
    Generate Lean spec from PBT using impl signatures.

    Goal: Theorem statement that captures PBT invariants.
    Proof obligations SHOULD use 'sorry' - we're stating, not proving!

    Loops until:
    - Code compiles (no type errors)
    - Has proper theorem statements

    Args:
        payload: Spec generation payload
        workspace: Workspace path for LSP

    Returns:
        Spec generation result
    """
    # Load templates
    registry = SpecTemplateRegistry()
    system_prompt = registry.load_system(payload.variant)
    generate_template = registry.load_template(payload.variant, "generate")
    refine_template = registry.load_template(payload.variant, "refine")

    # Initial context
    context = payload.model_dump()

    # Initial generation
    messages = [
        ChatMessageSystem(content=system_prompt),
        ChatMessageUser(content=generate_template.render(**context)),
    ]

    # Get LSP tools
    tools = lean_lsp_mcp_tools()

    # Agent loop: refine until compiles
    max_attempts = 16
    tool_calls_count = 0

    for attempt in range(max_attempts):
        # Generate response
        response = await model.generate(messages, tools=tools)
        messages.append(response.message)

        if response.message.tool_calls:
            # Execute LSP tools
            tool_calls_count += len(response.message.tool_calls)
            tool_results = await execute_tools(
                response.message.tool_calls,
                workspace
            )
            messages.extend(tool_results)
        else:
            # Agent returned code
            lean_code = extract_code_block(response.message.content)

            # Validate: compiles + has theorems
            diagnostics = await get_diagnostics(lean_code, workspace)
            validation = validate_spec_output(lean_code, diagnostics)

            if validation.valid:
                # Success! (sorry is expected and good)
                return SpecResult(
                    success=True,
                    lean_code=lean_code,
                    attempts=attempt + 1,
                    compiles=True,
                    has_sorry=validation.has_sorry,
                    has_statements=validation.has_statements,
                    tool_calls=tool_calls_count,
                )
            else:
                # Has errors: refine
                if attempt < max_attempts - 1:
                    messages.append(
                        ChatMessageUser(
                            content=refine_template.render(
                                current_code=lean_code,
                                diagnostics=diagnostics,
                                errors=validation.errors,
                            )
                        )
                    )

    # Failed: couldn't get it to compile
    return SpecResult(
        success=False,
        lean_code=lean_code,
        attempts=max_attempts,
        compiles=False,
        error="Max attempts reached, code still has type errors",
        tool_calls=tool_calls_count,
    )


def extract_code_block(content: str) -> str:
    """Extract code from <code>...</code> tags."""
    import re
    match = re.search(r'<code>(.*?)</code>', content, re.DOTALL)
    return match.group(1).strip() if match else content


async def execute_tools(tool_calls, workspace):
    """Execute LSP tool calls."""
    # Implementation similar to formalize_impl/agent.py
    pass


async def get_diagnostics(lean_code: str, workspace: Path) -> str:
    """Get Lean diagnostics for code."""
    # Write to temp file, call lean_diagnostic_messages
    pass
```

### Step 5: Implement Runner

**File**: `src/generate/scaffold/formalize_spec/runner.py`

```python
"""Per-sample orchestration for spec agent."""

from __future__ import annotations

import logging
from pathlib import Path

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize_spec.agent import spec_generation_agent
from generate.scaffold.formalize_spec.models import (
    SpecPayload,
    SpecResult,
)
from generate.scaffold.units import extract_unit_tests

logger = logging.getLogger(__name__)


async def run_spec_agent(
    datapoint: Datapoint,
    impl_signatures: dict[str, str],
    variant: str,
    workspace: Path,
) -> SpecResult:
    """
    Run spec generation agent for a single datapoint.

    Args:
        datapoint: The test datapoint
        impl_signatures: Function signatures from Impl.lean
        variant: Spec variant (control-functional, etc)
        workspace: Workspace path

    Returns:
        Spec generation result
    """
    # Extract unit tests
    unit_tests = extract_unit_tests(datapoint.code)

    # Create payload
    payload = SpecPayload(
        pbt_code=datapoint.code,
        pbt_name=datapoint.name,
        impl_signatures=impl_signatures,
        unit_tests=unit_tests,
        function_name=datapoint.name.replace("test_", ""),
        variant=variant,
    )

    # Run agent
    logger.info(f"Running spec agent for {datapoint.name}...")
    result = await spec_generation_agent(payload, workspace)

    if result.success:
        logger.info(
            f"✓ Spec agent succeeded: {result.attempts} attempts, "
            f"compiles={'✓' if result.compiles else '✗'}, "
            f"has_sorry={'✓' if result.has_sorry else '✗'}"
        )
    else:
        logger.error(f"✗ Spec agent failed: {result.error}")

    return result
```

### Step 6: Create Spec Templates

**Directory structure**:
```
src/generate/templates/spec/
├── registry.py           # NEW
├── variants/
│   ├── control-functional/
│   │   ├── system.prompt           # NEW: Extract from current
│   │   ├── generate.prompt.template  # NEW
│   │   └── refine.prompt.template    # NEW
│   ├── control-mvcgen/
│   ├── terse-functional/
│   └── terse-mvcgen/
└── common/fragments/
    ├── impl_reference.prompt       # NEW
    └── no_sorry_requirement.prompt # NEW
```

**File**: `src/generate/templates/spec/registry.py`

```python
"""Template registry for spec agent."""

from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent


class SpecTemplateRegistry:
    """Load spec agent templates by variant."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load_system(self, variant: str) -> str:
        """Load system prompt for variant."""
        path = f"variants/{variant}/system.prompt"
        template = self.env.get_template(path)
        return template.render()

    def load_template(self, variant: str, name: str) -> Template:
        """Load template (generate or refine) for variant."""
        path = f"variants/{variant}/{name}.prompt.template"
        return self.env.get_template(path)
```

**File**: `src/generate/templates/spec/variants/control-functional/system.prompt`

```
You are a Lean 4 specification generator.

Given:
- Python property-based test
- Extracted unit tests
- Lean implementation signatures (from Impl.lean)

Generate Lean theorem statements that:
1. Match the implementation function signature EXACTLY
2. Capture the invariants from the property test
3. Use 'sorry' for proof obligations

IMPORTANT: Your output should be THEOREM STATEMENTS with sorry proofs.

Example:
```lean
theorem my_property (x : Nat) : my_function x < 100 := by
  sorry
```

The 'sorry' is EXPECTED - we want the theorem statement, not the proof.

You have access to LSP tools to check your code compiles.
```

**File**: `src/generate/templates/spec/variants/control-functional/generate.prompt.template`

```jinja2
Generate a Lean 4 specification for this property-based test.

## Property Test

```python
{{ pbt_code }}
```

## Implementation Signatures (from Impl.lean)

{% for func_name, signature in impl_signatures.items() %}
```lean
{{ signature }}
```
{% endfor %}

## Unit Tests

{% for test in unit_tests %}
- Input: `{{ test.input }}`
- Expected: `{{ test.expected }}`
{% endfor %}

## Task

Write a Lean 4 specification:
1. Function signature MUST match implementation
2. Capture PBT invariants as theorem statements
3. Use `sorry` for proof obligations (you're stating, not proving)
4. Ensure code compiles (type-checks)

Output format:
<code>
-- Lean code here
</code>
```

**File**: `src/generate/templates/spec/variants/control-functional/refine.prompt.template`

```jinja2
Your spec has errors. Please refine.

## Current Code

```lean
{{ current_code }}
```

## Diagnostics

```
{{ diagnostics }}
```

## Errors

{% for error in errors %}
- {{ error }}
{% endfor %}

## Instructions

Fix the type errors. Use LSP tools:
- `lean_diagnostic_messages` - check errors
- `lean_term_goal` - check expected types
- `lean_goal` - see proof state (if applicable)

Remember: Implementation signatures are in Impl.lean. Match them exactly.
Sorry is OK for proofs - focus on making the theorem statement type-check.

Output format:
<code>
-- Refined Lean code
</code>
```

### Step 7: Testing

**Test file**: `src/tests/test_spec_agent.py`

```python
import pytest
from pathlib import Path

from generate.scaffold.formalize_spec.models import SpecPayload
from generate.scaffold.formalize_spec.agent import spec_generation_agent
from generate.scaffold.formalize_spec.validator import (
    validate_spec_output,
    extract_signatures,
)


def test_validate_spec_output_success():
    """Test validation accepts valid spec."""
    code = """
theorem foo_property (x : Nat) : x + 1 > x := by
  sorry
"""
    diagnostics = ""  # No errors

    result = validate_spec_output(code, diagnostics)

    assert result.valid
    assert result.compiles
    assert result.has_statements
    assert result.has_sorry  # This is GOOD for specs!


def test_extract_signatures():
    """Test signature extraction from Impl.lean."""
    impl = """
def foo (x : Nat) : Nat := x + 1
def bar (x y : Nat) : Bool := x < y
"""

    sigs = extract_signatures(impl)

    assert "foo" in sigs
    assert "bar" in sigs
    assert "Nat" in sigs["foo"]


@pytest.mark.asyncio
async def test_spec_agent_integration(tmp_path):
    """Integration test for spec agent."""
    payload = SpecPayload(
        pbt_code="@given(st.integers())\ndef test_inc(x): assert x + 1 > x",
        pbt_name="test_inc",
        impl_signatures={"inc": "def inc (x : Nat) : Nat"},
        unit_tests=[{"input": "5", "expected": "6"}],
        function_name="inc",
        variant="control-functional",
    )

    result = await spec_generation_agent(payload, tmp_path)

    assert result.success or result.error is not None
    # May fail due to mock environment, but should return valid result
```

### Step 8: Commit Phase 3

```bash
git add src/generate/scaffold/formalize_spec/
git add src/generate/templates/spec/
git add src/tests/test_spec_agent.py
git commit -m "feat(phase3): implement spec generation agent

Complete spec agent implementation:
- validator.py: Validates compiles + has statements (sorry is good!)
- models.py: SpecPayload, SpecResult data models
- agent.py: Spec generation agent with LSP loop
- runner.py: Per-sample orchestration
- templates: System prompts, generate/refine templates for all variants
- tests: Unit and integration tests

Spec agent generates theorem statements from PBTs, using sorry for proofs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## ⏳ Phase 4: Orchestration (PENDING)

**Goal**: Wire everything together with Python orchestration logic.

### Step 1: Rewrite task.py Orchestration

**File**: `src/generate/scaffold/task.py`

**Major rewrite** - replace direct spec generation with orchestration:

```python
@task
def fvspec(
    datafile: str,
    # ... existing params ...
):
    """Main task with two-agent orchestration."""

    # Load dataset
    dataset = mk_dataset(datafile, limit=sample_size)

    # Create database session for function discovery
    from generate.scaffold.dataset import get_session
    session = get_session(DATA_DIR / "pbts_full.db")

    # Setup solvers
    fvspec_task = Task(
        dataset=dataset,
        setup=[
            workspace_setup(),
            pass_session_to_state(session),  # NEW
        ],
        solver=[
            orchestrate_two_agents(variant=variant),  # NEW: replaces old flow
        ],
        scorer=scorer,
        config=GenerateConfig(max_messages=max_messages),
        epochs=epochs,
    )

    return fvspec_task


@solver
def pass_session_to_state(session: Session) -> Solver:
    """Pass database session to task state."""
    async def run(state: TaskState, generate: Generate) -> TaskState:
        state.metadata["session"] = session
        return state
    return run


@solver
def orchestrate_two_agents(variant: str) -> Solver:
    """
    Orchestrate implementation and spec agents sequentially.

    Flow:
    1. Run implementation agent (formalize function + deps)
    2. Validate impl has zero sorry
    3. Extract signatures from Impl.lean
    4. Run spec agent (generate theorem statements)
    5. Validate spec compiles
    6. Collect metrics from both agents
    """
    async def run(state: TaskState, generate: Generate) -> TaskState:
        from generate.scaffold.formalize_impl.runner import run_formalize_impl_for_sample
        from generate.scaffold.formalize_spec.runner import run_spec_agent
        from generate.scaffold.formalize_spec.validator import extract_signatures

        datapoint = state.metadata["datapoint"]
        session = state.metadata["session"]
        workspace = state.metadata["workspace"]

        # Phase 1: Implementation Agent
        logger.info("=" * 60)
        logger.info("PHASE 1: Implementation Formalization")
        logger.info("=" * 60)

        impl_result = await run_formalize_impl_for_sample(
            datapoint=datapoint,
            session=session,
            variant=variant,
            workspace=workspace,
        )

        if not impl_result.get("success"):
            state.metadata["error"] = "impl_agent_failed"
            state.metadata["error_detail"] = impl_result.get("error")
            return state

        # Validate: Impl.lean has ZERO sorry
        impl_lean = impl_result["lean_text"]
        if has_sorry(impl_lean):
            state.metadata["error"] = "impl_has_sorry"
            state.metadata["error_detail"] = (
                "Implementation must be fully computable (no sorry allowed)"
            )
            return state

        # Validate: Impl.lean compiles
        impl_diagnostics = await check_lean_file(workspace / "Impl.lean")
        if "error:" in impl_diagnostics:
            state.metadata["error"] = "impl_compile_error"
            state.metadata["error_detail"] = impl_diagnostics
            return state

        logger.info(f"✓ Implementation agent succeeded")
        logger.info(f"  Modules: {len(impl_result['manifest'])}")
        logger.info(f"  Sorry count: 0 (required)")

        # Phase 2: Spec Agent
        logger.info("=" * 60)
        logger.info("PHASE 2: Specification Generation")
        logger.info("=" * 60)

        # Extract signatures for spec agent
        signatures = extract_signatures(impl_lean)

        spec_result = await run_spec_agent(
            datapoint=datapoint,
            impl_signatures=signatures,
            variant=variant,
            workspace=workspace,
        )

        if not spec_result.success:
            state.metadata["error"] = "spec_agent_failed"
            state.metadata["error_detail"] = spec_result.error
            return state

        logger.info(f"✓ Spec agent succeeded")
        logger.info(f"  Attempts: {spec_result.attempts}")
        logger.info(f"  Compiles: {'✓' if spec_result.compiles else '✗'}")
        logger.info(f"  Has sorry: {'✓' if spec_result.has_sorry else '✗'} (expected)")

        # Success: Both agents completed
        state.metadata["impl_agent"] = {
            "success": True,
            "modules": len(impl_result["manifest"]),
            "has_sorry": False,
            "function_discovered": impl_result.get("function_discovered", False),
            "discovery_confidence": impl_result.get("discovery_confidence"),
        }

        state.metadata["spec_agent"] = {
            "success": True,
            "attempts": spec_result.attempts,
            "compiles": spec_result.compiles,
            "has_sorry": spec_result.has_sorry,
            "tool_calls": spec_result.tool_calls,
        }

        # Output is the spec
        state.output = ModelOutput.from_content(
            model=generate.model,
            content=spec_result.lean_code,
        )

        return state

    return run


def has_sorry(lean_code: str) -> bool:
    """Check if Lean code contains sorry."""
    import re
    return bool(re.search(r'\bsorry\b', lean_code))


async def check_lean_file(path: Path) -> str:
    """Check if Lean file compiles, return diagnostics."""
    # Use lean_diagnostic_messages tool
    pass
```

### Step 2: Update quality_assessment.py

**File**: `src/generate/scaffold/quality_assessment.py`

**Add metrics tracking for both agents**:

```python
def extract_quality_metrics(state: TaskState, sample: Sample) -> dict[str, Any]:
    """Extract metrics from task state."""

    # Existing metrics...

    # NEW: Implementation agent metrics
    impl_metrics = state.metadata.get("impl_agent", {})
    spec_metrics = state.metadata.get("spec_agent", {})

    metrics["impl_agent"] = {
        "success": impl_metrics.get("success", False),
        "modules_count": impl_metrics.get("modules", 0),
        "has_sorry": impl_metrics.get("has_sorry"),
        "function_discovered": impl_metrics.get("function_discovered", False),
        "discovery_method": impl_metrics.get("discovery_method"),
        "discovery_confidence": impl_metrics.get("discovery_confidence"),
    }

    metrics["spec_agent"] = {
        "success": spec_metrics.get("success", False),
        "attempts": spec_metrics.get("attempts", 0),
        "compiles": spec_metrics.get("compiles", False),
        "has_sorry": spec_metrics.get("has_sorry"),
        "tool_calls": spec_metrics.get("tool_calls", 0),
    }

    metrics["pipeline"] = {
        "both_succeeded": (
            impl_metrics.get("success") and spec_metrics.get("success")
        ),
        "impl_computable": not impl_metrics.get("has_sorry", True),
        "spec_states_theorem": spec_metrics.get("has_sorry", False),
    }

    return metrics
```

### Step 3: Update Artifact Structure

**New structure**:
```
artifacts/{timestamp}__{variant}/{sample_id}__{pbt_name}/
├── Spec.lean              # From spec agent (with sorry)
├── Impl.lean              # From impl agent (zero sorry)
├── Tests.lean             # Unit tests
├── impl/                  # Implementation agent details
│   ├── {Module1}.lean
│   ├── {Module2}.lean
│   └── manifest.jsonl
├── qa.json                # Metrics from both agents
└── logs/
    ├── impl_agent.log     # Implementation agent messages
    ├── spec_agent.log     # Spec agent messages
    └── orchestration.log  # Orchestration flow
```

### Step 4: Testing

**Test orchestration**:
```bash
# Single sample test
uv run fvspec --variant control-functional --sample-size 1 --parallelism 1

# Check artifacts
ls artifacts/{timestamp}__control-functional/00001_test_*/
cat artifacts/{timestamp}__control-functional/00001_test_*/Impl.lean  # Should have zero sorry
cat artifacts/{timestamp}__control-functional/00001_test_*/Spec.lean  # Should have sorry
cat artifacts/{timestamp}__control-functional/00001_test_*/qa.json | jq .impl_agent
cat artifacts/{timestamp}__control-functional/00001_test_*/qa.json | jq .spec_agent
```

### Step 5: Commit Phase 4

```bash
git add src/generate/scaffold/task.py
git add src/generate/scaffold/quality_assessment.py
git commit -m "feat(phase4): implement two-agent orchestration

Python orchestration of implementation + spec agents:
- Implementation agent: discovers function, formalizes with zero sorry
- Spec agent: generates theorem statements (sorry expected)
- Validates: impl compiles, spec compiles
- Tracks: metrics from both agents separately
- Artifacts: Impl.lean (computable) + Spec.lean (statements)

All orchestration is pure Python logic (no LLM orchestrator).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## ⏳ Phase 5: Validation & Optimization (PENDING)

**Goal**: Validate system works, optimize based on metrics.

### Step 1: Run Full Benchmark

```bash
# 50 samples
uv run fvspec --variant control-functional --sample-size 50 --parallelism 10

# Check results
uv run inspect view --log-dir artifacts
```

### Step 2: Analyze Metrics

**Analysis script**: `src/scripts/analyze_phase2_results.py`

```python
"""Analyze Phase 2 refactor results."""

import json
from pathlib import Path
from collections import Counter

def analyze_results(artifacts_dir: Path):
    """Analyze metrics from Phase 2 refactor run."""

    # Collect all qa.json files
    qa_files = list(artifacts_dir.rglob("qa.json"))

    impl_success = []
    spec_success = []
    discovery_methods = []
    discovery_confidences = []

    for qa_file in qa_files:
        with open(qa_file) as f:
            metrics = json.load(f)

        impl = metrics.get("impl_agent", {})
        spec = metrics.get("spec_agent", {})

        impl_success.append(impl.get("success", False))
        spec_success.append(spec.get("success", False))

        if impl.get("function_discovered"):
            discovery_methods.append(impl.get("discovery_method"))
            discovery_confidences.append(impl.get("discovery_confidence"))

    # Report
    print("=" * 60)
    print("PHASE 2 REFACTOR RESULTS")
    print("=" * 60)
    print(f"\nTotal samples: {len(qa_files)}")

    print(f"\n## Implementation Agent")
    print(f"Success rate: {sum(impl_success)/len(impl_success)*100:.1f}%")
    print(f"Function discovery rate: {len(discovery_methods)/len(qa_files)*100:.1f}%")

    if discovery_methods:
        print(f"\nDiscovery methods:")
        for method, count in Counter(discovery_methods).most_common():
            print(f"  {method}: {count} ({count/len(discovery_methods)*100:.1f}%)")

        print(f"\nDiscovery confidence:")
        print(f"  Mean: {sum(discovery_confidences)/len(discovery_confidences):.2f}")
        print(f"  Min: {min(discovery_confidences):.2f}")
        print(f"  Max: {max(discovery_confidences):.2f}")

    print(f"\n## Spec Agent")
    print(f"Success rate: {sum(spec_success)/len(spec_success)*100:.1f}%")

    print(f"\n## Pipeline")
    both = sum(1 for i, s in zip(impl_success, spec_success) if i and s)
    print(f"Both succeeded: {both} ({both/len(qa_files)*100:.1f}%)")


if __name__ == "__main__":
    import sys
    artifacts_dir = Path(sys.argv[1])
    analyze_results(artifacts_dir)
```

**Run**:
```bash
uv run python src/scripts/analyze_phase2_results.py artifacts/{timestamp}__control-functional/
```

### Step 3: Identify Issues

**Common failure modes**:

1. **Impl agent produces sorry**:
   - Root cause: Complex dependency can't be formalized
   - Fix: Strengthen "no sorry" emphasis in prompt
   - Alternative: Add retry with explicit no-sorry instruction

2. **Spec agent can't compile**:
   - Root cause: Signature mismatch with impl
   - Fix: Improve signature extraction
   - Alternative: Pass full impl file, not just signatures

3. **Function discovery fails**:
   - Root cause: Complex test pattern
   - Fix: Add more discovery strategies
   - Track: Which strategies fail most often

4. **Pipeline too slow**:
   - Root cause: Too many agent iterations
   - Fix: Optimize prompts for fewer refinements
   - Alternative: Set lower max_attempts

### Step 4: Optimize Prompts

Based on analysis, update:

1. **Impl agent prompts** (`impl/variants/*/translate.prompt.template`):
   - Add stronger "ZERO sorry" emphasis
   - Provide examples of common patterns
   - Add troubleshooting guidance

2. **Spec agent prompts** (`spec/variants/*/generate.prompt.template`):
   - Clarify signature matching requirements
   - Provide examples of good theorem statements
   - Explain when sorry is appropriate

3. **Refine prompts** (both agents):
   - Add error-specific guidance
   - Include common fixes
   - Reference LSP tool usage

### Step 5: A/B Testing (Optional)

**Compare with baseline**:
```bash
# Baseline (main branch)
git checkout main
uv run fvspec --variant control-functional --sample-size 50

# Treatment (phase2 branch)
git checkout q/analyze-deps-2
uv run fvspec --variant control-functional --sample-size 50

# Compare
uv run python src/scripts/compare_baseline_treatment.py \
    artifacts/baseline/ \
    artifacts/treatment/
```

### Step 6: Documentation

Update:
- `benchmark/CLAUDE.md` - New architecture
- `ideas/autoformalization/refactoring_plan.agents.md` - Mark complete
- Add architecture diagram
- Update CLI help text

### Step 7: Commit Phase 5

```bash
git add -A
git commit -m "feat(phase5): validation and optimization complete

Validation results:
- Function discovery: XX% success rate
- Implementation agent: XX% success (zero sorry)
- Spec agent: XX% success (compiles)
- Overall pipeline: XX% both agents succeed

Optimizations:
- Updated prompts for better success rates
- Improved error handling
- Added comprehensive metrics tracking

Phase 2 refactor complete!

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Success Criteria Summary

### Phase 1 ✅
- [x] All 155 tests pass after rename
- [x] No logic changes, pure refactor

### Phase 2 🔄 (50% complete)
- [x] Function discovery integrated in dataset.py
- [ ] Discovery tracked in agent.py
- [ ] Discovery metadata in models.py
- [ ] Templates created for function_under_test
- [ ] Integration tests pass

### Phase 3 ⏳
- [ ] Spec agent generates valid Lean (compiles)
- [ ] 95%+ specs have theorem statements
- [ ] Specs reference impl signatures correctly
- [ ] Specs use sorry for proof obligations

### Phase 4 ⏳
- [ ] Impl agent: 100% zero sorry (fully computable)
- [ ] Spec agent: >90% have sorry (stating theorems)
- [ ] Both agents succeed in 95%+ of samples
- [ ] Orchestration metrics tracked

### Phase 5 ⏳
- [ ] Structural faithfulness improvement vs baseline
- [ ] Implementation correctness validated
- [ ] Spec captures PBT invariants
- [ ] Pipeline latency <30% increase vs baseline

---

## Quick Reference

### File Changes by Phase

**Phase 1 (Complete)**:
- 32 files renamed/updated
- All imports updated
- All tests passing

**Phase 2 (Partial - 1/6 steps)**:
- ✅ `formalize_impl/dataset.py` (done)
- ⏳ `formalize_impl/agent.py` (pending)
- ⏳ `formalize_impl/models.py` (pending)
- ⏳ `impl/common/fragments/function_under_test.prompt` (pending)
- ⏳ `impl/variants/*/translate.prompt.template` (pending)
- ⏳ `tests/test_phase2_integration.py` (pending)

**Phase 3 (0/7 steps)**:
- 4 new Python files (~1000 LOC)
- ~10 new template files (~800 LOC)
- Test file

**Phase 4 (0/5 steps)**:
- `task.py` major rewrite (~300 LOC changed)
- `quality_assessment.py` update (~100 LOC added)
- Artifact structure changes

**Phase 5 (0/7 steps)**:
- Analysis scripts
- Prompt optimizations
- Documentation updates

### Commands

```bash
# Development
uv run pytest src/tests/ -v              # Run all tests
uv run ruff format && uv run ruff check  # Lint/format

# Single sample test
uv run fvspec --variant control-functional --sample-size 1

# Full benchmark
uv run fvspec --variant control-functional --sample-size 50 --parallelism 10

# View results
uv run inspect view --log-dir artifacts

# Analysis
uv run python src/scripts/analyze_phase2_results.py artifacts/{dir}/
```

### Current Branch Status

**Branch**: `q/analyze-deps-2`
**Base**: `main`
**Commits ahead**: 3
- 348852c1: Phase 1 rename
- cbe60a54: Phase 2 partial (dataset integration)
- (current HEAD)

**Ready to continue**: Phase 2 steps 2-6, then Phase 3-5
