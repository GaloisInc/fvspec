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
# Grade all samples (output: fvspec-jan22.graded.jsonl)
uv run grader artifacts/dataset-out/fvspec-jan22.jsonl

# Grade to specific output (resume-safe: reuses existing grades from output)
uv run grader input.jsonl -o graded.jsonl
uv run grader input.jsonl -o graded.jsonl  # Run again: skips already-graded

# Test with a small limit
uv run grader input.jsonl --limit 10

# Retry failed samples (grades missing + retries errors)
uv run grader input.graded.jsonl --retry-failed
```

### Range-Based Grading

Grade specific ranges of samples using `--start-idx` and `--stop-idx` (0-based indexing):

```bash
# Grade samples 100-199 (inclusive start, exclusive stop)
uv run grader input.jsonl --start-idx 100 --stop-idx 200

# Resume from sample 500 to end
uv run grader input.jsonl --start-idx 500

# Grade up to sample 1000 (0-999)
uv run grader input.jsonl --stop-idx 1000

# Retry errors in specific range
uv run grader input.graded.jsonl --retry-failed --start-idx 500 --stop-idx 1000
```

**Parallelization with ranges**: Split large datasets into chunks for parallel processing:

```bash
# Split 10,000 samples into 4 parallel workers (separate outputs)
uv run grader input.jsonl --start-idx 0 --stop-idx 2500 -o output-1.jsonl     # Terminal 1
uv run grader input.jsonl --start-idx 2500 --stop-idx 5000 -o output-2.jsonl  # Terminal 2
uv run grader input.jsonl --start-idx 5000 --stop-idx 7500 -o output-3.jsonl  # Terminal 3
uv run grader input.jsonl --start-idx 7500 -o output-4.jsonl                  # Terminal 4

# Then merge the graded chunks
cat output-{1,2,3,4}.jsonl > output.graded.jsonl
```

**Simpler approach** (sequential resume): Just run the same command multiple times:
```bash
uv run grader input.jsonl -o output.graded.jsonl  # Run, interrupt, re-run - it resumes
```

### Options

- `--output, -o`: Output file path (default: `<input>.graded.jsonl`, idempotent if input already ends in `.graded.jsonl`)
- `--model, -m`: Model to use (default: `claude-haiku-4-5-20251001`)
- `--limit, -n`: Grade only the first N missing samples (mutually exclusive with `--start-idx`/`--stop-idx`)
- `--start-idx`: Start grading from this index (0-based, inclusive). Can be used alone or with `--stop-idx`
- `--stop-idx`: Stop grading at this index (0-based, exclusive). Can be used alone or with `--start-idx`
- `--retry-failed`: Also retry samples with `grader_error` field (default: only grades missing samples)
- `--parallel, -p`: Parallel workers (not yet implemented)

**Default behavior**:
- **Resume-safe**: If output file exists, already-graded samples are reused (matched by sample name)
- **Skips already-graded**: Samples with difficulty fields in input or output pass through unchanged
- **Complete copy**: All samples written to output, only missing ones are graded
- **Idempotent naming**: Running on `foo.graded.jsonl` outputs to the same file (not `foo.graded.graded.jsonl`)

**Notes**:
- `--limit` and `--start-idx`/`--stop-idx` are mutually exclusive (validation enforced)
- `--retry-failed` adds error retry to default missing-sample behavior
- **Prompt caching**: The system prompt is automatically cached, reducing cost by ~90% for cached tokens. Cache lasts 5 minutes, so batched grading is highly cost-effective.
- **Rate limiting**: If you hit rate limits (429 errors), the grader will automatically retry with exponential backoff. You can safely run large batches.

## Output Format

**Important**: The output file is a **complete copy** of the input file. All samples are written to the output.

**What gets graded by default**: Samples missing `difficulty_subjective_haiku` field (resume-safe behavior). Already-graded samples pass through unchanged. Use `--retry-failed` to also retry samples with `grader_error`.

**What gets graded**: Only the Lean formalization itself (spec + impl code). The grader ignores Python source, dependencies, complexity metrics, and other provenance - it treats each sample as a standalone Lean verification task.

Each graded sample is augmented with the following fields:

```json
{
  "difficulty_subjective_haiku": 6.5,
  "difficulty_subjective_haiku_takes": "This task requires moderate Lean proficiency for type class usage and recursion. The mathematical complexity is straightforward, but the proof obligations involve non-trivial induction steps.",
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

## Resume and Retry Workflow

The grader automatically resumes partial runs by reusing grades from the output file:

```bash
# Step 1: Initial grading run (may be interrupted)
uv run grader fvspec.jsonl -o fvspec.graded.jsonl
# Creates: fvspec.graded.jsonl with some samples graded

# Step 2: Resume - reuses existing grades from output file
uv run grader fvspec.jsonl -o fvspec.graded.jsonl
# Loads fvspec.graded.jsonl, reuses already-graded samples
# Only grades samples not yet in output

# Step 3: Check for errors
grep -c "grader_error" fvspec.graded.jsonl

# Step 4: Retry errors (if any exist)
uv run grader fvspec.graded.jsonl --retry-failed
# Grades missing samples + retries samples with grader_error

# Step 5: Verify all succeeded
grep -c "grader_error" fvspec.graded.jsonl
# Should be 0
```

**Range-based resume/retry**:

```bash
# Resume from specific point
uv run grader input.graded.jsonl --start-idx 1000

# Retry errors in specific range
uv run grader input.graded.jsonl --retry-failed --start-idx 1000 --stop-idx 2000
```

**Key insight**: The grader checks the output file for existing grades. You can always re-run `grader input.jsonl -o output.graded.jsonl` and it will skip samples already in the output.

## Workflow Integration

The grader fits into the postproduction pipeline:

```bash
# 1. Merge and deduplicate runs
uv run merge src/scripts/postproduction/merge/runs.txt
# Creates: artifacts/dataset-out/fvspec.jsonl

# 2. Grade samples for difficulty (resume-safe)
uv run grader artifacts/dataset-out/fvspec.jsonl -o artifacts/dataset-out/fvspec.graded.jsonl
# Creates fvspec.graded.jsonl, can be re-run to resume

# 3. Retry failed samples (if any had errors)
uv run grader artifacts/dataset-out/fvspec.graded.jsonl --retry-failed
# Re-grades samples with grader_error field

# 4. Analyze and filter by difficulty scores
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
- **Resume from output**: Loads existing grades from output file to avoid re-grading
- **Incremental output**: Writes samples as they're graded
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
