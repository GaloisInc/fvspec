---
license:
- mit
- apache-2.0
task_categories:
- text-generation
tags:
- code
- python
- property-based-testing
- hypothesis
- software-testing
pretty_name: fvspec-pbt
size_categories:
- 10K<n<100K
language:
- en
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
dataset_info:
  features:
  - name: id
    dtype: int64
  - name: name
    dtype: string
  - name: code
    dtype: string
  - name: language
    dtype: string
  - name: source_file
    dtype: string
  - name: start_line
    dtype: int64
  - name: end_line
    dtype: int64
  - name: repo
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
  - name: metrics
    struct:
    - name: loc
      dtype: int64
    - name: sloc
      dtype: int64
    - name: lloc
      dtype: int64
    - name: comments
      dtype: int64
    - name: avg_complexity
      dtype: float64
    - name: max_complexity
      dtype: int64
    - name: maintainability_index
      dtype: float64
    - name: halstead_difficulty
      dtype: float64
    - name: halstead_effort
      dtype: float64
  - name: summary
    dtype: string
  - name: dependencies
    list:
    - name: name
      dtype: string
    - name: qualified_name
      dtype: string
    - name: code
      dtype: string
    - name: language
      dtype: string
    - name: source_file
      dtype: string
    - name: depth
      dtype: int64
    - name: kind
      dtype: string
    - name: resolution
      dtype: string
  splits:
  - name: train
    num_examples: 21746
---

# fvspec-pbt: Real-World Property-Based Tests

**fvspec-pbt** is a corpus of **21,746 real-world Python property-based tests** (PBTs) mined from **645 open-source repositories**. Each row is a single test paired with its resolved dependency closure, a static complexity profile, and (for a graded subset) a natural-language summary of the property under test.

This is the **source dataset** for [fvspec-fv](https://huggingface.co/datasets/GaloisInc/fvspec-fv): every fvspec-fv Lean 4 formalization is derived from one of these PBTs. Use fvspec-pbt directly to study real-world testing practice, or as input to your own formalization / test-generation pipelines. Browse the downstream benchmark at [fvspec.galois.com](https://fvspec.galois.com).

> **Note:** This dataset was previously named *RealPBT*. The name and the `realpbt_*` column prefix used downstream have been retired in favour of `fvspec-pbt` / `pbt_*`.

## Why real-world tests?

Synthetic coding puzzles leak into model training data. fvspec-pbt is harvested from production test suites — Hypothesis strategies, `pytest` fixtures, and assertion-style invariants written by real engineers — to provide a contamination-resistant basis for evaluating program understanding and specification.

## Dataset Structure

A single split (`train`) of 21,746 rows. Each row represents one Python test function together with the code it depends on.

### Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique identifier for the test |
| `name` | str | Test function name (e.g. `test_add_padding`) |
| `code` | str | Full source of the test function |
| `language` | str | Always `"python"` |
| `source_file` | str | Path to the test within its origin repository |
| `start_line` / `end_line` | int | Location of the test in `source_file` |
| `summary` | str \| null | Natural-language description of the property under test (present for a 7,627-test subset; `null` otherwise) |
| `repo` | struct | Origin repository metadata (see below) |
| `metrics` | struct | Static complexity profile of the test (see below) |
| `dependencies` | list[struct] | Resolved dependency closure — helpers, fixtures, classes, and assignments the test transitively references |

### `repo` sub-fields

| Field | Description |
|-------|-------------|
| `name` | `owner/repo` slug |
| `url` | Clone URL |
| `license` | SPDX identifier, or `NOASSERTION` when undeclared |
| `stars` / `forks` | GitHub popularity signals at harvest time |

### `metrics` sub-fields

Static metrics computed over the test source (via [`radon`](https://radon.readthedocs.io/)):

| Field | Description |
|-------|-------------|
| `loc` / `sloc` / `lloc` | Lines / source lines / logical lines of code |
| `comments` | Comment line count |
| `avg_complexity` / `max_complexity` | Cyclomatic complexity (mean and max over blocks) |
| `maintainability_index` | Maintainability index (0–100) |
| `halstead_difficulty` / `halstead_effort` | Halstead complexity measures |

### `dependencies` sub-fields

Each dependency is the code a test transitively references, resolved across the repository:

| Field | Description |
|-------|-------------|
| `name` / `qualified_name` | Identifier and its fully-qualified form |
| `code` | Source of the dependency |
| `kind` | `function`, `method`, `class`, `assignment`, or `null` |
| `source_file` | Where the dependency is defined |
| `language` | Always `"python"` |
| `depth` / `resolution` | Provenance of the dependency resolution (may be `null`) |

## Composition

- **21,746 tests** across **645 repositories**
- **20,781 tests (96%)** carry at least one resolved dependency; mean 15.4 dependencies per test (max 618)
- **7,627 tests (35%)** have a natural-language `summary`; the rest are `null`
- Dependency kinds: ~100K functions, ~52K assignments, ~25K classes, ~15K methods

License mix across origin repositories (most common):

| License | Tests |
|---------|-------|
| NOASSERTION | 16,423 |
| MIT | 3,109 |
| Apache-2.0 | 1,029 |
| BSD-3-Clause | 959 |
| Other (ISC, Unlicense, CC0, BSD-2-Clause, …) | rest |

`NOASSERTION` marks repositories that did not declare a machine-readable license; consult the upstream repo (`repo.url`) before redistributing individual tests.

## Loading

```python
from datasets import load_dataset

ds = load_dataset("GaloisInc/fvspec-pbt", split="train")

# Tests with a natural-language summary
summarized = ds.filter(lambda x: x["summary"] is not None)

# Self-contained tests (no external dependency closure)
standalone = ds.filter(lambda x: len(x["dependencies"]) == 0)

# Tests from permissively-licensed repositories
permissive = ds.filter(lambda x: x["repo"]["license"] in {"MIT", "Apache-2.0", "BSD-3-Clause"})
```

## Relationship to fvspec-fv

fvspec-pbt is the upstream input to the fvspec-fv formalization pipeline:

```
fvspec-pbt (this dataset)  →  unified formalization agent  →  fvspec-fv (Lean 4 Impl + Spec)
```

An fvspec-fv sample's `pbt_code` and `pbt_summary` fields trace back to a row's `code` and `summary` here, and its `pbt_id` field is the foreign key to this dataset's `id`. Join on `pbt_id` to study how a given Python property maps onto its Lean formalization(s).

## Citation

If you use fvspec-pbt, please cite:

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

This compilation is made available under both an MIT license and an Apache 2.0 license. Individual tests retain the license of their origin repository (`repo.license`); review upstream terms before redistributing test contents.
