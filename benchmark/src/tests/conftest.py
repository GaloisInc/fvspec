"""Pytest configuration and fixtures for the benchmark test suite."""

import os
import pytest


@pytest.fixture(autouse=True)
def disable_wandb():
    """Disable wandb for all tests to prevent clutter in artifacts and wandb logs.

    This fixture runs automatically for every test (autouse=True) and:
    - Sets WANDB_MODE=disabled to prevent wandb from logging
    - Ensures no wandb runs are created during testing
    - Keeps artifacts/ directory clean during test runs

    The fixture is session-scoped to apply once for the entire test session.
    """
    # Save original value if it exists
    original_mode = os.environ.get("WANDB_MODE")

    # Disable wandb
    os.environ["WANDB_MODE"] = "disabled"

    yield

    # Restore original value
    if original_mode is not None:
        os.environ["WANDB_MODE"] = original_mode
    else:
        os.environ.pop("WANDB_MODE", None)
