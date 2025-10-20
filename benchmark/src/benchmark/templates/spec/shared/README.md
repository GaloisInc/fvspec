# Shared Prompt Templates (Single Source of Truth)

This directory contains shared prompt components used across multiple variants to maintain consistency and reduce duplication.

## Structure

```
shared/
  initial.prompt           # Default initial user prompt (SSoT)
  fragments/               # Reusable system prompt sections
    task_core.txt         # Core task description
    output_format.txt     # Code output format instruction
    metrics.txt           # Faithfulness/Interest metrics description
```

## Usage

### Initial Prompt

The `initial.prompt` file is the **single source of truth** for the initial user prompt. Variants will automatically use this unless they provide their own override.

**To use the shared initial prompt:**
- Simply don't create an `initial.prompt` file in your variant directory
- The system will automatically fall back to `shared/initial.prompt`

**To override with custom wording:**
- Create `initial.prompt` in your variant directory
- Example: `terse-functional` has its own for deliberately concise wording

### System Prompt Fragments

Fragments are reusable sections that can be included in variant system prompts using Jinja2's `{% include %}` directive.

**Example usage in `variants/control-functional/system.prompt`:**

```jinja
You are an expert at declaring Lean 4 theorems.

{% include 'shared/fragments/task_core.txt' %}

## Output Format
{% include 'shared/fragments/output_format.txt' %}

## Strategy
Use the available Lean LSP tools...

## Metrics
{% include 'shared/fragments/metrics.txt' %}
```

## Adding New Shared Content

**When to create a shared fragment:**
1. Content is identical across 2+ variants
2. Content represents a conceptual standard (output format, metrics)
3. Consistency matters more than customization

**When NOT to share:**
1. Content is deliberately different for experimental reasons
2. Content is style-specific (functional vs mvcgen)
3. Variant is testing a hypothesis about that specific content

## Variant Override Hierarchy

```
1. Variant-specific file (variants/my-variant/initial.prompt)
   ↓ (if not found)
2. Shared default (shared/initial.prompt)
   ↓ (if not found)
3. Error: template not found
```

## Examples

**Variant using shared initial prompt:**
```
variants/control-functional/
  system.prompt    # Uses {% include %} for shared fragments
  metadata.toml
  # No initial.prompt - uses shared/initial.prompt
```

**Variant with custom initial prompt:**
```
variants/terse-functional/
  system.prompt    # May or may not use includes
  initial.prompt   # Custom override for deliberate terseness
  metadata.toml
```

## Maintaining SSoT

When updating shared content:
1. Update the fragment in `shared/fragments/`
2. All variants that include it will automatically use the new version
3. Variants with overrides are unaffected

When a variant needs customization:
1. Stop including the fragment
2. Write variant-specific content inline
3. Document why in the variant's `metadata.toml`
