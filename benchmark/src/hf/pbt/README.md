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
pretty_name: RealPBT
size_categories:
- 10K<n<100K
language:
- en
---

# RealPBT: Real-World Property-Based Tests

RealPBT is a corpus of **21,746 real-world Python property-based tests** (PBTs) mined from **645 open-source repositories**. Each row is a single test paired with its resolved dependency closure, a complexity profile, and (for a graded subset) a natural-language summary of the property under test.

This is the **source dataset** for [FVSpec](https://huggingface.co/datasets/galoisinc/fvspec-fv): every FVSpec Lean 4 formalization is derived from one of these PBTs. Use RealPBT directly to study real-world testing practice, or as input to your own formalization / test-generation pipelines. Browse the downstream benchmark at [fvspec.galois.com](https://fvspec.galois.com).

## Why real-world tests?

Synthetic coding puzzles leak into model training data. RealPBT is harvested from production test suites — Hypothesis strategies, `pytest` fixtures, and assertion-style invariants written by real engineers — to provide a contamination-resistant basis for evaluating program understanding and specification.

## Dataset Structure

Each row represents one Python test function together with the code it depends on.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique identifier for the test |
| `name` | str | Test function name (e.g. `test_add_padding`) |
| `code` | str | Full source of the test function |
| `language` | str | Always `"python"` |
| `source_file` | str | Path to the test within its origin repository |
| `start_line` / `end_line` | int | Location of the test in `source_file` |
| `summary` | str \| null | Natural-language description of the property under test (present for a 7,627-test subset; `null` otherwise) |
| `repo` | dict | Origin repository metadata (see below) |
| `metrics` | dict | Static complexity profile of the test (see below) |
| `dependencies` | list[dict] | Resolved dependency closure — helpers, fixtures, classes, and assignments the test transitively references |

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

ds = load_dataset("galoisinc/fvspec-pbt", split="train")

# Tests with a natural-language summary
summarized = ds.filter(lambda x: x["summary"] is not None)

# Self-contained tests (no external dependency closure)
standalone = ds.filter(lambda x: len(x["dependencies"]) == 0)

# Tests from permissively-licensed repositories
permissive = ds.filter(lambda x: x["repo"]["license"] in {"MIT", "Apache-2.0", "BSD-3-Clause"})
```

## Relationship to FVSpec

RealPBT is the upstream input to the FVSpec formalization pipeline:

```
RealPBT (this dataset)  →  unified formalization agent  →  FVSpec (Lean 4 Impl + Spec)
```

A FVSpec sample's `realpbt_code` and `realpbt_summary` fields trace back to a row's `code` and `summary` here. Join on the test source to study how a given Python property maps onto its Lean formalization(s).

## Citation

If you use RealPBT, please cite:

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
