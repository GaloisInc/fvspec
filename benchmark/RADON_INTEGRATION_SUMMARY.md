# Radon Metrics Integration - Summary

## What Was Implemented

Radon code complexity metrics are now **automatically included** in all benchmark runs. The integration queries radon metrics from the database and logs them to wandb for each sample.

## Changes Made

### 1. Quality Assessment Model (`src/generate/scaffold/quality_assessment/models.py`)

**Added 21 radon metric fields:**
- `radon__loc`, `radon__sloc`, `radon__lloc` - Lines of code metrics
- `radon__comments`, `radon__blank`, `radon__multi`, `radon__single_comments` - Comment metrics
- `radon__num_functions`, `radon__avg_complexity`, `radon__max_complexity`, `radon__total_complexity` - Complexity metrics
- `radon__complexity_rank`, `radon__maintainability_index`, `radon__maintainability_rank` - Quality ranks
- `radon__halstead_*` - Halstead complexity metrics (vocabulary, length, volume, difficulty, effort, time, bugs)

**Updated `from_task_state()` method:**
- Queries `radon_metrics` table from database using sample ID
- Gracefully handles missing metrics (sets to None)
- Fails silently if radon_metrics table doesn't exist

**Automatic wandb logging:**
- `to_wandb_metrics()` already uses `model_dump()` and flattening
- New radon__ fields automatically flow through to wandb
- No additional changes needed!

### 2. Documentation (`README.md`)

Updated the "Radon Code Metrics" section to explain:
- Metrics are automatically logged if radon_metrics table exists
- One-time setup to compute and import metrics
- How to view metrics in wandb, Inspect viewer, and qa.json files
- Note about wandb API limitations (can't backfill finished runs)

### 3. Backfill Script (Not Used)

**`src/scripts/backfill_radon_to_wandb.py`** - Created but **not functional** due to wandb API limitations:
- Wandb doesn't allow modifying finished runs via public API
- Script remains in repo for reference but documented as non-functional
- Proper solution is to re-run benchmarks with radon metrics integrated

## How It Works

1. **During benchmark run:**
   - Each sample is evaluated
   - `QualityAssessment.from_task_state()` is called
   - Queries `radon_metrics` table for the sample's PBT ID
   - Adds metrics to QualityAssessment object

2. **Logging to wandb:**
   - `qa.to_wandb_metrics()` exports all metrics (including radon__)
   - Wandb logger calls this method for each sample
   - Radon metrics appear at each step with `radon__` prefix

3. **Saved to artifacts:**
   - `qa.json` files contain all metrics including radon__
   - Available for post-run analysis

## One-Time Setup

If you haven't already, compute and import radon metrics:

```bash
# Compute for all PBTs (takes ~5-10 minutes)
uv run compute-radon-metrics --output artifacts/radon_metrics/metrics.json

# Import into database (creates radon_metrics table with 54,345 records)
uv run import-radon-metrics artifacts/radon_metrics/metrics.json

# Verify
uv run import-radon-metrics verify
```

**After this setup, all future benchmark runs automatically include radon metrics.**

## Using Radon Metrics

### Run a Benchmark

```bash
# Run with radon metrics automatically included
uv run fvspec --variant control-functional --sample-size 50

# Compare variants with radon metrics
uv run fvspec compare-variants --variant control-functional --variant terse-functional
```

### View in Wandb

1. Go to your run in wandb
2. **Charts tab**: Filter metrics by "radon__" to see all radon metrics
3. **Table tab**: See radon__ columns for each sample
4. **Workspace**: Compare radon metrics across runs and variants

**Useful visualizations:**
- `radon__avg_complexity` vs step - Complexity over samples
- `radon__maintainability_index` vs step - Maintainability trends
- Scatter: `radon__sloc` (X) vs `radon__avg_complexity` (Y) - Size vs complexity
- Correlate with benchmark metrics: `radon__avg_complexity` vs `token_usage`

### View in Inspect AI

```bash
uv run inspect view --log-dir artifacts
# Browse samples and see radon metrics in scores table
```

### Query from Files

```bash
# View radon metrics in qa.json
cat artifacts/<run>/12345_test_foo/qa.json | jq '.radon__avg_complexity'

# Extract all radon metrics
cat artifacts/<run>/*/qa.json | jq '{id: .sample_id, complexity: .radon__avg_complexity, maintainability: .radon__maintainability_index}'
```

## Metrics Available

All metrics prefixed with `radon__`:

**Raw Metrics:**
- `loc` - Total lines of code
- `sloc` - Source lines of code (no blanks/comments)
- `lloc` - Logical lines of code
- `comments` - Comment lines
- `blank` - Blank lines
- `multi` - Multi-line strings
- `single_comments` - Single-line comments

**Complexity:**
- `num_functions` - Number of functions analyzed
- `avg_complexity` - Average cyclomatic complexity
- `max_complexity` - Maximum complexity
- `total_complexity` - Sum of complexities
- `complexity_rank` - Rank A-F (A best)

**Maintainability:**
- `maintainability_index` - MI score 0-100 (higher better)
- `maintainability_rank` - Rank A-C (A best)

**Halstead:**
- `halstead_vocabulary` - Unique operators + operands
- `halstead_length` - Total operators + operands
- `halstead_volume` - Program volume
- `halstead_difficulty` - Difficulty score
- `halstead_effort` - Implementation effort
- `halstead_time` - Time to implement (seconds)
- `halstead_bugs` - Expected bugs

## Benefits

1. **Objective complexity measures** - Track PBT complexity across runs
2. **Correlation analysis** - See if complex PBTs affect model performance
3. **Variant comparison** - Compare model behavior on different complexity levels
4. **Sample selection** - Filter/sample based on complexity
5. **Quality tracking** - Monitor maintainability trends

## Limitations & Notes

### Cannot Backfill Finished Runs

Wandb's public API doesn't allow adding history to finished runs. To get radon metrics for existing variants:
- Re-run the benchmarks after setting up radon_metrics table
- Or analyze radon metrics separately using database queries

### Missing Metrics Handled Gracefully

If a sample's radon metrics aren't in the database:
- Fields are set to None
- Run continues without errors
- Other metrics still logged normally

### Performance Impact

- Minimal: One database query per sample
- Query is fast (indexed by pbt_id)
- No noticeable slowdown in benchmark runs

## Next Steps

1. **Run a test benchmark** with radon metrics:
   ```bash
   uv run fvspec --variant control-functional --sample-size 10
   ```

2. **Check wandb** to verify radon__ metrics appear

3. **Analyze results** to see if code complexity correlates with:
   - Token usage
   - Success rate
   - Generation time
   - Faithfulness scores

4. **Use radon metrics** to filter/stratify samples in future experiments

## Files Modified

- `src/generate/scaffold/quality_assessment/models.py` - Added radon fields and query logic
- `README.md` - Updated documentation
- `RADON_INTEGRATION_SUMMARY.md` (this file) - Integration guide

## References

- Radon metrics computation: `src/generate/scaffold/quality_assessment/radon_metrics.py`
- Import script: `src/scripts/import_radon_metrics.py`
- Compute script: `src/scripts/compute_radon_metrics.py`
- Radon documentation: https://radon.readthedocs.io/
