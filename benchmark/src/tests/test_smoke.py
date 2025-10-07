"""Smoke tests for the fvspec benchmark.

These tests verify that the inspect_ai task loop can run without crashing
due to basic software engineering errors (import issues, type errors, etc).
They use mocked LLM responses to avoid API costs and provide fast feedback.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from inspect_ai.model import ChatMessageAssistant
from benchmark.scaffold.task import fvspec
from benchmark.scaffold.dataset import Datapoint

# Configure anyio for async tests
pytestmark = pytest.mark.anyio


@pytest.fixture
def minimal_test_data():
    """Create a minimal test dataset with 2 samples."""
    return [
        {
            "id": 1,
            "repo_id": 1,
            "pbt_name": "test_simple_add",
            "pbt": "from hypothesis import given\nfrom hypothesis import strategies as st\n@given(x=st.integers(), y=st.integers())\ndef test_simple_add(x: int, y: int):\n    assert x + y == y + x",
            "dep_names": [],
            "deps": [],
            "source": "/test/test_simple.py",
            "summary": "Test addition commutativity",
            "hash": "abc123",
            "summary_vector": None,
        },
        {
            "id": 2,
            "repo_id": 1,
            "pbt_name": "test_list_append",
            "pbt": "from hypothesis import given\nfrom hypothesis import strategies as st\n@given(lst=st.lists(st.integers()), val=st.integers())\ndef test_list_append(lst: list, val: int):\n    original_len = len(lst)\n    lst.append(val)\n    assert len(lst) == original_len + 1",
            "dep_names": [],
            "deps": [],
            "source": "/test/test_list.py",
            "summary": "Test list append increases length",
            "hash": "def456",
            "summary_vector": None,
        },
    ]


@pytest.fixture
def temp_data_file(minimal_test_data):
    """Create a temporary JSON file with test data."""
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(minimal_test_data, tmp)
        tmp.flush()
        yield Path(tmp.name)
    # Cleanup
    Path(tmp.name).unlink(missing_ok=True)


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
    with patch("benchmark.scaffold.dataset.sample_datapoints") as mock_sample:
        # Only use 1 sample for speed
        mock_sample.return_value = [
            Datapoint(
                id=1,
                repo_id=1,
                pbt_name="test_simple_add",
                pbt="from hypothesis import given\n@given(x=st.integers())\ndef test(x: int): assert x == x",
                dep_names=[],
                deps=[],
                source="/test.py",
                summary="Test",
                hash="abc",
                summary_vector=None,
            )
        ]

        # Just create the task - don't run it
        task = fvspec(datafile=str(temp_data_file), use_mcp=False)

        # Verify task was created properly
        assert task is not None
        assert task.dataset is not None
        assert len(task.dataset) == 1
        assert task.solver is not None


async def test_smoke_dataset_loading(temp_data_file):
    """Smoke test: Verify dataset loading doesn't crash."""
    from benchmark.scaffold.dataset import load_datapoints

    datapoints = load_datapoints(temp_data_file)

    assert len(datapoints) == 2
    assert all(isinstance(dp, Datapoint) for dp in datapoints)
    assert datapoints[0].id == 1
    assert datapoints[1].pbt_name == "test_list_append"


def test_smoke_prompt_rendering():
    """Smoke test: Verify prompt templates can be rendered."""
    from benchmark.templates.prompt import initial, system

    # Test system prompt
    system_prompt = system.render()
    assert isinstance(system_prompt, str)
    assert len(system_prompt) > 0

    # Test initial prompt with sample data
    initial_prompt = initial.render(
        pbt="def test(): pass", deps=["def helper(): return 42"]
    )
    assert isinstance(initial_prompt, str)
    assert "def test(): pass" in initial_prompt
    assert "def helper(): return 42" in initial_prompt


def test_smoke_tool_registration():
    """Smoke test: Verify lean_compile tool can be created."""
    from benchmark.scaffold.tools.declaration import lean_compile

    tool = lean_compile()
    assert callable(tool)


def test_smoke_quality_assessment_from_mock_state():
    """Smoke test: Verify QA extraction doesn't crash."""
    from benchmark.scaffold.quality_assessment import QualityAssessment
    from inspect_ai.solver import TaskState
    from inspect_ai.model import ChatMessageUser
    from benchmark.scaffold.dataset import Datapoint
    from unittest.mock import Mock

    # Create a minimal mock TaskState
    from inspect_ai.model import ModelName

    mock_output = Mock()
    mock_output.model = "mock/model"
    mock_output.time = 1.5

    state = TaskState(
        model=ModelName("mock/model"),
        sample_id="00001_test",
        epoch=0,
        input="test input",
        messages=[
            ChatMessageUser(content="test", source="input"),
            ChatMessageAssistant(
                content="<code>def test : Nat := sorry</code>\nFaithfulness: 7/10\nInterest: 3/10",
                source="generate",
            ),
        ],
        output=mock_output,
        metadata={
            "datapoint": Datapoint(
                id=1,
                repo_id=1,
                pbt_name="test",
                pbt="def test():\n    pass",
                dep_names=[],
                deps=[],
                source="/test.py",
                summary="Test",
                hash="abc",
                summary_vector=None,
            ),
            "date_time": "2025-01-01T00-00-00",
        },
    )

    qa = QualityAssessment.from_task_state(state)

    assert qa.sample_id == 1
    assert qa.sample_name == "test"
    assert qa.faithfulness_subjective == 7.0
    assert qa.interest_subjective == 3.0
    assert qa.success is True
    assert qa.num_sorries == 1
