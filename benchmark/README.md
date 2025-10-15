# Benchmark

## Running the benchmark

```bash
# List available variants
uv run fvspec --list-variants

# Run with control variant (uses default from config or registry if not specified)
uv run fvspec
uv run fvspec --variant control-functional

# Run with treatment variant
uv run fvspec --variant terse-functional

# Run with control mvcgen variant
uv run fvspec --variant control-mvcgen

# Disable MCP tools for faster execution
uv run fvspec --no-mcp
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
  2025-10-14T15-30-00__variant_control-functional/
  2025-10-14T16-45-00__variant_terse-functional/
```

### Architecture

**Directory structure:**
```
src/benchmark/templates/
  variants/
    control-functional/       # Control for functional-style experiments
      system.prompt
      initial.prompt
      metadata.toml

    control-mvcgen/          # Control for imperative-style experiments
      system.prompt
      initial.prompt
      metadata.toml

    terse-functional/        # Treatment: minimal instructions
      system.prompt
      initial.prompt
      metadata.toml

  registry.toml              # Master index
```

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

**2. Edit prompts:**
```bash
vim src/benchmark/templates/variants/my-experiment/system.prompt
vim src/benchmark/templates/variants/my-experiment/initial.prompt
```

**3. Update metadata:**
```bash
vim src/benchmark/templates/variants/my-experiment/metadata.toml
```

Change `name`, `description`, and `notes.motivation`.

**4. Register variant:**

Edit `src/benchmark/templates/registry.toml`:
```toml
[variants.my-experiment]
path = "variants/my-experiment"
style = "functional"
description = "Testing hypothesis X"
tags = ["treatment"]
based_on = "control-functional"
```

**5. Test:**
```bash
uv run fvspec --variant my-experiment
```

### Comparing Variants

**Run control and treatment:**
```bash
uv run fvspec --variant control-functional
uv run fvspec --variant my-experiment
```

**Compare outputs:**
```bash
diff artifacts/2025-*__variant_control-functional/00123_test_foo/QA.json \
     artifacts/2025-*__variant_my-experiment/00123_test_foo/QA.json
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

Set default variant in `config.toml`:
```toml
[prompt]
variant = "control-functional"
```

Priority: `--variant` (CLI arg) > `config.variant` > registry default

### Implementation

**Code flow:**
1. CLI (`__init__.py`): Parse `--variant` flag
2. Task (`task.py`): Load via `get_variant_prompts()`
3. Dataset (`dataset.py`): Render with variant template
4. Output (`declaration.py`): Write to `artifacts/<timestamp>__variant_<name>/`

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

## Dashboard

View benchmark results interactively:

```bash
uv run panel serve src/scripts/dashboard.py
```

With custom arguments:

```bash
uv run panel serve src/scripts/dashboard.py --args -d "artifacts/2025-10-01T13-26-28" -x "interest" -y "faithfulness"
```

## Testing

Run smoke tests to verify the pipeline won't crash:

```bash
uv run pytest
```

## Other utilities

Preview prompt templates:

```bash
# Preview prompts with functional or mvcgen style
uv run preview_prompts <data_file.json> --style functional
uv run preview_prompts <data_file.json> --style mvcgen
```

Analyze dependencies in scraped tests:

```bash
uv run analyze_deps
```

## Verification Styles

Two approaches to Lean verification are available through variants:

- **functional** (FVAPPS style): Pure functional programming with recursion and induction (e.g., `control-functional`, `terse-functional`)
- **mvcgen** (imperative): `do` notation, Hoare triples, loop invariants, `mvcgen` tactic (e.g., `control-mvcgen`)
