# Grader: Difficulty Assessment

Post-production tool that uses Claude Haiku 4.5 to estimate proof difficulty for Lean formalizations.

## Overview

The grader evaluates each sample on **Difficulty** (0-10): estimates the challenge of completing the proofs (replacing `sorry` with actual proofs), considering mathematical complexity, type challenges, proof difficulty, domain knowledge, and Lean expertise.

Each score is accompanied by **"Haiku Takes"**: prose justification explaining the key factors behind the score.

**Philosophy**: The grader treats the Lean formalization as a standalone formal verification task, **ignoring its Python provenance**. It evaluates: "Given this Lean code, how hard would it be to prove these theorems?" The Python source that generated it is irrelevant to the difficulty of the Lean problem itself.

**Why only difficulty?** Quality is already captured during generation via:
- `structural_faithfulness`: Objective metrics (parameter coverage, type correspondence, etc.)
- `faithfulness_subjective`: Self-reported score (though currently not populated)
- `plausibility`: Automated property testing results

Difficulty requires human/LLM judgment and isn't captured elsewhere.

## Usage

### Prerequisites

Set your Anthropic API key. You can either:

1. Create a `.env` file in the repo root (`./`) with:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Or export it as an environment variable:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

The grader will automatically load `.env` from the repo root when running from `./benchmark/`.

### Basic Usage

From the `benchmark/` directory:

```bash
# Grade all samples in a merged JSONL file
uv run grader artifacts/dataset-out/fvspec-jan22.jsonl

# Specify output file
uv run grader input.jsonl --output graded.jsonl

# Test with a small limit
uv run grader input.jsonl --limit 10

# Retry failed samples (input must be a previously graded file)
uv run grader input.graded.jsonl --retry-failed
```

### Options

- `--output, -o`: Output file path (default: `<input>.graded.jsonl`)
- `--model, -m`: Model to use (default: `claude-haiku-4-5-20251001`)
- `--limit, -n`: Grade only the first N samples (output still contains all samples, but only first N are graded)
- `--retry-failed`: Only re-grade samples that have `grader_error` field. **Important**: Input must be a previously graded file (e.g., `input.graded.jsonl`), not the original input.
- `--parallel, -p`: Parallel workers (not yet implemented)

**Notes**:
- The output is always a complete copy of the input. `--limit` and `--retry-failed` control which samples get graded, but all samples are written to the output file.
- When using `--retry-failed`, the input must be a previously graded file (containing `grader_error` fields), not the original ungraded input.
- **Prompt caching**: The system prompt is automatically cached, reducing cost by ~90% for cached tokens. Cache lasts 5 minutes, so batched grading is highly cost-effective.
- **Rate limiting**: If you hit rate limits (429 errors), the grader will automatically retry with exponential backoff. You can safely run large batches.

## Output Format

**Important**: The output file is a **complete copy** of the input file. All samples are written to the output, but only the specified samples (based on `--limit`, `--retry-failed`, or all if neither) are re-graded. Other samples pass through unchanged.

**What gets graded**: Only the Lean formalization itself (spec + impl code). The grader ignores Python source, dependencies, complexity metrics, and other provenance - it treats each sample as a standalone Lean verification task.

Each graded sample is augmented with two fields:

```json
{
  "grader_difficulty": {
    "score": 6.5,
    "haiku_takes": "This task requires moderate Lean proficiency for type class usage and recursion. The mathematical complexity is straightforward, but the proof obligations involve non-trivial induction steps."
  },
  "grader_metadata": {
    "model": "claude-haiku-4-5-20251001",
    "timestamp": "2025-01-23T12:34:56.789Z",
    "tokens_used": 1422,
    "grading_time_seconds": 1.15,
    "version": "1.0.0"
  }
}
```

If grading fails, a `grader_error` field is added with the error message.

## Cost Estimation

**Per sample (first call)**: ~1K system + Lean code input + ~250 output tokens ≈ ~$0.0005-0.0015 (varies by code length)
**Per sample (with cache hit)**: ~100 system (cached) + Lean code input + ~250 output ≈ ~$0.0003-0.0008

For 10,000 samples: ~$5-15 (depends on code length), with ~50% savings from caching

The grader uses **prompt caching** for the system prompt, which saves ~90% on cached tokens after the first request. The cache lasts 5 minutes, so batched grading is highly cost-effective. Input size varies based on Lean code length (spec + impl).

Use `--limit` to test on a small number of samples before running on full dataset.

## Retry Workflow

If some samples fail due to API errors or rate limits, use `--retry-failed` to re-grade only those samples:

```bash
# Step 1: Initial grading run
uv run grader artifacts/dataset-out/fvspec-jan22.jsonl
# Creates: fvspec-jan22.graded.jsonl
# Some samples may have grader_error field

# Step 2: Check for errors
grep -c "grader_error" artifacts/dataset-out/fvspec-jan22.graded.jsonl

# Step 3: Retry failed samples (input is the GRADED file, not original)
uv run grader artifacts/dataset-out/fvspec-jan22.graded.jsonl --retry-failed \
  -o artifacts/dataset-out/fvspec-jan22.graded.jsonl
# Only re-grades samples with grader_error field
# Overwrites the file with corrected version

# Step 4: Verify all succeeded
grep -c "grader_error" artifacts/dataset-out/fvspec-jan22.graded.jsonl
# Should be 0 (or fewer than before)
```

**Important**: `--retry-failed` expects a **previously graded file** as input (one that has `grader_error` fields). Don't pass the original ungraded input.

## Workflow Integration

The grader fits into the postproduction pipeline:

```bash
# 1. Merge runs
uv run merge src/scripts/postproduction/merge/runs.txt

# 2. Deduplicate
uv run python src/scripts/postproduction/deduplicate.py artifacts/dataset-out/fvspec-jan22.jsonl

# 3. Grade samples for difficulty
uv run grader artifacts/dataset-out/fvspec-jan22.jsonl
# Creates: artifacts/dataset-out/fvspec-jan22.graded.jsonl

# 4. Retry failed samples (if any had errors)
uv run grader artifacts/dataset-out/fvspec-jan22.graded.jsonl --retry-failed -o artifacts/dataset-out/fvspec-jan22.graded.jsonl
# Re-grades only samples with grader_error field, overwrites the file

# 5. Analyze and filter by difficulty scores
```

## Architecture

- **SDK**: Raw Anthropic SDK (not pydantic-ai) for simple LLM-as-judge task
- **Structured output**: Uses new beta structured outputs API for guaranteed JSON schema conformance
- **Templates**: Jinja2 templates for prompts (modular and editable)
- **Prompt caching**: System prompt is cached for 90% cost savings on repeated calls
- **Rate limit handling**:
  - Graceful handling of 429 errors with exponential backoff + jitter
  - Respects `retry-after` headers from API
  - Automatic retry with increasing delays
- **Incremental output**: Writes samples as they're graded (resume-friendly)
- **Error handling**: Failed samples written with `grader_error` field

## Files

- `__init__.py` - Typer CLI entry point
- `models.py` - Pydantic models for grading results (DifficultyGrade, GraderMetadata)
- `client.py` - Anthropic API wrapper with retry logic and structured outputs
- `grader.py` - Core grading logic (orchestrates prompts + client)
- `prompts/` - Jinja2 prompt templates and loaders
  - `__init__.py` - Template loading functions (load_system_prompt, render_difficulty_prompt)
  - `system.prompt` - Shared system prompt (cached for 90% savings)
  - `difficulty.prompt.template` - Difficulty estimation template (Jinja2)

## Customization

### Editing Prompts
Edit prompt templates in `prompts/` to customize grading criteria:
- `system.prompt` - Core instructions and context (plain text)
- `difficulty.prompt.template` - Difficulty assessment prompt (Jinja2 template)

The template loaders are in `prompts/__init__.py` and use Jinja2 for variable substitution.

### Import Style
All imports use absolute paths (`from scripts.postproduction.grader.X import Y`) for clarity and IDE support.

## Performance Notes

- **Prompt caching**: System prompt cached for 90% savings on repeat calls (5 min TTL)
- **Rate limits**: Automatic retry with exponential backoff + jitter for 429 errors
- **Batching**: Most cost-effective to grade samples in batches (caching benefits)
- **Failed generations**: Grader handles failed generations gracefully
- **Calibrated scoring**: 5 is moderate difficulty, 8+ is very challenging
- **Parallel processing**: Not yet implemented (use serial mode)
- **Quality vs Difficulty**: Quality already captured via `structural_faithfulness` and `plausibility` metrics
