# Merge: Unified Dataset Builder

Post-production tool that merges multiple benchmark runs into a single deduplicated JSONL dataset.

## Overview

The merge tool:
1. **Reads** run names from `runs.txt` listing directories to merge
2. **Combines** sample data from multiple runs (datapoint.json, qa.json, Lean code files)
3. **Deduplicates** by sample_id, keeping the highest quality sample when duplicates exist
4. **Prunes** schema according to configurable transformations (field removal, renaming, ordering)
5. **Outputs** a unified JSONL file where each line contains complete sample data

**Automatic quality-based deduplication:** When the same sample_id appears across multiple runs, the tool automatically keeps the best version based on:
- Success status
- Structural faithfulness score
- Theorem count
- Unit test availability
- Implementation/spec generation success

## Usage

### Prerequisites

From the `benchmark/` directory, ensure you have benchmark runs in `artifacts/runs/`.

**To sync runs from remote server:**
```bash
rsync -avxP user@server:fvspec-jobs/benchmark/artifacts/runs/ ~/path/to/fvspec/benchmark/artifacts/runs/
```

### Basic Usage

```bash
# Merge runs listed in runs.txt (default location)
uv run merge src/scripts/postproduction/merge/runs.txt

# Specify custom output file
uv run merge runs.txt --output artifacts/dataset-out/my-dataset.jsonl

# Use runs.txt from different location
uv run merge /path/to/custom-runs.txt
```

### Creating runs.txt

Edit `src/scripts/postproduction/merge/runs.txt` to list run directory names (one per line):

```text
2025-12-18T14-48-17__idx43000-43500__control-functional
2025-12-20T09-15-32__idx0-500__control-mvcgen
2025-12-21T11-30-45__idx500-1000__terse-functional
```

**Finding run directories:**
```bash
ls benchmark/artifacts/runs/
```

### Options

- `runs_file`: Path to file containing run directory names (required argument)
- `--output, -o`: Output JSONL file path (default: `artifacts/dataset-out/fvspec.jsonl`)

## Output Format

The output is a JSONL file (one JSON object per line) where each sample contains:

```json
{
  "sample_id": 12345,
  "id": "12345_test_example",
  "name": "test_example",
  "repo_id": 789,
  "run_provenance": "2025-12-18T14-48-17__idx43000-43500__control-functional",

  "code": "Python PBT source code...",
  "spec": "Lean specification code...",
  "impl": "Lean implementation code...",
  "tests": "Lean unit test code...",

  "success": true,
  "num_theorems": 3,
  "has_unit_tests": true,
  "structural_faithfulness": {...},
  "...": "...all other fields from datapoint.json and qa.json..."
}
```

**Key fields:**
- **sample_id**: Unique identifier for the sample (used for deduplication)
- **run_provenance**: Which run this sample came from (after deduplication)
- **code**: Original Python PBT source
- **spec/impl/tests**: Generated Lean formalization files
- **success**: Whether generation succeeded
- **structural_faithfulness**: Quality metrics
- All other fields from datapoint.json and qa.json are included

## Workflow Integration

The merge tool fits into the postproduction pipeline:

```bash
# 1. Sync runs from remote (if needed)
rsync -avxP user@server:fvspec-jobs/benchmark/artifacts/runs/ ./benchmark/artifacts/runs/

# 2. Create/edit runs.txt with desired run directories
vim src/scripts/postproduction/merge/runs.txt

# 3. Merge and deduplicate
uv run merge src/scripts/postproduction/merge/runs.txt
# Creates: artifacts/dataset-out/fvspec.jsonl

# 4. Grade samples for difficulty (optional)
uv run grader artifacts/dataset-out/fvspec.jsonl
# Creates: artifacts/dataset-out/fvspec.graded.jsonl

# 5. Analyze results
```

## Deduplication Algorithm

When multiple runs contain the same sample_id, the tool keeps the sample with the highest quality score.

**Quality scoring** (in priority order):
1. **success** (true > false) - Did generation succeed?
2. **structural_faithfulness.overall** (higher better) - How well does Lean capture Python?
3. **num_theorems** (higher better) - How many theorems were generated?
4. **has_unit_tests** (true > false) - Were unit tests generated?
5. **impl_autoform_success** (true > false) - Did implementation generation succeed?
6. **spec_sig_success** (true > false) - Did signature extraction succeed?

**Example:** If sample 12345 appears in both `run_A` and `run_B`:
- `run_A`: success=true, structural_faithfulness=0.85, num_theorems=5
- `run_B`: success=true, structural_faithfulness=0.90, num_theorems=3

The tool keeps the `run_B` version because structural faithfulness (0.90 > 0.85) is the tiebreaker after success (both true).

## Schema Pruning

The merge tool applies configurable schema transformations defined in `prune.py`:

### Field Removal

Remove unwanted fields from output by editing `FIELDS_TO_REMOVE` in `prune.py`:

```python
FIELDS_TO_REMOVE = {
    "internal_debug_field",
    "temporary_data",
}
```

### Field Renaming

Rename fields for consistency by editing `FIELD_RENAMES` in `prune.py`:

```python
FIELD_RENAMES = {
    "old_field_name": "new_field_name",
    "impl_code": "implementation",
}
```

### Field Ordering

Control output field order by editing `FIELD_ORDER` in `prune.py`:

```python
FIELD_ORDER = [
    "sample_id",
    "id",
    "name",
    # ... fields appear in this order
]
```

Fields not in `FIELD_ORDER` appear after listed fields in alphabetical order.

**To apply changes:**
1. Edit `src/scripts/postproduction/merge/prune.py`
2. Re-run merge command
3. New output will reflect transformations

## Architecture

**Files:**
- `__init__.py` - Main CLI entry point (Typer app)
- `deduplicate.py` - Quality-based deduplication logic
- `prune.py` - Schema transformation configuration
- `runs.txt` - List of run directories to merge
- `README.md` - This file

**Key functions:**
- `merge_runs_to_jsonl()` - Main orchestration
- `process_sample()` - Load and combine single sample
- `deduplicate_samples()` - Quality-based deduplication
- `prune_samples()` - Apply schema transformations

**Output directory:**
```
benchmark/artifacts/dataset-out/
  fvspec.jsonl           # Default merged output
  fvspec.graded.jsonl    # After grading (optional)
```

## Statistics

The tool displays merge statistics:

```
Merge Summary:

  Runs processed: 3
  Total samples processed: 1,247
  Unique samples written: 1,189
  Duplicates replaced: 58
  Skipped: 0

✓ Merge complete! Deduplicated data saved to: artifacts/dataset-out/fvspec.jsonl
File size: 45.2 MB
```

**Interpreting stats:**
- **Runs processed**: How many runs from runs.txt were found and processed
- **Total samples processed**: Total samples across all runs (including duplicates)
- **Unique samples written**: Final count after deduplication
- **Duplicates replaced**: How many samples were replaced with higher quality versions
- **Skipped**: Samples missing required files (datapoint.json or qa.json)

## Use Cases

### Merge multiple sampling runs

When you run the benchmark with sequential sampling (idx0-500, idx500-1000, etc.), merge them into one dataset:

```bash
# runs.txt contains:
# 2025-12-18T14-48-17__idx0-500__control-functional
# 2025-12-18T15-20-10__idx500-1000__control-functional
# 2025-12-18T16-10-43__idx1000-1500__control-functional

uv run merge src/scripts/postproduction/merge/runs.txt
```

### Compare and merge variants

Merge runs from different variants to create a unified dataset:

```bash
# runs.txt contains:
# 2025-12-20T09-15-32__control-functional
# 2025-12-20T09-15-45__control-mvcgen
# 2025-12-20T09-16-02__terse-functional

uv run merge src/scripts/postproduction/merge/runs.txt -o artifacts/dataset-out/all-variants.jsonl
```

### Re-run failed samples

If some samples failed in one run, re-run them and merge with originals (deduplication keeps best):

```bash
# runs.txt contains:
# 2025-12-18T14-48-17__original-run
# 2025-12-19T10-30-00__failed-samples-retry

uv run merge src/scripts/postproduction/merge/runs.txt
# Automatically keeps successful versions from retry run
```

## Notes

- **Idempotent**: Safe to re-run with same inputs (overwrites output file)
- **Order independent**: Deduplication is deterministic regardless of run order in runs.txt
- **Gitignored**: Output directory `artifacts/dataset-out/` is gitignored
- **Performance**: Processes ~1000 samples/minute (varies by disk speed)
- **Memory**: Loads all samples into memory during deduplication (typically <1GB for 10k samples)
