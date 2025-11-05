"""Smoke tests for the fvspec generate.

These tests verify that the inspect_ai task loop can run without crashing
due to basic software engineering errors (import issues, type errors, etc).
They use mocked LLM responses to avoid API costs and provide fast feedback.
"""

import tempfile
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessageAssistant

from generate.scaffold.dataset import Datapoint
from generate.scaffold.task import fvspec
from generate.templates.spec import get_variant_prompts


@pytest.fixture
def minimal_test_data():
    """Create a minimal test dataset with 2 samples."""
    return [
        {
            "id": 1,
            "repo_id": 1,
            "name": "test_simple_add",
            "code": "from hypothesis import given\nfrom hypothesis import strategies as st\n@given(x=st.integers(), y=st.integers())\ndef test_simple_add(x: int, y: int):\n    assert x + y == y + x",
            "dep_names": "[]",
            "deps": "[]",
            "source": "/test/test_simple.py",
            "summary": "Test addition commutativity",
            "hash": "abc123",
            "summary_vector": None,
        },
        {
            "id": 2,
            "repo_id": 1,
            "name": "test_list_append",
            "code": "from hypothesis import given\nfrom hypothesis import strategies as st\n@given(lst=st.lists(st.integers()), val=st.integers())\ndef test_list_append(lst: list, val: int):\n    original_len = len(lst)\n    lst.append(val)\n    assert len(lst) == original_len + 1",
            "dep_names": "[]",
            "deps": "[]",
            "source": "/test/test_list.py",
            "summary": "Test list append increases length",
            "hash": "def456",
            "summary_vector": None,
        },
    ]


@pytest.fixture
def temp_data_file(minimal_test_data):
    """Create a temporary SQLite DB file with test data."""
    from sqlmodel import Session, create_engine

    with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    # Create DB and populate with test data
    engine = create_engine(f"sqlite:///{db_path}")
    from generate.scaffold.dataset.models import Datapoint

    Datapoint.metadata.create_all(engine)

    with Session(engine) as session:
        for data in minimal_test_data:
            dp = Datapoint(**data)
            session.add(dp)
        session.commit()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


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
    # Just create the task - don't run it (uses actual temp DB)
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
    functional_system, functional_initial = get_variant_prompts("control-functional")
    assert isinstance(functional_system, str)
    assert len(functional_system) > 0

    # Test mvcgen variant
    mvcgen_system, mvcgen_initial = get_variant_prompts("control-mvcgen")
    assert isinstance(mvcgen_system, str)
    assert len(mvcgen_system) > 0
    assert "mvcgen" in mvcgen_system

    # Test initial prompt rendering with sample data
    initial_prompt = functional_initial.render(
        pbt="def test(): pass", deps=["def helper(): return 42"]
    )
    assert isinstance(initial_prompt, str)
    assert "def test(): pass" in initial_prompt
    assert "def helper(): return 42" in initial_prompt


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
    from generate.scaffold.quality_assessment.models import QualityAssessment

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
                name="test",
                code="def test():\n    pass",
                dep_names="[]",
                deps="[]",
                source="/test.py",
                summary="Test",
                hash="abc",
                summary_vector=None,
            ),
            "date_time": "2025-01-01T00-00-00",
            "variant": "control-functional",
        },
    )

    qa = QualityAssessment.from_task_state(state)

    assert qa.sample_id == 1
    assert qa.sample_name == "test"
    assert qa.faithfulness_subjective == 7.0
    assert qa.interest_subjective == 3.0
    assert qa.success is True
    assert qa.num_sorries == 1
