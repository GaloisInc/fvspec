# Weights & Biases Integration

The fvspec benchmark now supports logging metrics to [Weights & Biases](https://wandb.ai/) for better experiment tracking and visualization.

## Setup

1. Install wandb (already included in dependencies):
   ```bash
   uv sync
   ```

2. Login to wandb:
   ```bash
   wandb login
   ```

3. Enable wandb logging in `config.toml`:
   ```toml
   [wandb]
   enabled = true
   project = "fvspec"
   entity = "your-team"  # optional
   tags = ["experiment-1"]
   log_code = true
   log_qa = true
   ```

## Usage

### Single Variant Run

Run with wandb logging enabled via config:
```bash
uv run fvspec --variant control-functional
```

Enable wandb via CLI (overrides config):
```bash
uv run fvspec --wandb --wandb-project my-project --wandb-tag experiment-2
```

Disable wandb via CLI:
```bash
uv run fvspec --no-wandb
```

### A/B Testing (Variant Comparison)

Compare multiple variants with wandb tracking:
```bash
uv run fvspec compare-variants --variant control-functional --variant terse-functional --wandb
```

The comparison runs will be grouped together in wandb, making it easy to compare metrics across variants.

## Metrics Logged

wandb automatically tracks all the metrics computed by the benchmark:

### Per-Sample Metrics (logged for each sample)

**Performance:**
- `token_usage` - Total tokens used
- `time` - Execution time in seconds
- `num_messages` - Total messages exchanged
- `num_generate_messages` - Number of model responses
- `num_input_messages` - Number of user messages

**Code Quality:**
- `success` - Whether valid Lean code was generated (1/0)
- `num_sorries` - Number of `sorry` placeholders
- `lines_pbt` - Lines in original Python test
- `lines_code` - Lines of generated Lean code
- `percent_lines_added` - Percent lines added relative to Python

**Subjective Metrics (AI self-reported):**
- `faithfulness_subjective` - How faithful the spec is to the test (0-10)
- `interest_subjective` - Complexity/interest of the problem (0-10)

**Structural Faithfulness (computed):**
- `structural_faithfulness_overall` - Weighted average of structural metrics
- `parameter_coverage` - Fraction of Python parameters found in Lean
- `type_correspondence` - Fraction of types correctly mapped
- `strategy_coverage` - Fraction of Hypothesis bounds captured
- `assertion_coverage` - Ratio of Lean properties to Python assertions
- `dependency_coverage` - Fraction of dependencies referenced

### Summary Metrics (logged at run completion)

Aggregate statistics computed across all samples:
- `summary/total_samples` - Total number of samples evaluated
- `summary/success_rate` - Fraction of successful samples
- `summary/mean_token_usage` - Average tokens per sample
- `summary/std_token_usage` - Standard deviation of token usage
- `summary/mean_time` - Average execution time
- `summary/std_time` - Standard deviation of time
- `summary/mean_num_sorries` - Average placeholders per sample
- `summary/mean_lines_code` - Average lines of code generated
- `summary/mean_faithfulness_subjective` - Average AI-reported faithfulness
- `summary/std_faithfulness_subjective` - Std dev of faithfulness
- `summary/mean_interest_subjective` - Average AI-reported interest
- `summary/std_interest_subjective` - Std dev of interest
- `summary/mean_structural_faithfulness` - Average structural faithfulness
- `summary/std_structural_faithfulness` - Std dev of structural faithfulness

## Artifacts

When `log_code` and `log_qa` are enabled in config:
- Generated Lean code files (`Spec.lean`) are logged as artifacts
- Quality assessment JSON files (`qa.json`) are logged as artifacts

## wandb Dashboard Features

Once your runs are logged to wandb, you can:

1. **Compare variants side-by-side** - View metrics across different prompt variants
2. **Track metrics over time** - See how performance changes across runs
3. **Visualize distributions** - Plot histograms of metrics like token usage, faithfulness
4. **Filter and group runs** - Use tags and groups to organize experiments
5. **Export data** - Download metrics for custom analysis
6. **Share results** - Create public reports for collaboration

## Configuration Options

### In `config.toml`

```toml
[wandb]
# Enable or disable wandb logging
enabled = false

# Project name in wandb (creates project if it doesn't exist)
project = "fvspec"

# Entity/team name (optional, defaults to your personal workspace)
# entity = "your-team"

# Tags to apply to all runs (can also add via CLI)
tags = []

# Log generated Lean code files as artifacts
log_code = true

# Log quality assessment JSON files as artifacts
log_qa = true
```

### Via CLI

```bash
# Enable/disable wandb
--wandb / --no-wandb

# Set project name
--wandb-project my-project

# Set entity
--wandb-entity my-team

# Add tags (can specify multiple times)
--wandb-tag experiment-1 --wandb-tag ablation-study
```

## Artifact Organization

The benchmark organizes outputs in a clean directory structure:

- `artifacts/runs/` - Benchmark run outputs
  - `2025-10-22T15-30-00__variant_control-functional/` - Timestamped run directories
  - `comparison_2025-10-22T16-00-00/` - Multi-variant comparison runs
- `artifacts/wandb/` - wandb cache and logs
  - Managed automatically by wandb
  - Can be safely deleted to free up space

## Example Workflow

1. **Initial baseline:**
   ```bash
   uv run fvspec --wandb --wandb-tag baseline --variant control-functional --sample-size 100
   ```

   Results will be in `artifacts/runs/<timestamp>__variant_control-functional/`

2. **Test new variant:**
   ```bash
   uv run fvspec --wandb --wandb-tag new-approach --variant terse-functional --sample-size 100
   ```

   Results will be in `artifacts/runs/<timestamp>__variant_terse-functional/`

3. **Compare in wandb dashboard:**
   - Navigate to your project in wandb
   - Select both runs
   - Use "Compare" view to see metrics side-by-side

4. **Run formal A/B test:**
   ```bash
   uv run fvspec compare-variants \
     --variant control-functional \
     --variant terse-functional \
     --sample-size 200 \
     --wandb \
     --wandb-tag formal-comparison
   ```

   Results will be in `artifacts/runs/comparison_<timestamp>/`

## Tips

- **Use tags** to organize experiments by hypothesis, date, or research question
- **Use groups** (automatic for `compare-variants`) to compare related runs
- **Set a consistent project name** across related experiments
- **Review summary metrics first** before diving into per-sample details
- **Create reports** in wandb to document findings for your team
- **Export metrics** to CSV if you need custom statistical analysis

## Troubleshooting

**"wandb not logged in"**: Run `wandb login` and follow the prompts

**Metrics not showing up**: Check that `enabled = true` in config or `--wandb` is passed

**Too many artifacts**: Set `log_code = false` and `log_qa = false` in config to reduce storage

**Comparing variants**: Use `compare-variants` subcommand for proper grouping in wandb
