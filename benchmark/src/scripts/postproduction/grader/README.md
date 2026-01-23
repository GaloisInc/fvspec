# Grader: Quality and Difficulty Assessment

Post-production tool that uses Claude Haiku 4.5 to grade benchmark samples for formalization quality and difficulty.

## Overview

The grader evaluates each sample along two dimensions:

1. **Quality**: Assesses how well the Lean formalization captures the Python PBT
   - Correctness (0-10): Faithfulness to Python logic
   - Type safety (0-10): Type alignment with Python semantics
   - Edge cases (0-10): Boundary condition handling
   - Lean idioms (0-10): Idiomatic Lean code

2. **Difficulty**: Estimates the challenge of creating the formalization
   - Math complexity (0-10): Abstract reasoning required
   - Type challenges (0-10): Type system complexity
   - Proof difficulty (0-10): Proof sophistication needed
   - Domain knowledge (0-10): Specialized knowledge required
   - Lean expertise (0-10): Lean proficiency needed

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

# Skip one dimension
uv run grader input.jsonl --skip-difficulty  # Only grade quality
uv run grader input.jsonl --skip-quality     # Only grade difficulty

# Retry failed samples (input must be a previously graded file)
uv run grader input.graded.jsonl --retry-failed
```

### Options

- `--output, -o`: Output file path (default: `<input>.graded.jsonl`)
- `--model, -m`: Model to use (default: `claude-haiku-4-5-20251001`)
- `--limit, -n`: Grade only the first N samples (output still contains all samples, but only first N are graded)
- `--skip-quality`: Skip quality assessment (only grade difficulty)
- `--skip-difficulty`: Skip difficulty assessment (only grade quality)
- `--retry-failed`: Only re-grade samples that have `grader_error` field. **Important**: Input must be a previously graded file (e.g., `input.graded.jsonl`), not the original input.
- `--parallel, -p`: Parallel workers (not yet implemented)

**Notes**:
- The output is always a complete copy of the input. `--limit` and `--retry-failed` control which samples get graded, but all samples are written to the output file.
- When using `--retry-failed`, the input must be a previously graded file (containing `grader_error` fields), not the original ungraded input.

## Output Format

**Important**: The output file is a **complete copy** of the input file. All samples are written to the output, but only the specified samples (based on `--limit`, `--retry-failed`, or all if neither) are re-graded. Other samples pass through unchanged.

Each graded sample is augmented with three fields:

```json
{
  "grader_quality": {
    "score": 7.5,
    "correctness": 8.0,
    "type_safety": 7.0,
    "edge_cases": 7.0,
    "lean_idioms": 8.0,
    "explanation": "The formalization correctly captures...",
    "confidence": 0.85
  },
  "grader_difficulty": {
    "score": 6.5,
    "math_complexity": 7.0,
    "type_challenges": 6.0,
    "proof_difficulty": 7.0,
    "domain_knowledge": 5.0,
    "lean_expertise": 6.0,
    "explanation": "This task requires understanding...",
    "confidence": 0.9
  },
  "grader_metadata": {
    "model": "claude-haiku-4-5-20251001",
    "timestamp": "2025-01-23T12:34:56.789Z",
    "tokens_used": 3542,
    "quality_tokens": 1821,
    "difficulty_tokens": 1721,
    "grading_time_seconds": 2.45,
    "version": "1.0.0"
  }
}
```

If grading fails, a `grader_error` field is added with the error message.

## Cost Estimation

**Per sample**: ~3.5K input tokens + ~500 output tokens = ~$0.0015

For 10,000 samples: ~$15

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

# 3. Grade samples (NEW)
uv run grader artifacts/dataset-out/fvspec-jan22.jsonl
# Creates: artifacts/dataset-out/fvspec-jan22.graded.jsonl

# 4. Retry failed samples (if any had errors)
uv run grader artifacts/dataset-out/fvspec-jan22.graded.jsonl --retry-failed -o artifacts/dataset-out/fvspec-jan22.graded.jsonl
# Re-grades only samples with grader_error field, overwrites the file

# 5. Analyze and filter by quality/difficulty scores
```

## Architecture

- **SDK**: Raw Anthropic SDK (not pydantic-ai) for simple LLM-as-judge task
- **Structured output**: Uses tool use pattern for guaranteed JSON schema conformance
- **Templates**: Jinja2 templates for prompts (modular and editable)
- **Retry logic**: Exponential backoff for rate limits
- **Incremental output**: Writes samples as they're graded (resume-friendly)
- **Error handling**: Failed samples written with `grader_error` field

## Files

- `__init__.py` - Typer CLI entry point
- `models.py` - Pydantic models for grading results
- `client.py` - Anthropic API wrapper with retry logic
- `grader.py` - Core grading logic and template rendering
- `prompts/` - Jinja2 prompt templates
  - `system.prompt` - Shared system prompt
  - `quality.prompt.template` - Quality assessment template
  - `difficulty.prompt.template` - Difficulty estimation template

## Customization

Edit prompt templates in `prompts/` to customize grading criteria without modifying Python code.

## Notes

- Grader handles failed generations (spec/impl may be None)
- Structural faithfulness scores provided as context, not to bias assessment
- Calibrated scoring: 5 is average, 8+ is exceptional/very challenging
- Parallel processing not yet implemented (use serial mode)
