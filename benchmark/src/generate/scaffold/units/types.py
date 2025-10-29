"""Pydantic models for unit test extraction and generation."""

from typing import Literal
from pydantic import BaseModel, Field


class TestCase(BaseModel, frozen=True):
    """A single unit test case extracted from a PBT.

    Attributes:
        func_name: Name of the function being tested
        inputs: List of input arguments in Lean syntax (e.g., ["[1, 2, 3]", "5"])
        expected_output: Expected output in Lean syntax (e.g., "[2, 4, 6]")
        is_float: Whether this test involves floating-point values requiring tolerance
        rtol: Relative tolerance for float comparison (numpy.isclose semantics)
        atol: Absolute tolerance for float comparison
        test_name: Descriptive name for the test
        extraction_method: How this test was extracted (currently only "ast")
    """

    func_name: str
    inputs: list[str]
    expected_output: str
    is_float: bool = False
    rtol: float = Field(default=1e-5)
    atol: float = Field(default=1e-8)
    test_name: str
    extraction_method: Literal["ast"] = "ast"


class TestSuite(BaseModel, frozen=True):
    """A collection of unit tests for a single function.

    Attributes:
        exact_tests: Tests with exact equality (use LSpec)
        float_tests: Tests with approximate equality (use external validation)
        extraction_stats: Metadata about the extraction process
    """

    exact_tests: list[TestCase]
    float_tests: list[TestCase]
    extraction_stats: dict[str, int | str]
