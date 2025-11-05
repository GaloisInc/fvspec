# Benchmark

**You need `pbts_full.db` from MaxVH and put it in `./benchmark/data/`**

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

# Run single variant (uses default from config or registry if not specified)
uv run fvspec
uv run fvspec --variant control-functional

# Run with treatment variant
uv run fvspec --variant terse-functional

# Run with control mvcgen variant
uv run fvspec --variant control-mvcgen

# Control dataset sample size (default: 100)
uv run fvspec --sample-size 50
uv run fvspec --sample-size 200

# A/B testing: compare multiple variants in parallel
uv run fvspec compare-variants
uv run fvspec compare-variants --variant control-functional --variant terse-functional

# Combine options
uv run fvspec --variant terse-functional --sample-size 50
uv run fvspec compare-variants --sample-size 200

# Control parallelism (default: config.meta.parallelism)
uv run fvspec --parallelism 10
uv run fvspec compare-variants --parallelism 32
```

## Dependency Utilities

Sometimes you only need the dependency modules, not the full benchmark loop. The `deps` subcommands handle that:

```bash
# Autoformalize dependencies for specific datapoint ids
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47

# Sample N datapoints (default 1) and generate stubs/cached Lean modules
uv run fvspec deps autoformalize --sample-size 10 -s 42

# Force regenerate dependencies (ignores cache, overwrites on collision)
uv run fvspec --force-cache-regen --sample-size 10
uv run fvspec deps autoformalize --force-cache-regen --sample-id 42

# Cache management
uv run fvspec deps cache-clear-local     # Clear local dependency cache
uv run fvspec deps cache-clear-wandb     # Delete remote wandb cache artifact
```

`autoformalize` writes Lean modules and manifests alongside other artifacts (e.g. `artifacts/<timestamp>__control-functional-deps/.../deps/`). If the cache already contains a Lean file for the dependency hash, it is reused; otherwise a computable stub is emitted and marked for later refinement by the autoformalizer agent.

**Cache management:**
- `--force-cache-regen`: Ignores cache and regenerates all dependencies from scratch, overwriting existing entries on hash collision
- `cache-clear-local`: Clears local cache in `artifacts/depcache/`
- `cache-clear-wandb`: Deletes the wandb cache artifact to start fresh across the team (requires wandb enabled)

## Viewing Results

### Inspect AI Viewer (Recommended)

View evaluation logs with the official inspect_ai viewer:

```bash
# View all results in artifacts directory
uv run inspect view --log-dir artifacts

# View specific run
uv run inspect view --log-dir artifacts/2025-10-14T15-30-00__control-functional

# View comparison results
uv run inspect view --log-dir artifacts/comparison_2025-10-14T15-45-00
```

The inspect viewer provides:
- Interactive web interface with scores and metrics
- Sample-by-sample inspection
- Filtering and sorting capabilities
- Comparison views for A/B testing

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

The benchmark supports **prompt variants** for A/B testing different prompting strategies. Variants allow systematic comparison of how different prompt formulations affect model performance.

### Quick Start

**List available variants:**
```bash
uv run fvspec --list-variants
```

**Run specific variant:**
```bash
uv run fvspec --variant control-functional
uv run fvspec --variant terse-functional
```

**Output organization:**
```
artifacts/
  2025-10-14T15-30-00__control-functional/
  2025-10-14T16-45-00__terse-functional/
```

### Architecture

**Directory structure (Single Source of Truth):**
```
src/benchmark/templates/
  shared/                    # SSoT for common prompt components
    initial.prompt          # Default initial prompt (used by most variants)
    fragments/              # Reusable system prompt sections
      task_core.txt        # Core task description
      output_format.txt    # <code> tag instruction
      metrics.txt          # Faithfulness/Interest scoring
    README.md              # Documentation for shared templates

  variants/
    control-functional/    # Control for functional-style experiments
      system.prompt        # Uses {% include %} for shared fragments
      metadata.toml
      # No initial.prompt - uses shared/initial.prompt

    control-mvcgen/        # Control for imperative-style experiments
      system.prompt        # Uses {% include %} for output_format.txt
      metadata.toml
      # No initial.prompt - uses shared/initial.prompt

    terse-functional/      # Treatment: minimal instructions
      system.prompt        # Custom, deliberately terse
      initial.prompt       # Override: terser than shared version
      metadata.toml

  registry.toml            # Master index
  prompt.py                # Jinja2 loader with {% include %} support
  registry.py              # Variant loading with shared fallback
```

**Key SSoT principles:**
- `shared/initial.prompt` is the default for all variants (override only when needed)
- `shared/fragments/` provides reusable sections via `{% include %}`
- Variants can mix shared fragments with custom content
- One change to a shared fragment updates all variants that use it

**Registry format** (`templates/registry.toml`):
```toml
[meta]
default_variant = "control-functional"

[variants.control-functional]
path = "variants/control-functional"
style = "functional"
description = "Default FVAPPS-style functional verification"
tags = ["functional", "stable", "control"]

[variants.terse-functional]
path = "variants/terse-functional"
style = "functional"
description = "Minimal instructions"
tags = ["functional", "treatment"]
based_on = "control-functional"
```

### Creating New Variants

**1. Copy existing variant:**
```bash
cp -r src/benchmark/templates/variants/control-functional \
      src/benchmark/templates/variants/my-experiment
```

**2. Edit system prompt:**
```bash
vim src/benchmark/templates/variants/my-experiment/system.prompt
```

**Leverage shared fragments with `{% include %}`:**
```jinja
You are an expert at X.

{% include 'shared/fragments/task_core.txt' %}

{% include 'shared/fragments/output_format.txt' %}

## Custom Section
Your experiment-specific content here...

{% include 'shared/fragments/metrics.txt' %}
```

**3. Decide on initial prompt:**
- **Use shared** (recommended): Delete `initial.prompt` file - variant will use `shared/initial.prompt`
- **Custom override**: Keep and edit `initial.prompt` for deliberately different wording

**4. Update metadata:**
```bash
vim src/benchmark/templates/variants/my-experiment/metadata.toml
```

Change `name`, `description`, and `notes.motivation`.

**5. Register variant:**

Edit `src/benchmark/templates/registry.toml`:
```toml
[variants.my-experiment]
path = "variants/my-experiment"
style = "functional"
description = "Testing hypothesis X"
tags = ["treatment"]
based_on = "control-functional"
```

**6. Test:**
```bash
uv run fvspec --variant my-experiment
```

### Comparing Variants

**A/B testing with eval_set (recommended):**
```bash
# Compare all control and treatment variants in parallel
uv run fvspec compare-variants

# Compare specific variants
uv run fvspec compare-variants --variant control-functional --variant terse-functional

# Compare with custom options
uv run fvspec compare-variants --variant control-mvcgen --variant control-functional --sample-size 50
```

The `compare-variants` subcommand uses `inspect_ai`'s `eval_set()` to run multiple variants in parallel with unified logging. Results are stored in `artifacts/comparison_<timestamp>/`.

**Manual sequential comparison:**
```bash
uv run fvspec --variant control-functional
uv run fvspec --variant my-experiment
```

**Compare outputs:**
```bash
diff artifacts/2025-*__control-functional/00123_test_foo/qa.json \
     artifacts/2025-*__my-experiment/00123_test_foo/qa.json
```

**Metrics to compare:**
- Faithfulness scores (how well Lean captures Python)
- Interest scores (complexity of specifications)
- Token usage (efficiency)
- Compilation success rate
- Lines of code generated

### Best Practices

**Naming:**
- `control-*` for control conditions
- `<experiment>-<style>` for treatments (e.g., `terse-functional`, `verbose-mvcgen`)

**Tags:**
- `control`: Control conditions
- `treatment`: Treatment conditions (experimental variants)
- `stable`: Production-ready
- `functional` / `mvcgen`: Style indicators

**Documentation:**
Always document in `metadata.toml`:
1. **Hypothesis**: What are you testing?
2. **Motivation**: Why this variant?
3. **Expected outcome**: What would validate your hypothesis?
4. **Based on**: Which variant did you modify?

### Configuration

Set defaults in `config.toml`:
```toml
[prompt]
variant = "control-functional"

[dataset]
sample_size = 100
```

Priority: CLI args (`--variant`, `--sample-size`) > config.toml > defaults

### Implementation

**Code flow:**
1. CLI (`__init__.py`): Parse `--variant` flag
2. Task (`task.py`): Load via `get_variant_prompts()`
3. Dataset (`dataset.py`): Render with variant template
4. Output (`declaration.py`): Write to `artifacts/<timestamp>__<name>/`

**Key classes:**
- `VariantRegistry`: Loads/validates from `registry.toml`
- `VariantConfig`: Pydantic model for variant metadata + templates
- `get_variant_prompts()`: Returns `(system_prompt, initial_template)` tuple

### Current Variants

**Control variants:**
- **control-functional**: Full FVAPPS-style instructions, recursion and induction
- **control-mvcgen**: Full mvcgen/Hoare logic instructions, loop invariants

**Treatment variants:**
- **terse-functional**: Minimal instructions, tests concision hypothesis

## Testing

Run smoke tests to verify the pipeline won't crash:

```bash
uv run pytest
```

## Other utilities

Preview prompt templates:

```bash
# Preview prompts (samples from database)
uv run preview-prompts data/pbts_full.db --prompt-type spec
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

## Verification Styles

Two approaches to Lean verification are available through variants:

- **functional** (FVAPPS style): Pure functional programming with recursion and induction (e.g., `control-functional`, `terse-functional`)
- **mvcgen** (imperative): `do` notation, Hoare triples, loop invariants, `mvcgen` tactic (e.g., `control-mvcgen`)
