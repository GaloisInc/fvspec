# Benchmark

**You need to [download `pbts_full.db`](https://www.dropbox.com/scl/fi/n8245no2aao5rjkk46bw7/pbts_full.db?rlkey=teccs61td980bmdsvr5empcib&e=1&st=ec2beuz2&dl=0) and put it in `./benchmark/data/`**

This data was scraped by Benchify (www.benchify.com) from permissively-licensed repos on Github. For more information about the data please contact max@benchify.com or maxvh@hey.com.

## Database Overview

The benchmark uses a **SQLite database** (`pbts_full.db`) with SQLModel ORM for type-safe, efficient access to property-based tests.

**Statistics**:
- 54,345 property-based tests (PBTs)
- 6,343,790 unit tests
- 448,160 PBT-function associations

**Key Features**:
- ✅ Fast SQL queries with filtering (no indexing needed)
- ✅ Type-safe access via SQLModel ORM
- ✅ Efficient sampling with dependency filtering
- ✅ Unit test overlaps stored in normalized tables

**Database Schema**:
- `unit_tests` - Unit tests with metadata (id, repo_id, name, code, etc.)
- `pbt_functions` - Property-based tests (PBTs) with metadata (id, repo_id, name, code, deps, etc.)
- `unit_test_functions` - Associations between PBTs and unit tests (many-to-many relationship)
- `functions` - Functions under test (id, name, etc.)
- JSON fields (`deps`, `dep_names`) stored as TEXT, parsed via `.get_deps()` / `.get_dep_names()`

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

### Automatic Integration

Radon metrics are **automatically queried and logged** during benchmark runs if the `radon_metrics` table exists in the database. The metrics are included in:
- Per-sample wandb logs (`radon__avg_complexity`, `radon__sloc`, etc.)
- `qa.json` files in artifacts directories
- Inspect AI viewer scores

**21 metrics per sample:**
- Raw: LOC, SLOC, LLOC, comments, blank lines
- Complexity: Average/max/total cyclomatic complexity, complexity rank
- Maintainability: Index and rank (0-100, higher is better)
- Halstead: Vocabulary, length, volume, difficulty, effort, time, bugs

### Setup (One-Time)

If radon metrics aren't in the database yet, compute and import them once:

```bash
# Compute metrics for all PBTs in the database
uv run compute-radon-metrics compute

# Import into database (creates radon_metrics table)
uv run import-radon-metrics import-metrics artifacts/radon_metrics/<timestamp>_metrics.json

# Verify import
uv run import-radon-metrics verify
```

After this one-time setup, **all future benchmark runs will automatically include radon metrics**.

### Viewing Radon Metrics

**In wandb:**
- Per-sample metrics logged at each step: `radon__avg_complexity`, `radon__maintainability_index`, etc.
- Filter by "radon__" prefix to see all metrics
- Compare across runs and variants

**In Inspect AI viewer:**
```bash
uv run inspect view --log-dir artifacts
# Browse samples to see radon metrics in the scores table
```

**In qa.json files:**
```bash
cat artifacts/<run>/12345_test_foo/qa.json | jq '.radon__avg_complexity'
```

### Note on Backfilling

Due to wandb API limitations, you **cannot retroactively add metrics to finished runs**. To get radon metrics for existing variants, re-run the benchmarks after setting up the radon_metrics table.

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
# Preview prompts (samples from database)
uv run preview-prompts data/pbts_full.db --prompt-type formalize
uv run preview-prompts data/pbts_full.db --prompt-type deps

# Control sample size and random seed (defaults from config.toml: sample_size=100, ranseed=0)
uv run preview-prompts data/pbts_full.db --sample-size 10 --ranseed 42
```

Analyze dependencies in scraped tests:

```bash
# Full analysis with sampling
uv run analyze-deps --sample-size 1000 --seed 42

# Stream all datapoints (no sampling)
uv run analyze-deps --no-sample

# Use specific database path
uv run analyze-deps --dataset-path data/pbts_full.db
```

Interactive data exploration:

```bash
# Launch Streamlit data explorer
uv run data-explorer

# Features: search by ID, random sampling, filters, bookmarks, history
```

## Verification Style

The active approach is **functional** (FVAPPS style): pure functional programming with recursion and induction (`control-functional` variant). The `mvcgen` imperative approach (Hoare triples, loop invariants) is no longer actively maintained.
