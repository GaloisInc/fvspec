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
pretty_name: fvspec-fv
size_categories:
- 1K<n<10K
language:
- en
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
dataset_info:
  features:
  - name: sample_id
    dtype: int64
  - name: code_hash
    dtype: string
  - name: pbt_sample_name
    dtype: string
  - name: pbt_id
    dtype: int64
  - name: run
    dtype: string
  - name: is_canonical
    dtype: bool
  - name: formalization_rank
    dtype: int64
  - name: num_formalizations
    dtype: int64
  - name: pareto_dominated
    dtype: bool
  - name: pbt_code
    dtype: string
  - name: pbt_summary
    dtype: string
  - name: pbt_lines_pbt
    dtype: int64
  - name: pbt_radon
    struct:
    - name: loc
      dtype: int64
    - name: sloc
      dtype: int64
    - name: lloc
      dtype: int64
    - name: comments
      dtype: int64
    - name: blank
      dtype: int64
    - name: multi
      dtype: int64
    - name: single_comments
      dtype: int64
    - name: num_functions
      dtype: int64
    - name: avg_complexity
      dtype: float64
    - name: max_complexity
      dtype: int64
    - name: total_complexity
      dtype: int64
    - name: complexity_rank
      dtype: string
    - name: maintainability_index
      dtype: float64
    - name: maintainability_rank
      dtype: string
    - name: halstead_vocabulary
      dtype: int64
    - name: halstead_length
      dtype: int64
    - name: halstead_volume
      dtype: float64
    - name: halstead_difficulty
      dtype: float64
    - name: halstead_effort
      dtype: float64
    - name: halstead_time
      dtype: float64
    - name: halstead_bugs
      dtype: float64
  - name: language
    dtype: string
  - name: spec
    dtype: string
  - name: impl
    dtype: string
  - name: num_theorems
    dtype: int64
  - name: structural_faithfulness
    struct:
    - name: parameter_coverage
      dtype: float64
    - name: type_correspondence
      dtype: float64
    - name: strategy_coverage
      dtype: float64
    - name: assertion_coverage
      dtype: float64
    - name: dependency_coverage
      dtype: float64
    - name: assertion_theorem_difference
      dtype: int64
    - name: overall
      dtype: float64
  - name: impl_autoform_success
    dtype: float64
  - name: actually_invokes_given
    dtype: bool
  - name: implementation_level
    dtype: string
  - name: num_fns_impl
    dtype: int64
  - name: difficulty_binary
    dtype: string
  - name: difficulty_binary_confidence
    dtype: float64
  - name: difficulty_binary_reasoning
    dtype: string
  - name: dependencies
    list:
    - name: name
      dtype: string
    - name: code
      dtype: string
    - name: language
      dtype: string
    - name: qualified_name
      dtype: string
    - name: source_file
      dtype: string
    - name: depth
      dtype: int64
    - name: kind
      dtype: string
    - name: resolution
      dtype: string
  - name: lean_metrics
    struct:
    - name: spec_structure
      struct:
      - name: total_lines
        dtype: int64
      - name: code_lines
        dtype: int64
      - name: blank_lines
        dtype: int64
      - name: comment_lines
        dtype: int64
      - name: num_axioms
        dtype: int64
      - name: num_defs
        dtype: int64
      - name: num_theorems
        dtype: int64
      - name: num_lemmas
        dtype: int64
      - name: num_structures
        dtype: int64
      - name: num_inductives
        dtype: int64
      - name: num_sorries
        dtype: int64
      - name: num_admits
        dtype: int64
      - name: num_axiomized_defs
        dtype: int64
      - name: num_eval_statements
        dtype: int64
      - name: num_imports
        dtype: int64
      - name: num_namespace_blocks
        dtype: int64
    - name: impl_structure
      struct:
      - name: total_lines
        dtype: int64
      - name: code_lines
        dtype: int64
      - name: blank_lines
        dtype: int64
      - name: comment_lines
        dtype: int64
      - name: num_axioms
        dtype: int64
      - name: num_defs
        dtype: int64
      - name: num_theorems
        dtype: int64
      - name: num_lemmas
        dtype: int64
      - name: num_structures
        dtype: int64
      - name: num_inductives
        dtype: int64
      - name: num_sorries
        dtype: int64
      - name: num_admits
        dtype: int64
      - name: num_axiomized_defs
        dtype: int64
      - name: num_eval_statements
        dtype: int64
      - name: num_imports
        dtype: int64
      - name: num_namespace_blocks
        dtype: int64
    - name: spec_complexity
      struct:
      - name: max_nesting_depth
        dtype: int64
      - name: avg_nesting_depth
        dtype: float64
      - name: max_term_size
        dtype: int64
      - name: avg_term_size
        dtype: float64
      - name: total_proof_tokens
        dtype: int64
      - name: avg_proof_steps
        dtype: float64
      - name: max_proof_steps
        dtype: int64
      - name: num_dependencies
        dtype: int64
      - name: avg_dependencies_per_decl
        dtype: float64
      - name: avg_param_count
        dtype: float64
      - name: max_param_count
        dtype: int64
      - name: halstead_vocabulary
        dtype: int64
      - name: halstead_length
        dtype: int64
      - name: halstead_volume
        dtype: float64
      - name: halstead_difficulty
        dtype: float64
      - name: halstead_effort
        dtype: float64
      - name: halstead_time
        dtype: float64
      - name: halstead_bugs
        dtype: float64
    - name: impl_complexity
      struct:
      - name: max_nesting_depth
        dtype: int64
      - name: avg_nesting_depth
        dtype: float64
      - name: max_term_size
        dtype: int64
      - name: avg_term_size
        dtype: float64
      - name: total_proof_tokens
        dtype: int64
      - name: avg_proof_steps
        dtype: float64
      - name: max_proof_steps
        dtype: int64
      - name: num_dependencies
        dtype: int64
      - name: avg_dependencies_per_decl
        dtype: float64
      - name: avg_param_count
        dtype: float64
      - name: max_param_count
        dtype: int64
      - name: halstead_vocabulary
        dtype: int64
      - name: halstead_length
        dtype: int64
      - name: halstead_volume
        dtype: float64
      - name: halstead_difficulty
        dtype: float64
      - name: halstead_effort
        dtype: float64
      - name: halstead_time
        dtype: float64
      - name: halstead_bugs
        dtype: float64
    - name: total_lean_lines
      dtype: int64
    - name: total_sorries
      dtype: int64
    - name: total_axioms
      dtype: int64
  - name: metrics_metadata
    struct:
    - name: version
      dtype: string
    - name: timestamp
      dtype: string
    - name: computation_time_seconds
      dtype: float64
    - name: spec_available
      dtype: bool
    - name: impl_available
      dtype: bool
  - name: grader_metadata
    struct:
    - name: model
      dtype: string
    - name: timestamp
      dtype: string
    - name: tokens_used
      dtype: int64
    - name: grading_time_seconds
      dtype: float64
    - name: version
      dtype: string
  - name: provenance
    struct:
    - name: git_commit
      dtype: string
    - name: model
      dtype: string
    - name: run_timestamp
      dtype: timestamp[s]
    - name: lean_toolchain
      dtype: string
  - name: time
    dtype: float64
  - name: token_usage
    dtype: int64
  - name: token_usage_breakdown
    list:
    - name: subagent
      dtype: string
    - name: function_name
      dtype: string
    - name: tokens_spent
      dtype: int64
    - name: num_toolcalls
      dtype: int64
  - name: turn_counts
    struct:
    - name: impl
      struct:
      - name: turns
        dtype: int64
      - name: tool_calls
        dtype: int64
    - name: spec
      struct:
      - name: turns
        dtype: int64
      - name: tool_calls
        dtype: int64
    - name: units
      struct:
      - name: turns
        dtype: int64
      - name: tool_calls
        dtype: int64
    - name: total_turns
      dtype: int64
    - name: total_tool_calls
      dtype: int64
  - name: pbt_repo
    struct:
    - name: name
      dtype: string
    - name: url
      dtype: string
    - name: license
      dtype: string
    - name: stars
      dtype: int64
    - name: forks
      dtype: int64
  splits:
  - name: train
    num_examples: 9415
---

# fvspec-fv: Formal Verification Specification Benchmark

**fvspec-fv** is a benchmark of **9,415 Lean 4 formalization challenges** derived from **2,772 unique Python property-based tests** (PBTs). Each sample pairs an `impl` (computable Lean definitions) with a `spec` (theorem statements containing `sorry` placeholders for models to discharge).

Built on [fvspec-pbt](https://huggingface.co/datasets/GaloisInc/fvspec-pbt). Browse the dataset at [fvspec.galois.com](https://fvspec.galois.com).

> **Note:** The source-PBT columns were previously prefixed `realpbt_*`; they are now `pbt_*` (e.g. `realpbt_code` → `pbt_code`), tracking the rename of the upstream dataset to `fvspec-pbt`.

## Dataset Structure

A single split (`train`) of 9,415 rows. Each row represents one **formalization** of a Python PBT into Lean 4. The same PBT may have multiple formalizations from different pipeline runs, each capturing different aspects of the original test.

### Key fields

| Field | Type | Description |
|-------|------|-------------|
| `sample_id` | int | Unique identifier for this formalization |
| `code_hash` | str | SHA-256 of `pbt_code` — groups formalizations of the same PBT |
| `run` | str | Pipeline run identifier (`"feb03"` or `"apr08"`) |
| `is_canonical` | bool | Best formalization in its group by composite quality score |
| `formalization_rank` | int | 1-based rank within group (1 = canonical) |
| `num_formalizations` | int | Total formalizations for this PBT |
| `pareto_dominated` | bool | Whether a strictly better formalization exists on all quality axes |
| `spec` | str | Lean 4 specification — theorem statements with `sorry` |
| `impl` | str | Lean 4 implementation — computable definitions |
| `num_theorems` | int | Number of theorems in `spec` |
| `impl_autoform_success` | float | Implementation completeness: `1.0` fully implemented, `0.5` structured but stubbed (`sorry`), `0.0` failed |
| `implementation_level` | str | `"provided"` (impl bodies generated) or `"signature"` (signatures only) |
| `actually_invokes_given` | bool | Whether the spec actually applies the implementation under test |
| `num_fns_impl` | int | Number of functions defined in `impl` |
| `structural_faithfulness` | struct | How well the Lean spec captures the Python PBT (sub-metrics below) |
| `difficulty_binary` | str | `"easy"` or `"hard"` (Claude Haiku 4.5 assessment) |
| `difficulty_binary_confidence` | float | Confidence of difficulty assessment (0–1) |
| `difficulty_binary_reasoning` | str | Free-text justification for the difficulty label |
| `lean_metrics` | struct | Structural/complexity metrics over the generated Lean (lines, sorries, axioms, Halstead, …) |
| `provenance` | struct | `git_commit`, `model`, `run_timestamp`, `lean_toolchain` |

### Source-PBT fields (`pbt_*`)

Carried over from the [fvspec-pbt](https://huggingface.co/datasets/GaloisInc/fvspec-pbt) row this sample was formalized from:

| Field | Type | Description |
|-------|------|-------------|
| `pbt_id` | int | Foreign key to `id` in fvspec-pbt (may be `null` for the `apr08` run) |
| `pbt_sample_name` | str | Original Python test function name |
| `pbt_code` | str | Original Python PBT source |
| `pbt_summary` | str | Natural-language description of the PBT |
| `pbt_lines_pbt` | int | Line count of the original PBT |
| `pbt_radon` | struct | `radon` complexity profile of the original PBT |
| `pbt_repo` | struct | Origin repository metadata (`name`, `url`, `license`, `stars`, `forks`) |

### `structural_faithfulness` sub-fields

| Sub-metric | Description |
|------------|-------------|
| `parameter_coverage` | Do Lean theorem parameters correspond to Python test parameters? |
| `type_correspondence` | Do Lean types reflect the Python types under test? |
| `strategy_coverage` | Are Hypothesis strategies reflected in Lean constraints? |
| `assertion_coverage` | Are Python assertions captured as Lean theorem statements? |
| `assertion_theorem_difference` | Gap between Python assertions and emitted theorems |
| `dependency_coverage` | Are helper functions and fixtures formalized? |
| `overall` | Composite score |

The full machine-readable schema (including `dependencies`, `metrics_metadata`, `grader_metadata`, `token_usage_breakdown`, and `turn_counts`) is in the `dataset_info` block of this card's metadata.

## Multiple Formalizations

A single Python PBT may have several formalizations from different pipeline runs.

- Some formalizations produce **more theorems** (broader coverage of test behavior)
- Others score higher on **structural faithfulness** (tighter correspondence to the Python source)
- Others capture **more dependencies** (helper functions, fixtures)

Many multi-formalization groups have a Pareto front larger than 1: no single formalization dominates on all quality dimensions. The `pareto_dominated` field marks samples where a strictly better alternative exists across all structural-faithfulness sub-metrics.

### Filtering

```python
from datasets import load_dataset

ds = load_dataset("GaloisInc/fvspec-fv", split="train")

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

- `difficulty_binary`: `"easy"` (3,546 samples) or `"hard"` (5,869 samples)
- `difficulty_binary_confidence`: model confidence (0–1)
- `difficulty_binary_reasoning`: free-text justification

## Provenance

Two pipeline runs contribute to this dataset:

| Run     | Samples | Model             | Date          |
|---------|---------|-------------------|---------------|
| `feb03` | 5,979   | Claude Sonnet     | Feb 2026      |
| `apr08` | 3,436   | Claude Sonnet 4.6 | Mar–Apr 2026  |

The `apr08` run produces higher structural faithfulness on average; `feb03` tends toward higher theorem counts and dependency coverage.

## Citation

If you use fvspec-fv, please cite:

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
