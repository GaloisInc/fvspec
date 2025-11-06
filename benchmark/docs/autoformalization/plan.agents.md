# TODOs

## Synthesizing `Testable` instances for existentials

The core issues are:

1. Vacuous existence theorems (test_acos): When Python tests have no meaningful property (just "does it
run?"), spec agent hallucinates trivial existence statements like "function returns something"
2. Plausible incompatibility: Even legitimate existence theorems cannot be tested by plausible because it
cannot synthesize Testable instances for statements like ∀ x, ∃ y, P(x, y)

What Python constructs legitimately map to existence statements:
- Exception assertions: with self.assertRaises(...) → ∃ msg, f(...) = error msg ✅
- Divisibility/factorization properties: a % b == 0 implies divisibility → ∃ k, a = k * b ✅
- "Well-defined" claims for partial functions → ∃ result, f(x) = result ❌ (vacuous for total functions)

The test_acos case suggests we need to either:
- Guide the spec agent away from vacuous existence theorems
- Detect when Python tests have no meaningful property to formalize
- Accept that some samples cannot produce interesting specifications
