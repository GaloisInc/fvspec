# Weights & Biases Integration

The fvspec benchmark integrates with [Weights & Biases](https://wandb.ai/) to provide comprehensive experiment tracking, metric visualization, and artifact management for synthetic data.

## Table of Contents

- [Setup](#setup)
- [Current Implementation](#current-implementation)
  - [Metrics Logging](#metrics-logging)
  - [Artifact Upload](#artifact-upload)
  - [Dependency Cache Sync](#dependency-cache-sync)
- [Architecture Decisions](#architecture-decisions)
- [How It Works](#how-it-works)
  - [Sample Artifact Flow](#sample-artifact-flow)
  - [Dependency Cache Flow](#dependency-cache-flow)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Questions & Concerns](#questions--concerns)
- [Next Steps](#next-steps)

## Setup

1. **Install dependencies** (wandb is included):
   ```bash
   cd benchmark
   uv sync
   ```

2. **Login to wandb**:
   ```bash
   uv run wandb login
   ```
   Follow the prompts to authenticate with your wandb account.

3. **Configure in `config.toml`**:
   ```toml
   [wandb]
   enabled = true
   project = "fvspec"
   entity = "fvspec"  # IMPORTANT: This is the correct team entity - do not change
   tags = ["experiment-1"]
   upload_samples = true
   sync_dep_cache = true
   ```

   **Note:** The `entity = "fvspec"` setting is correct and should not be changed.
   This is the shared team workspace for the project.

## Current Implementation

### Metrics Logging

The benchmark tracks **15 per-sample metrics** and **14 aggregate summary metrics** automatically logged to wandb after each evaluation.

#### Per-Sample Metrics

Logged incrementally as each sample completes:

**Performance metrics:**
- `token_usage` - Total tokens consumed by the model
- `time` - Wall-clock execution time in seconds
- `num_messages` - Total messages in conversation
- `num_generate_messages` - Number of model responses
- `num_input_messages` - Number of user/system messages

**Code quality metrics:**
- `success` - Whether valid Lean code was generated (1 or 0)
- `num_sorries` - Count of `sorry` placeholders in output
- `lines_pbt` - Lines in original Python property-based test
- `lines_code` - Lines of generated Lean code
- `percent_lines_added` - Percentage increase from Python to Lean

**Subjective metrics** (AI self-reported during generation):
- `faithfulness_subjective` - How well the spec captures the test (0-10 scale)
- `interest_subjective` - Complexity/interest of the problem (0-10 scale)

**Structural faithfulness metrics** (computed objectively from code analysis):
- `structural_faithfulness_overall` - Weighted average of all structural metrics
- `parameter_coverage` - Fraction of Python parameters found in Lean signature
- `type_correspondence` - Fraction of parameter types correctly mapped
- `strategy_coverage` - Fraction of Hypothesis strategy bounds captured
- `assertion_coverage` - Ratio of Lean properties to Python assertions
- `dependency_coverage` - Fraction of imported dependencies referenced

#### Summary Metrics

Logged once at run completion with `summary/` prefix:

- `summary/total_samples` - Total samples evaluated
- `summary/success_rate` - Fraction of successful samples
- `summary/mean_token_usage`, `summary/std_token_usage` - Token usage statistics
- `summary/mean_time`, `summary/std_time` - Execution time statistics
- `summary/mean_num_sorries` - Average `sorry` count per successful sample
- `summary/mean_lines_code` - Average lines of generated code
- `summary/mean_faithfulness_subjective`, `summary/std_faithfulness_subjective` - Subjective faithfulness statistics
- `summary/mean_interest_subjective`, `summary/std_interest_subjective` - Subjective interest statistics
- `summary/mean_structural_faithfulness`, `summary/std_structural_faithfulness` - Structural metric statistics

### File Upload (Incremental)

**All synthetic data outputs are uploaded to wandb incrementally**, enabling:
- Recovery from canceled runs (files upload as samples complete)
- Reproducibility and auditing
- Centralized storage for team collaboration
- Easy access via wandb UI "Files" tab

**What gets uploaded per sample:**
- `Spec.lean` - Generated Lean 4 specification code
- `qa.json` - Quality assessment metrics
- `datapoint.json` - Original test metadata and dependencies

**Implementation approach:**
- Uses `run.save(path, base_path=..., policy="now")` for immediate uploads
- Files are associated directly with the wandb run (not stored as artifacts)
- `base_path` parameter preserves directory structure in wandb
- `policy="now"` forces immediate upload vs waiting for run end
- Files appear in wandb UI under "Files" tab for each run

**Key benefit:** If a run is canceled mid-evaluation, all completed samples are already uploaded and accessible in the wandb UI.

**Note:** Artifacts are reserved for versioned datasets (like the dependency cache). Per-sample files use `run.save()` which is wandb's recommended pattern for incremental file uploads during a run.

### Dependency Cache Sync

The benchmark maintains a **shared dependency cache** that stores Lean formalizations of Python dependencies (NumPy, PyTorch, etc.) to avoid redundant generation across runs.

**Hybrid sync strategy:**
1. **Download at run start**: Pull latest `dep-cache:latest` artifact from wandb
2. **Use throughout run**: All samples read from local cache in `artifacts/depcache/`
3. **Upload at run end**: Push updated cache back to wandb as new version

**Why this approach:**
- Bounded wandb API calls (2 per run, not per sample)
- Dependencies are rarely shared between samples in a single run
- Cache is most valuable across runs (not within a run)
- Simpler implementation with predictable performance

**Artifact details:**
- Artifact type: `dependency-cache`
- Naming: `dep-cache` (wandb manages versioning with `:latest` alias)
- Contains: All cached Lean modules with metadata JSON files

**Comparison runs:** Only the first logger downloads, only the first logger uploads (cache is shared across all variants in a comparison).

## Architecture Decisions

### Why run.save() Instead of Artifacts?

**Alternative considered:** Single run artifact that grows incrementally
- ❌ wandb artifacts are immutable once logged (can't add files after `log_artifact()`)
- ❌ Would require creating new artifact versions for each sample
- ❌ Artifacts designed for versioned datasets, not incremental uploads

**Chosen approach:** `run.save()` for direct file uploads
- ✅ Files upload immediately as samples complete
- ✅ Preserved even if run is canceled
- ✅ Visible in wandb UI under "Files" tab
- ✅ Aligns with wandb's recommended pattern for incremental uploads
- ✅ Simpler implementation, no finalization issues

**Artifacts still used for:** Dependency cache (single upload at end, versioned dataset)

### Why Serial Uploads?

**Current implementation:** Sample files uploaded synchronously after each completion

**Why not async (trio/asyncio)?**
- Initial implementation focuses on correctness
- Serial uploads ensure proper ordering and error handling
- Performance impact is low (uploads happen in background)
- **Deferred:** Async optimization with trio planned for future iteration

### Why Hybrid Cache Sync?

**Alternative A: Download at start, upload at end** ✅ **CHOSEN**
- Bounded API calls (2 per run)
- Cache valuable across runs, not within runs
- Simple and predictable

**Alternative B: Per-sample uploads**
- ❌ Would require O(n) API calls for n samples
- ❌ Dependencies rarely shared between samples in one run
- ❌ Adds complexity without proportional benefit

**Alternative C: No sync**
- ❌ Loses collaboration benefits
- ❌ Every developer regenerates same dependencies
- ❌ Defeats purpose of caching

## How It Works

### Sample File Upload Flow

```
1. Benchmark starts → WandbLogger.init_run()
   └─ Initialize wandb.Run with project/entity/tags

2. For each sample:
   ├─ Agent generates Lean code
   ├─ write_to_disk() extracts code, computes QA metrics
   ├─ log_sample_to_wandb(state)
   │  ├─ logger.log_sample_metrics(qa)  # Log to run history
   │  └─ logger.log_sample_to_artifact(sample_dir, sample_id)
   │     ├─ run.save("sample_42/Spec.lean", base_path=..., policy="now")
   │     ├─ run.save("sample_42/qa.json", base_path=..., policy="now")
   │     └─ run.save("sample_42/datapoint.json", base_path=..., policy="now")
   │        # Files upload immediately to wandb

3. Run completes → logger.finish()
   ├─ log_summary_metrics(all_qa)  # Compute and log aggregates
   └─ run.finish()  # Finalize wandb run
```

**Key insight:** `run.save()` uploads files immediately to the wandb run. Files are associated with the run (not stored as versioned artifacts), making them perfect for incremental uploads that survive canceled runs.

**File organization in wandb UI:**
Files appear under the "Files" tab for each run, organized by sample directory:
```
Files/
├── sample_0_test_numpy_array/
│   ├── Spec.lean
│   ├── qa.json
│   └── datapoint.json
├── sample_1_test_pytorch_model/
│   ├── Spec.lean
│   ├── qa.json
│   └── datapoint.json
└── ... (one directory per sample)
```

### Dependency Cache Flow

```
1. CLI invokes fvspec → load WandbConfig

2. If sync_dep_cache enabled:
   ├─ logger.init_run(...)
   └─ logger.download_dep_cache()
      ├─ run.use_artifact("dep-cache:latest")
      ├─ artifact.download(root="artifacts/depcache")
      └─ Returns Path or None if artifact doesn't exist

3. During evaluation:
   └─ Samples read from artifacts/depcache/ as needed
      (formalize/impl/cache.py handles cache reads/writes)

4. Run completes (in finally block):
   └─ If sync_dep_cache enabled:
      └─ logger.upload_dep_cache()
         ├─ Create wandb.Artifact(name="dep-cache", type="dependency-cache")
         ├─ artifact.add_dir("artifacts/depcache")
         └─ run.log_artifact(artifact)  # New version pushed
```

**Cache structure:**
```
artifacts/depcache/
├── {sha256_hash_1}/
│   ├── NumpyArrayOps.lean
│   └── metadata.json
├── {sha256_hash_2}/
│   ├── TorchTensorOps.lean
│   └── metadata.json
└── ... (one directory per cached dependency)
```

**Metadata tracks:**
- `dep_name` - Original Python dependency name
- `lean_module` - Generated Lean module name
- `source_hash` - SHA256 of Python source code
- `variant` - Prompt variant used for generation
- `status` - "ok", "failed", or "stub"
- `provenance` - Model, run_id, attempts, diagnostics

## Configuration

### In `config.toml`

```toml
[wandb]
# Enable wandb logging
enabled = true

# Project name (creates if doesn't exist)
project = "fvspec"

# Entity/team name - IMPORTANT: Use "fvspec" for the shared team workspace
# Do NOT change this value - it ensures all team members share artifacts and runs
entity = "fvspec"

# Tags applied to all runs
tags = ["experiment-1", "baseline"]

# Upload all sample outputs as artifacts (Spec.lean, qa.json, datapoint.json)
upload_samples = true

# Sync dependency cache (download at start, upload at end)
sync_dep_cache = true
```

> **⚠️ Important:** The `entity` should always be set to `"fvspec"` for team collaboration.
> This ensures all runs, artifacts, and cache are stored in the shared team workspace.
> Do not change this to your personal entity.

### Via CLI

```bash
# Disable wandb (default is enabled)
--wandb-disable

# Set project name
--wandb-project my-project

# Set entity
--wandb-entity my-team

# Add tags (can specify multiple times)
--wandb-tag experiment-1 --wandb-tag ablation-study
```

**Note:**
- Wandb is **enabled by default** unless `--wandb-disable` flag is specified
- `upload_samples` and `sync_dep_cache` can only be configured via `config.toml` (no CLI flags yet)

## Usage Examples

### Basic Run with wandb Enabled

```bash
uv run fvspec --variant control-functional --sample-size 100
```

If `config.toml` has `enabled = true`, this automatically:
- Logs all per-sample metrics during evaluation
- Uploads sample artifacts incrementally
- Downloads dep cache at start
- Uploads dep cache at end
- Logs summary metrics on completion

Output structure:
```
artifacts/
├── runs/2025-10-22T15-30-00__control-functional/
│   ├── sample_0_test_example/
│   │   ├── Spec.lean
│   │   ├── qa.json
│   │   └── datapoint.json
│   └── ...
├── depcache/
│   └── {hash}/...
└── wandb/
    └── ... (wandb internal files)
```

### A/B Variant Comparison

```bash
uv run fvspec compare-variants \
  --variant control-functional \
  --variant terse-functional \
  --sample-size 200 \
  --wandb-tag comparison-study
```

Behavior:
- Both variants share a wandb group for easy comparison
- Run names: `{group}__{variant}__{timestamp}`
- Single cache download at start (first logger)
- Single cache upload at end (first logger)
- Each variant gets its own run artifact

### Disable Artifact Upload

If you want metrics but not artifacts (save storage):

```toml
[wandb]
enabled = true
upload_samples = false  # No sample artifacts
sync_dep_cache = false  # No cache sync
```

This logs all metrics to wandb but doesn't upload any files.

### View Results

```bash
# View all runs in wandb web UI
# Navigate to https://wandb.ai/{entity}/{project}

# Or use inspect's local viewer
uv run inspect view --log-dir artifacts/runs
```

## Cache Management

The dependency cache can be managed both locally and remotely via wandb. This is useful when:
- Starting fresh experiments with clean cache state
- Debugging cache corruption issues
- Coordinating cache state across team members
- Force regenerating dependencies with updated models/prompts

### Commands

**Clear local cache:**
```bash
uv run fvspec deps cache-clear-local
```
Deletes all cached dependencies from `artifacts/depcache/`. Next run will regenerate from scratch or download from wandb.

**Clear remote wandb cache:**
```bash
uv run fvspec deps cache-clear-wandb
```
Deletes the `dep-cache:latest` artifact from wandb. Requires `wandb.enabled = true` in config. Next run will create a fresh cache artifact.

**Force regeneration:**
```bash
# Main benchmark run
uv run fvspec --force-regen --sample-size 10

# Dependency autoformalization
uv run fvspec deps autoformalize --force-regen --sample-id 42
```
Ignores cache and regenerates all dependencies from scratch. Overwrites existing cache entries on hash collision. When combined with wandb sync, uploads the regenerated cache at the end.

### Workflows

**Full cache reset (local + remote):**
```bash
# 1. Clear local cache
uv run fvspec deps cache-clear-local

# 2. Clear remote cache (optional - for team coordination)
uv run fvspec deps cache-clear-wandb

# 3. Run with fresh generation
uv run fvspec --force-deps-regen --sample-size 10
```

**Force regenerate without affecting remote cache:**
```bash
# Clears local, skips download, regenerates, uploads to wandb
uv run fvspec --force-deps-regen --sample-size 10
```

**Selective regeneration:**
```bash
# Regenerate dependencies for specific datapoints
uv run fvspec deps autoformalize --force-deps-regen --sample-id 5 --sample-id 42
```

### Behavior Details

**`--force-deps-regen` flag:**
1. Clears local cache at run start
2. Skips wandb cache download (if `sync_dep_cache = true`)
3. Marks all dependencies as uncached, forcing regeneration
4. Overwrites cache entries on hash collision (last write wins)
5. Uploads regenerated cache to wandb at run end (if enabled)

**`cache-clear-wandb` command:**
- Uses wandb API to delete the artifact
- Gracefully handles missing artifacts (first run case)
- Requires `wandb.enabled = true` in config
- Next run creates new `:v0` artifact

**Cache collision handling:**
When `--force-deps-regen` is used and a dependency hash collides with an existing cache entry, the new generation overwrites the old one. This is intentional - allows updating cached dependencies with improved models or prompts.

## Questions & Concerns

### Storage Scaling

**Concern:** With `upload_samples = true`, every run uploads hundreds of samples × 3 files each. A 100-sample run uploads ~300 files.

**Questions:**
- How quickly will we hit wandb storage limits?
- Should we implement configurable file filtering (e.g., only upload qa.json)?
- Do we need artifact cleanup policies (delete old runs)?

**Mitigation ideas:**
- Monitor storage usage in early testing
- Add `--upload-filter` CLI flag to select which files to upload
- Document storage usage patterns in README
- Consider archiving old artifacts after analysis

### Async Upload Performance

**Current:** Serial uploads with `run.log_artifact()` after each sample

**Question:** Is the synchronous approach causing noticeable slowdown?

**Next steps:**
- Measure upload time per sample in real runs
- If >100ms per sample, consider trio async refactor
- wandb uploads happen in background, so impact may be minimal

**Trio refactor considerations:**
- Need to ensure artifact consistency (no concurrent modifications)
- Queue-based approach: upload task pulls from completed samples queue
- Error handling: retry logic for failed uploads

### File Deduplication

**Current:** Files uploaded with `run.save()` for each sample

**Questions:**
- Does wandb deduplicate identical files automatically?
- How much storage do repeated runs consume?
- Should we implement client-side deduplication?

**Testing needed:**
- Upload same run twice, verify storage usage
- Check if wandb's content-addressed storage deduplicates files
- Monitor storage consumption patterns

### Dependency Cache Conflicts

**Current:** Hybrid sync (download/upload at run boundaries)

**Potential issue:** If multiple runs execute concurrently, they might upload conflicting cache versions.

**Questions:**
- Should we implement cache locking?
- Is "last write wins" acceptable for cache artifacts?
- Do we need to merge cache artifacts intelligently?

**Current mitigation:** Cache entries are content-addressed (SHA256 keyed), so conflicts are unlikely. Even if two runs upload different caches, they'll merge naturally on next download.

### Configuration Complexity

**Observation:** Configuration is clean with clear field names (`upload_samples`, `sync_dep_cache`)

**Approach:** Keep configuration simple and well-documented in WANDB.md and config.toml comments.

### Test Isolation

**Current:** `conftest.py` sets `WANDB_MODE=disabled` for all tests

**Question:** Should we have integration tests that actually test wandb upload?

**Considerations:**
- Requires wandb auth in CI
- Potential for flaky tests (network issues)
- Storage costs for test artifacts

**Approach:** Manual testing for now, consider mocked wandb API for unit tests.

## Next Steps

### Immediate (This Week)

1. **Test with real run**
   - [x] Run `uv run fvspec --sample-size 10` with wandb enabled
   - [x] Verify artifacts appear in wandb UI
   - [x] Check artifact file structure and completeness
   - [ ] Monitor upload time per sample
   - [ ] Verify cache download/upload works

2. **Monitor storage usage**
   - [ ] Track wandb storage consumption after first few runs
   - [ ] Calculate storage per sample (estimate for 1000-sample runs)
   - [ ] Document storage recommendations in README

3. **Validate artifact integrity**
   - [ ] Download artifact from wandb
   - [ ] Verify all sample files are present and correct
   - [ ] Test dep cache restore from artifact

### Short Term (This Month)

4. **Add artifact filtering**
   - [ ] Implement `--upload-filter` CLI flag
   - [ ] Support patterns: `*.lean`, `*.json`, `qa.json`
   - [ ] Document filtering options

5. **Documentation updates**
   - [ ] Add wandb storage recommendations to main README
   - [ ] Document artifact organization and browsing
   - [ ] Create troubleshooting guide for upload issues

### Medium Term (Next Quarter)

6. **Async upload optimization**
   - [ ] Measure upload overhead in real runs
   - [ ] If >100ms/sample, implement trio-based async uploads
   - [ ] Add upload queue with configurable batch size
   - [ ] Ensure error handling and retry logic

7. **Cache conflict resolution**
   - [ ] Test concurrent runs writing to cache
   - [ ] Implement cache merging if needed
   - [ ] Add cache validation checks

8. **Artifact cleanup policies**
   - [ ] Design artifact retention policy (keep last N versions?)
   - [ ] Implement CLI command for artifact cleanup
   - [ ] Add automated cleanup option

### Long Term (Future Work)

9. **Enhanced metrics**
   - [ ] Track API rate limit consumption
   - [ ] Log dependency generation success rates

10. **Artifact comparison tools**
    - [ ] CLI command to diff artifacts between runs
    - [ ] Visualize metric changes over artifact versions
    - [ ] Generate comparison reports

11. **Integration with other tools**
    - [ ] Export metrics to MLflow format
    - [ ] Support for custom wandb dashboards
    - [ ] Automated report generation

## Troubleshooting

### Metrics not appearing
- Verify `enabled = true` in `config.toml` (wandb is enabled by default via CLI)
- Check for errors in console output
- Verify wandb dashboard for your project

### Artifact upload failures
- Check network connectivity
- Verify wandb storage quota not exceeded
- Look for error messages in console output
- Try `--wandb-disable` flag to isolate issue

### Nested wandb directories
The integration correctly uses `dir="artifacts"` so wandb creates `artifacts/wandb/`. If you see `artifacts/wandb/wandb/`, delete the nested directory.

### Tests creating artifacts
Tests automatically disable wandb via `conftest.py`. If you see test artifacts:
1. Verify `conftest.py` exists in `src/tests/`
2. Check `WANDB_MODE` environment variable isn't overridden
3. Run `pytest --verbose` to see fixture status

### Cache download fails
If `download_dep_cache()` fails:
- This is expected on first run (artifact doesn't exist yet)
- Check console for "Note: Could not download dep cache" message
- Verify `sync_dep_cache = true` in config
- Artifact will be created after first successful run
