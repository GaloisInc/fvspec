# Benchmark

The benchmark input is the [`GaloisInc/fvspec-pbt`](https://huggingface.co/datasets/GaloisInc/fvspec-pbt) dataset on the Hugging Face Hub — each row is a PBT with embedded dependencies, summary, and metadata. It is pulled automatically at run time (`datasets.load_dataset`); no local file is required. To run against a local JSONL instead, drop it under `data/` and pass its filename via `--datafile` (e.g. `--datafile mydata.jsonl`).

The underlying tests were scraped from permissively-licensed repos on GitHub.

## Generating the benchmark synthetic signatures

```bash
# List available variants
uv run fvspec --list-variants

# Run (uses default variant from config or registry if not specified)
uv run fvspec
uv run fvspec --variant control-functional

# Control dataset sample size (default: 100)
uv run fvspec --sample-size 50
uv run fvspec --sample-size 200

# Control parallelism (default: config.meta.parallelism)
uv run fvspec --parallelism 10
```

## Viewing Results

### Inspect AI Viewer (Recommended)

View evaluation logs with the official inspect_ai viewer:

```bash
# View all results in artifacts directory
uv run inspect view --log-dir artifacts

# View specific run
uv run inspect view --log-dir artifacts/2025-10-14T15-30-00__control-functional
```

The inspect viewer provides:
- Interactive web interface with scores and metrics
- Sample-by-sample inspection
- Filtering and sorting capabilities

### Dashboard (Legacy)

Alternative panel-based dashboard (unmaintained):

```bash
uv run panel serve src/scripts/panel.py
```

With custom arguments:

```bash
uv run panel serve src/scripts/panel.py --args -d "artifacts/2025-10-01T13-26-28" -x "interest" -y "faithfulness"
```

## Prompt Variants

The benchmark supports **prompt variants** for A/B testing different prompting strategies via `FormalizationVariantRegistry`.

### Quick Start

**List available variants:**
```bash
uv run fvspec --list-variants
```

**Run specific variant:**
```bash
uv run fvspec --variant control-functional
```

**Output organization:**
```
artifacts/
  2025-10-14T15-30-00__control-functional/
```

### Architecture

**Directory structure:**
```
src/generate/templates/
  formalize/                 # Unified formalization agent prompts
    common/
      initial.prompt.template   # Default initial prompt
      fragments/                # Reusable system prompt sections
    variants/
      control-functional/    # Only active variant
        system.prompt.template
        metadata.toml
    registry.toml            # Master index
    prompt.py                # Jinja2 loader with {% include %} support
    registry.py              # FormalizationVariantRegistry

  impl/                      # Dependency formalization prompts (not variants)
```

**Registry format** (`templates/formalize/registry.toml`):
```toml
[meta]
default_variant = "control-functional"

[variants.control-functional]
path = "variants/control-functional"
style = "functional"
description = "Default FVAPPS-style functional verification"
tags = ["functional", "stable", "control"]
```

### Creating New Variants

**1. Copy existing variant:**
```bash
cp -r src/generate/templates/formalize/variants/control-functional \
      src/generate/templates/formalize/variants/my-experiment
```

**2. Edit system prompt** (`system.prompt.template`) and update `metadata.toml`.

**3. Register variant** in `src/generate/templates/formalize/registry.toml`:
```toml
[variants.my-experiment]
path = "variants/my-experiment"
style = "functional"
description = "Testing hypothesis X"
tags = ["treatment"]
based_on = "control-functional"
```

**4. Test:**
```bash
uv run fvspec --variant my-experiment
```

### Configuration

Set defaults in `config.toml`:
```toml
[prompt]
variant = "control-functional"

[dataset]
sample_size = 100
```

Priority: CLI args (`--variant`, `--sample-size`) > config.toml > defaults

### Current Variants

- **control-functional**: Full FVAPPS-style instructions, recursion and induction (only active variant)

## Testing

Run smoke tests to verify the pipeline won't crash:

```bash
uv run pytest
```

## Radon Code Metrics

The benchmark automatically logs radon code complexity metrics for each sample. These metrics provide objective measures of code complexity and maintainability for the Python PBTs.

Radon metrics are included in:
- Per-sample wandb logs (`radon__avg_complexity`, `radon__sloc`, etc.)
- `qa.json` files in artifacts directories
- Inspect AI viewer scores

**21 metrics per sample:**
- Raw: LOC, SLOC, LLOC, comments, blank lines
- Complexity: Average/max/total cyclomatic complexity, complexity rank
- Maintainability: Index and rank (0-100, higher is better)
- Halstead: Vocabulary, length, volume, difficulty, effort, time, bugs

## Postproduction Pipeline

After running benchmarks, use postproduction scripts to process and analyze results:

### Merge Runs

Combine multiple benchmark runs into a unified deduplicated JSONL dataset:

```bash
# Edit runs.txt to list run directories
vim src/scripts/postproduction/merge/runs.txt

# Merge with automatic quality-based deduplication
uv run postprod merge src/scripts/postproduction/merge/runs.txt

# Creates: artifacts/dataset-out/fvspec.jsonl
```

See `src/scripts/postproduction/merge/README.md` for details on deduplication algorithm, schema pruning, and workflow integration.

### Grade Difficulty

Use Claude Haiku 4.5 to estimate proof difficulty for merged samples:

```bash
# Grade all samples
uv run postprod grader artifacts/dataset-out/fvspec.jsonl

# Creates: artifacts/dataset-out/fvspec.graded.jsonl

# Retry failed samples
uv run postprod grader artifacts/dataset-out/fvspec.graded.jsonl --retry-failed -o artifacts/dataset-out/fvspec.graded.jsonl
```

See `src/scripts/postproduction/grader/README.md` for cost estimation, retry workflow, and customization.

### Accumulate W&B Runs

Download and analyze W&B runs offline:

```bash
# Configure runs in manifest.toml
vim src/scripts/postproduction/accumulate_wandb/manifest.toml

# Download all runs
uv run python -m scripts.postproduction.accumulate sync

# Launch dashboard
uv run streamlit run src/scripts/postproduction/accumulate_wandb/dashboard.py
```

See `src/scripts/postproduction/accumulate_wandb/README.md` for manifest configuration and dashboard usage.

## Other utilities

Preview prompt templates:

```bash
# Preview prompts (samples from GaloisInc/fvspec-pbt)
uv run preview-prompts --prompt-type formalize
uv run preview-prompts --prompt-type deps

# Control sample size and random seed (defaults from config.toml: sample_size=100, ranseed=0)
uv run preview-prompts --sample-size 10 --ranseed 42
```

Analyze dependencies in scraped tests:

```bash
# Full analysis with sampling
uv run analyze-deps --sample-size 1000 --seed 42

# Stream all datapoints (no sampling)
uv run analyze-deps --no-sample
```

## Verification Style

The active approach is **functional** (FVAPPS style): pure functional programming with recursion and induction (`control-functional` variant). The `mvcgen` imperative approach (Hoare triples, loop invariants) is no longer actively maintained.
