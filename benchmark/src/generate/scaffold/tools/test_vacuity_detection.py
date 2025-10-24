#!/usr/bin/env python3
"""Simple test script for vacuity detection functionality.

Tests the VacuityMetrics class with example Lean code containing
theorems of varying degrees of vacuity.
"""

from generate.scaffold.quality_assessment import VacuityMetrics


def test_vacuous_theorem():
    """Test theorem that should prove with rfl (very vacuous)."""
    lean_code = """
theorem trivial_equality (x : Int) : x = x := by sorry
"""

    print("Testing vacuous theorem (x = x)...")
    metrics = VacuityMetrics.from_lean_code(lean_code)

    print(f"  Proves with rfl: {metrics.proves_with_rfl}")
    print(f"  Proves with trivial: {metrics.proves_with_trivial}")
    print(f"  Vacuity score: {metrics.vacuity_score}")
    print(f"  Theorems tested: {metrics.num_theorems_tested}")
    print()

    return metrics


def test_non_vacuous_theorem():
    """Test theorem that should not prove with simple tactics."""
    lean_code = """
def fibonacci : ℕ → ℕ
| 0 => 0
| 1 => 1
| n + 2 => fibonacci (n + 1) + fibonacci n

theorem fibonacci_positive (n : ℕ) (h : n > 0) : fibonacci n > 0 := by sorry
"""

    print("Testing non-vacuous theorem (fibonacci n > 0)...")
    metrics = VacuityMetrics.from_lean_code(lean_code)

    print(f"  Proves with rfl: {metrics.proves_with_rfl}")
    print(f"  Proves with trivial: {metrics.proves_with_trivial}")
    print(f"  Proves with simp: {metrics.proves_with_simp}")
    print(f"  Proves with decide: {metrics.proves_with_decide}")
    print(f"  Vacuity score: {metrics.vacuity_score}")
    print(f"  Theorems tested: {metrics.num_theorems_tested}")
    print()

    return metrics


def test_decidable_theorem():
    """Test theorem that might prove with decide."""
    lean_code = """
theorem simple_arithmetic (x : ℕ) (h : x = 5) : x + 2 = 7 := by sorry
"""

    print("Testing decidable theorem (5 + 2 = 7)...")
    metrics = VacuityMetrics.from_lean_code(lean_code)

    print(f"  Proves with rfl: {metrics.proves_with_rfl}")
    print(f"  Proves with trivial: {metrics.proves_with_trivial}")
    print(f"  Proves with simp: {metrics.proves_with_simp}")
    print(f"  Proves with decide: {metrics.proves_with_decide}")
    print(f"  Vacuity score: {metrics.vacuity_score}")
    print(f"  Theorems tested: {metrics.num_theorems_tested}")
    print()

    return metrics


def test_no_theorems():
    """Test code with no theorems."""
    lean_code = """
def add_one (x : ℕ) : ℕ := x + 1

def multiply (x y : ℕ) : ℕ := x * y
"""

    print("Testing code with no theorems...")
    metrics = VacuityMetrics.from_lean_code(lean_code)

    print(f"  Vacuity score: {metrics.vacuity_score}")
    print(f"  Theorems tested: {metrics.num_theorems_tested}")
    print()

    return metrics


def main():
    """Main function check gather vacuous metrics."""
    print("=" * 60)
    print("VACUITY DETECTION TEST")
    print("=" * 60)
    print()

    # Test various theorem types
    test_vacuous_theorem()
    test_non_vacuous_theorem()
    test_decidable_theorem()
    test_no_theorems()

    print("Testing complete!")


if __name__ == "__main__":
    main()
