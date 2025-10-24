#!/usr/bin/env python3
"""
Test simple regex patterns step by step.
"""

import re


def test_basic_theorem_match():
    lean_code = "theorem trivial_equality (x : Int) : x = x := by sorry"

    print(f"Input: {lean_code}")
    print()

    # Test basic theorem keyword match
    basic_pattern = r"theorem\s+(\w+)"
    matches = re.findall(basic_pattern, lean_code)
    print(f"Basic theorem pattern: {matches}")

    # Test theorem with params
    param_pattern = r"theorem\s+(\w+)\s*\([^)]*\)"
    matches = re.findall(param_pattern, lean_code)
    print(f"Theorem with params: {matches}")

    # Test finding the colon and conclusion
    full_pattern = r"theorem\s+(\w+)\s*([^:]*?)\s*:\s*([^:]*?)(?=\s*:=)"
    matches = re.findall(full_pattern, lean_code)
    print(f"Full pattern (before :=): {matches}")

    # Even simpler: everything up to :=
    simple_pattern = r"(theorem\s+\w+[^:]*?:[^:]*?)(?=\s*:=)"
    matches = re.findall(simple_pattern, lean_code)
    print(f"Simple capture everything: {matches}")


if __name__ == "__main__":
    test_basic_theorem_match()
