#!/usr/bin/env python3
"""Test only the theorem extraction without Lean compilation."""

from generate.scaffold.quality_assessment import _extract_theorem_statements


def test_theorem_extraction():
    """Tests some simple theorem extractions."""
    print("=" * 60)
    print("THEOREM EXTRACTION TEST")
    print("=" * 60)
    print()

    test_cases = [
        ("Simple theorem", "theorem trivial_equality (x : Int) : x = x := by sorry"),
        (
            "Multiline theorem",
            """
theorem fibonacci_positive (n : ℕ)
    (h : n > 0) :
    fibonacci n > 0 := by sorry
""",
        ),
        (
            "Theorem with def",
            """
def fibonacci : ℕ → ℕ
| 0 => 0
| 1 => 1
| n + 2 => fibonacci (n + 1) + fibonacci n

theorem fibonacci_positive (n : ℕ) (h : n > 0) : fibonacci n > 0 := by sorry
""",
        ),
        (
            "Multiple theorems",
            """
theorem first (x : ℕ) : x = x := by rfl

theorem second (x y : ℕ) (h : x > 0) : x + y ≥ x := by
  sorry

lemma helper : True := by trivial
""",
        ),
        (
            "No theorems",
            """
def add_one (x : ℕ) : ℕ := x + 1
def multiply (x y : ℕ) : ℕ := x * y
""",
        ),
    ]

    for name, lean_code in test_cases:
        print(f"Testing: {name}")
        print(f"Input:")
        print(lean_code)
        print()

        theorems = _extract_theorem_statements(lean_code)
        print(f"Extracted {len(theorems)} theorem(s):")
        for i, theorem in enumerate(theorems, 1):
            print(f"  {i}. {theorem}")
        print()
        print("-" * 40)
        print()


if __name__ == "__main__":
    "Main function to call the test theorem extractions."
    test_theorem_extraction()
