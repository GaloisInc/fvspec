---
license:
- mit
- apache-2.0
task_categories:
- text-generation
tags:
- code
- lean4
- formal-verification
- property-based-testing
- benchmark
pretty_name: FVSpec
size_categories:
- 1K<n<10K
language:
- en
---

# FVSpec: Formal Verification Specification Benchmark

FVSpec is a benchmark of **9,415 Lean 4 formalization challenges** derived from **2,772 unique Python property-based tests** (PBTs). Each sample pairs an `Impl.lean` (computable definitions) with a `Spec.lean` (theorem statements containing `sorry` placeholders for models to discharge).

Built on [RealPBT](https://huggingface.co/datasets/galoisinc/fvspec-pbt). Browse the dataset at [fvspec.galois.com](https://fvspec.galois.com).

## Dataset Structure

Each row represents one **formalization** of a Python PBT into Lean 4. The same PBT may have multiple formalizations from different pipeline runs, each capturing different aspects of the original test.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `sample_id` | int | Unique identifier for this formalization |
| `code_hash` | str | SHA-256 of `realpbt_code` — groups formalizations of the same PBT |
| `is_canonical` | bool | Best formalization in its group by composite quality score |
| `formalization_rank` | int | 1-based rank within group (1 = canonical) |
| `num_formalizations` | int | Total formalizations for this PBT |
| `pareto_dominated` | bool | Whether a strictly better formalization exists on all quality axes |
| `spec` | str | Lean 4 specification — theorem statements with `sorry` |
| `impl` | str | Lean 4 implementation — computable definitions |
| `realpbt_code` | str | Original Python PBT source |
| `realpbt_summary` | str | Natural language description of the PBT |
| `num_theorems` | int | Number of theorems in `spec` |
| `structural_faithfulness` | dict | How well the Lean spec captures the Python PBT (sub-metrics below) |
| `difficulty_binary` | str | "easy" or "hard" (Claude Haiku 4.5 assessment) |
| `difficulty_binary_confidence` | float | Confidence of difficulty assessment (0-1) |
| `run` | str | Pipeline run identifier ("feb03" or "apr08") |

### Structural Faithfulness Sub-metrics

| Sub-metric | Description |
|------------|-------------|
| `parameter_coverage` | Do Lean theorem parameters correspond to Python test parameters? |
| `type_correspondence` | Do Lean types reflect the Python types under test? |
| `strategy_coverage` | Are Hypothesis strategies reflected in Lean constraints? |
| `assertion_coverage` | Are Python assertions captured as Lean theorem statements? |
| `dependency_coverage` | Are helper functions and fixtures formalized? |
| `overall` | Composite score |

## Multiple Formalizations

A single Python PBT may have 2--15 formalizations from different pipeline runs. 

- Some formalizations produce **more theorems** (broader coverage of test behavior)
- Others score higher on **structural faithfulness** (tighter correspondence to the Python source)
- Others capture **more dependencies** (helper functions, fixtures)

**65% of multi-formalization groups have a Pareto front larger than 1**: no single formalization dominates on all quality dimensions. The `pareto_dominated` field marks samples where a strictly better alternative exists across all structural faithfulness sub-metrics.

### Filtering

```python
from datasets import load_dataset

ds = load_dataset("galoisinc/fvspec-fv", split="train")

# One-per-PBT (2,772 canonical samples)
canonical = ds.filter(lambda x: x["is_canonical"])

# All non-dominated formalizations
non_dominated = ds.filter(lambda x: not x["pareto_dominated"])

# Group by PBT for formalization comparison
from collections import defaultdict
groups = defaultdict(list)
for sample in ds:
    groups[sample["code_hash"]].append(sample)
```

## Compilation Guarantee

Every sample in this dataset compiles successfully with `lake build` against the Lean toolchain and Mathlib version specified in `provenance.lean_toolchain`. To compile a sample locally:

1. Set up a Lean 4 project with the matching toolchain and Mathlib dependency
2. Write `impl` to `Fvspec/Impl.lean` and `spec` to `Fvspec/Spec.lean`
3. Run `lake build`

## Difficulty Grading

Each sample is graded for proof difficulty by Claude Haiku 4.5:

- `difficulty_binary`: "easy" or "hard"
- `difficulty_binary_confidence`: model confidence (0--1)
- `difficulty_binary_reasoning`: free-text justification

## Provenance

Two pipeline runs contribute to this dataset:

| Run     | Samples | Model             | Date          |
|---------|---------|-------------------|---------------|
| `feb03` | 5,979   | Claude Sonnet     | Feb 2026      |
| `apr08` | 3,436   | Claude Sonnet 4.6 | Mar--Apr 2026 |

The `apr08` run produces higher structural faithfulness on average; `feb03` tends toward higher theorem counts and dependency coverage.

## Citation

If you use FVSpec, please cite:

```bibtex
@misc{fvspec2026,
  title={Real-World PBTs as Lean Specs},
  author={Dougherty, Quinn and Shackleton, Hazel and von Hippel, Max and Dodds, Mike},
  year={2026},
  url={https://fvspec.galois.com}
}
```

## Acknowledgements

This project is funded by the [Advanced Research + Invention Agency (ARIA)](https://www.aria.org.uk/).

## License

This work is made available under both an MIT license and an Apache 2.0 license such that users can decide which to utilize.
