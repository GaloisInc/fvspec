"""Smoke tests: every core scraper module imports cleanly."""

import importlib

import pytest

CORE_MODULES = ["db", "githubAsync", "license", "main", "migrator", "parse"]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_module_imports(module_name: str) -> None:
    """Importing each core scraper module must not raise."""
    importlib.import_module(module_name)
