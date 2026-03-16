"""Smoke tests for the fvspec generate.

These tests verify that the inspect_ai task loop can run without crashing
due to basic software engineering errors (import issues, type errors, etc).
They use mocked LLM responses to avoid API costs and provide fast feedback.
"""

import json
import tempfile
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessageAssistant

from generate.scaffold.dataset import Datapoint
from generate.scaffold.orchestration import fvspec
from generate.templates.formalize import get_formalization_prompts


def _make_datapoint(**overrides):
    """Create a Datapoint with sensible defaults."""
    defaults = {
        "id": 1,
        "name": "test_simple_add",
        "code": "from hypothesis import given\nfrom hypothesis import strategies as st\n@given(x=st.integers(), y=st.integers())\ndef test_simple_add(x: int, y: int):\n    assert x + y == y + x",
        "language": "python",
        "source_file": "/test/test_simple.py",
        "summary": "Test addition commutativity",
        "repo": {
            "name": "test-repo",
            "url": "https://github.com/test/repo",
            "license": "MIT",
            "stars": 10,
            "forks": 2,
        },
        "metrics": {
            "loc": 5,
            "sloc": 4,
            "lloc": 3,
            "comments": 0,
            "avg_complexity": 1.0,
            "max_complexity": 1,
            "maintainability_index": 80.0,
            "halstead_difficulty": 2.0,
            "halstead_effort": 10.0,
        },
        "dependencies": [],
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def minimal_test_data():
    """Create a minimal test dataset with 2 samples."""
    return [
        _make_datapoint(id=1, name="test_simple_add"),
        _make_datapoint(
            id=2,
            name="test_list_append",
            code="from hypothesis import given\nfrom hypothesis import strategies as st\n@given(lst=st.lists(st.integers()), val=st.integers())\ndef test_list_append(lst: list, val: int):\n    original_len = len(lst)\n    lst.append(val)\n    assert len(lst) == original_len + 1",
            source_file="/test/test_list.py",
            summary="Test list append increases length",
        ),
    ]


@pytest.fixture
def temp_data_file(minimal_test_data):
    """Create a temporary JSONL file with test data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        for record in minimal_test_data:
            tmp.write(json.dumps(record) + "\n")
        data_path = Path(tmp.name)

    yield data_path

    # Cleanup
    data_path.unlink(missing_ok=True)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response with valid Lean code."""
    return """<code>
-- Simple addition property
def add (x y : Int) : Int := sorry

theorem test_simple_add (x y : Int) : add x y = add y x := by
  sorry
</code>

Faithfulness: 8/10
Interest: 5/10
"""


async def test_smoke_task_creation(temp_data_file):
    """Smoke test: Verify task creation doesn't crash.

    This test verifies:
    - Task creation doesn't crash
    - Dataset loading works
    - Prompt rendering works
    - Tool registration works
    - No import errors, type errors, or missing dependencies
    """
    # Just create the task - don't run it (uses actual temp JSONL)
    task = fvspec(datafile=str(temp_data_file), sample_size=1)

    # Verify task was created properly
    assert task is not None
    assert task.dataset is not None
    assert len(task.dataset) >= 1
    assert task.solver is not None


async def test_smoke_dataset_loading(temp_data_file):
    """Smoke test: Verify dataset loading doesn't crash."""
    from generate.scaffold.dataset import load_datapoints_by_id

    datapoints = load_datapoints_by_id(temp_data_file, [1, 2])

    assert len(datapoints) == 2
    assert all(isinstance(dp, Datapoint) for dp in datapoints.values())
    assert datapoints[1].id == 1
    assert datapoints[2].name == "test_list_append"


def _trio_supported() -> bool:
    """Check whether the environment permits Trio's wakeup socket tweaks."""
    try:
        import socket

        s1, s2 = socket.socketpair()
        try:
            s1.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1)
        except PermissionError:
            return False
        finally:
            s1.close()
            s2.close()
    except OSError:
        return False
    return True


TRIO_SUPPORTED = _trio_supported()

if TRIO_SUPPORTED:
    pytestmark = pytest.mark.anyio
else:
    pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture(params=["asyncio", "trio"] if TRIO_SUPPORTED else ["asyncio"])
def anyio_backend(request):
    """Return the requested AnyIO backend, skipping trio when unsupported."""
    backend = request.param
    if backend == "trio" and not TRIO_SUPPORTED:
        pytest.skip("Trio backend requires socket permissions")
    return backend


def test_smoke_prompt_rendering():
    """Smoke test: Verify prompt templates can be rendered."""
    # Test functional variant
    functional_system, functional_initial = get_formalization_prompts(
        "control-functional"
    )
    assert isinstance(functional_system, str)
    assert len(functional_system) > 0

    # Test initial prompt rendering with sample data
    initial_prompt = functional_initial.render(
        pbt_code="def test(): pass",
        function_name="add",
        function_code="def add(x, y): return x + y",
        pbt_summary="Test addition",
        dependencies={},
    )
    assert isinstance(initial_prompt, str)
    assert "def test(): pass" in initial_prompt
    assert "def add(x, y): return x + y" in initial_prompt


def test_smoke_tool_registration():
    """Smoke test: Verify MCP tools can be created."""
    from generate.scaffold.tools.declaration import lean_diagnostic_messages, lean_goal

    # MCP tools for interactive agent use
    diag_tool = lean_diagnostic_messages()
    goal_tool = lean_goal()
    assert callable(diag_tool)
    assert callable(goal_tool)


def test_smoke_quality_assessment_from_mock_state():
    """Smoke test: Verify QA extraction doesn't crash."""
    from unittest.mock import Mock

    # Create a minimal mock TaskState
    from inspect_ai.model import ChatMessageUser, ModelName
    from inspect_ai.solver import TaskState

    from generate.scaffold.dataset import Datapoint
    from generate.scaffold.quality_assessment import QualityAssessment

    mock_output = Mock()
    mock_output.model = "mock/model"
    mock_output.time = 1.5

    lean_code = "def test : Nat := sorry"

    state = TaskState(
        model=ModelName("mock/model"),
        sample_id="00001_test",
        epoch=0,
        input="test input",
        messages=[
            ChatMessageUser(content="test", source="input"),
            ChatMessageAssistant(
                content=f"<code>{lean_code}</code>\nFaithfulness: 7/10\nInterest: 3/10",
                source="generate",
            ),
        ],
        output=mock_output,
        metadata={
            "datapoint": Datapoint(
                id=1,
                name="test",
                code="def test():\n    pass",
                summary="Test",
            ),
            "date_time": "2025-01-01T00-00-00",
            "variant": "control-functional",
        },
    )

    # Set spec_result in store (QA requires validated compilation, no legacy fallback)
    state.store.set(
        "spec_result",
        {
            "success": True,
            "lean_code": lean_code,
            "compiles": True,
            "has_statements": True,
        },
    )

    qa = QualityAssessment.from_task_state(state)

    assert qa.sample_id == 1
    assert qa.sample_name == "test"
    assert qa.faithfulness_subjective == 7.0
    assert qa.interest_subjective == 3.0
    assert qa.success is True
    assert qa.num_sorries == 1
