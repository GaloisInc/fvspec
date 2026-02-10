# Metrics: Lean Code Analysis

Post-production tool that computes structure and complexity metrics for Lean code in benchmark samples.

## Overview

The metrics tool analyzes Lean code (Spec.lean, Impl.lean, Tests.lean) and augments each sample with:

1. **Structure Metrics**: Line counts, declaration counts (axioms, defs, theorems), proof quality indicators (sorries, admits), special constructs (eval statements, imports)

2. **Complexity Metrics**: Nesting depth, proof term size, proof steps, dependencies, parameter counts, Halstead complexity measures

**Philosophy**: Unlike the grader (which uses LLM judgment), this tool uses static analysis to extract objective, reproducible metrics from Lean code. These metrics help evaluate:
- Code quality and completeness
- Proof complexity and difficulty
- Generation success patterns
- Architectural decisions (axioms vs definitions)

## Usage

### Basic Usage

From the `benchmark/` directory:

```bash
# Compute metrics for all missing samples (automatically skips already-computed)
uv run metrics artifacts/dataset-out/fvspec.jsonl

# Resume a partial run (only computes samples missing metrics)
uv run metrics artifacts/dataset-out/fvspec.metrics.jsonl

# Specify output file
uv run metrics input.jsonl --output metrics.jsonl

# Test with a small limit
uv run metrics input.jsonl --limit 10

# Retry failed samples (computes missing + retries errors)
uv run metrics input.jsonl --retry-failed
```

### Range-Based Computation

Compute metrics for specific ranges using `--start-idx` and `--stop-idx` (0-based indexing):

```bash
# Compute metrics for samples 100-199 (inclusive start, exclusive stop)
uv run metrics input.jsonl --start-idx 100 --stop-idx 200

# Resume from sample 500 to end
uv run metrics input.jsonl --start-idx 500

# Compute up to sample 1000 (0-999)
uv run metrics input.jsonl --stop-idx 1000

# Retry errors in specific range
uv run metrics input.metrics.jsonl --retry-failed --start-idx 500 --stop-idx 1000
```

**Parallelization with ranges**: Split large datasets for parallel processing:

```bash
# Split 10,000 samples into 4 parallel workers
# Terminal 1
uv run metrics input.jsonl --start-idx 0 --stop-idx 2500 -o output-1.jsonl

# Terminal 2
uv run metrics input.jsonl --start-idx 2500 --stop-idx 5000 -o output-2.jsonl

# Terminal 3
uv run metrics input.jsonl --start-idx 5000 --stop-idx 7500 -o output-3.jsonl

# Terminal 4
uv run metrics input.jsonl --start-idx 7500 -o output-4.jsonl

# Then merge the metric-annotated chunks if needed
```

### Options

- `--output, -o`: Output file path (default: `<input>.metrics.jsonl`)
- `--limit, -n`: Compute only first N missing samples (mutually exclusive with `--start-idx`/`--stop-idx`)
- `--start-idx`: Start computing from this index (0-based, inclusive)
- `--stop-idx`: Stop computing at this index (0-based, exclusive)
- `--retry-failed`: Also retry samples with `metrics_error` field (default: only compute missing samples)

**Default behavior**:
- **Resume-safe**: Automatically computes metrics for samples missing them
- **Skips already-computed**: Samples with metrics pass through unchanged
- **Complete copy**: All samples written to output, only missing ones computed

**Notes**:
- `--limit` and `--start-idx`/`--stop-idx` are mutually exclusive (validation enforced)
- `--retry-failed` adds error retry to default missing-sample behavior
- Computation is fast (~100-1000 samples/second) since it's regex-based parsing

## Output Format

**Important**: The output file is a **complete copy** of the input file. All samples are written to the output.

**What gets computed by default**: Samples missing both `lean_metrics` and `metrics_metadata` fields (resume-safe behavior). Already-computed samples pass through unchanged. Use `--retry-failed` to also retry samples with `metrics_error`.

Each sample is augmented with the following fields:

```json
{
  "lean_metrics": {
    "spec_structure": {
      "total_lines": 120,
      "code_lines": 95,
      "blank_lines": 15,
      "comment_lines": 10,
      "num_axioms": 8,
      "num_defs": 2,
      "num_theorems": 4,
      "num_lemmas": 1,
      "num_structures": 1,
      "num_inductives": 0,
      "num_sorries": 4,
      "num_admits": 0,
      "num_axiomized_defs": 6,
      "num_eval_statements": 0,
      "num_imports": 2,
      "num_namespace_blocks": 1
    },
    "spec_complexity": {
      "max_nesting_depth": 5,
      "avg_nesting_depth": 2.8,
      "max_term_size": 45,
      "avg_term_size": 18.3,
      "total_proof_tokens": 220,
      "avg_proof_steps": 3.2,
      "max_proof_steps": 8,
      "num_dependencies": 12,
      "avg_dependencies_per_decl": 1.7,
      "avg_param_count": 4.5,
      "max_param_count": 8,
      "halstead_vocabulary": 42,
      "halstead_length": 156,
      "halstead_volume": 853.2,
      "halstead_difficulty": 8.4,
      "halstead_effort": 7166.9,
      "halstead_time": 398.2,
      "halstead_bugs": 0.284
    },
    "impl_structure": {...},
    "impl_complexity": {...},
    "tests_structure": {...},
    "tests_complexity": {...},
    "total_lean_lines": 320,
    "total_sorries": 12,
    "total_axioms": 15
  },
  "metrics_metadata": {
    "version": "1.0.0",
    "timestamp": "2025-01-23T12:34:56.789Z",
    "computation_time_seconds": 0.025,
    "spec_available": true,
    "impl_available": true,
    "tests_available": false
  }
}
```

If computation fails, a `metrics_error` field is added with the error message.

## Metrics Explained

### Structure Metrics

**Line counts:**
- `total_lines`: All lines including blank and comments
- `code_lines`: Lines with actual code (excluding blank/comment)
- `blank_lines`: Empty lines
- `comment_lines`: Lines starting with `--` or `/-`

**Declarations:**
- `num_axioms`: Axiom declarations (ideally should be minimal)
- `num_defs`: Function/value definitions
- `num_theorems`: Theorem declarations
- `num_lemmas`: Lemma declarations
- `num_structures`: Structure type definitions
- `num_inductives`: Inductive type definitions

**Proof quality:**
- `num_sorries`: Sorry placeholders (unproven theorems)
- `num_admits`: Admit tactics (alternative to sorry)
- `num_axiomized_defs`: Axioms that look like they should be definitions (quality indicator)

**Special constructs:**
- `num_eval_statements`: `#eval` statements (computability checks)
- `num_imports`: Import statements
- `num_namespace_blocks`: Namespace declarations

### Complexity Metrics

**Nesting and depth:**
- `max_nesting_depth`: Maximum parentheses/bracket nesting depth
- `avg_nesting_depth`: Average nesting depth across all proofs

**Term size:**
- `max_term_size`: Token count of largest proof term
- `avg_term_size`: Average proof term size
- `total_proof_tokens`: Total tokens across all proofs

**Proof complexity:**
- `avg_proof_steps`: Average tactic invocations per proof
- `max_proof_steps`: Maximum tactic steps in any proof

**Dependencies:**
- `num_dependencies`: Count of external definitions/theorems referenced
- `avg_dependencies_per_decl`: Average dependencies per declaration

**Signatures:**
- `avg_param_count`: Average parameters per function/theorem
- `max_param_count`: Maximum parameters in any declaration

**Halstead complexity:**
- `halstead_vocabulary`: Number of unique operators and operands (n = n1 + n2)
- `halstead_length`: Total number of operators and operands (N = N1 + N2)
- `halstead_volume`: Program volume (V = N × log₂(n))
- `halstead_difficulty`: Difficulty to understand/maintain (D = (n1/2) × (N2/n2))
- `halstead_effort`: Effort required to implement (E = D × V)
- `halstead_time`: Time to implement in seconds (T = E / 18)
- `halstead_bugs`: Expected number of bugs (B = V / 3000)

**Note**: Halstead metrics are computed from operators (keywords, symbols like `def`, `theorem`, `+`, `→`, etc.) and operands (identifiers, literals). These metrics were originally developed for imperative languages but provide useful complexity indicators for functional/logical code as well.

## Performance

- **Speed**: ~100-1000 samples/second (regex-based parsing)
- **Memory**: Loads entire JSONL into memory (~1GB for 10k samples)
- **Parallelization**: Not yet implemented, use range-based manual parallelization

For large datasets (>10k samples), consider splitting into ranges and processing in parallel terminals.

## Resume and Retry Workflow

The tool automatically resumes partial runs by computing only missing metrics:

```bash
# Step 1: Initial computation (partial completion)
uv run metrics artifacts/dataset-out/fvspec.jsonl
# Creates: fvspec.metrics.jsonl
# Some samples computed, some may have metrics_error, some missing

# Step 2: Resume - computes all missing samples automatically
uv run metrics artifacts/dataset-out/fvspec.metrics.jsonl
# Automatically finds and computes samples missing metrics
# Skips already-computed samples

# Step 3: Check for errors
grep -c "metrics_error" artifacts/dataset-out/fvspec.metrics.jsonl

# Step 4: Retry errors (if any exist)
uv run metrics artifacts/dataset-out/fvspec.metrics.jsonl --retry-failed
# Computes missing samples + retries samples with metrics_error

# Step 5: Verify all succeeded
grep -c "metrics_error" artifacts/dataset-out/fvspec.metrics.jsonl
# Should be 0
```

**Range-based resume/retry**:

```bash
# Resume from specific point
uv run metrics input.metrics.jsonl --start-idx 1000

# Retry errors in specific range
uv run metrics input.metrics.jsonl --retry-failed --start-idx 1000 --stop-idx 2000
```

**Key insight**: The default behavior is resume-safe. Just re-run the tool on a partial file and it will automatically complete the missing samples.

## Workflow Integration

The metrics tool fits into the postproduction pipeline:

```bash
# 1. Merge and deduplicate runs
uv run merge src/scripts/postproduction/merge/runs.txt
# Creates: artifacts/dataset-out/fvspec.jsonl

# 2. Compute Lean metrics
uv run metrics artifacts/dataset-out/fvspec.jsonl
# Creates: artifacts/dataset-out/fvspec.metrics.jsonl

# 3. Grade samples for difficulty (optional)
uv run grader artifacts/dataset-out/fvspec.metrics.jsonl
# Creates: artifacts/dataset-out/fvspec.metrics.graded.jsonl

# 4. Analyze results with metrics-aware queries
```

**Order flexibility**: You can run metrics before or after grader - they're independent. However, computing metrics first can help identify patterns before grading.

## Use Cases

### Analyze proof completeness

```bash
# Compute metrics and check sorry counts
uv run metrics input.jsonl -o output.jsonl
jq '.lean_metrics.total_sorries' output.jsonl | sort -n | uniq -c
```

### Compare spec vs impl complexity

```bash
# Extract complexity comparisons
jq '{id: .sample_id, spec_lines: .lean_metrics.spec_structure.code_lines, impl_lines: .lean_metrics.impl_structure.code_lines}' output.jsonl
```

### Find samples with high axiom usage

```bash
# Identify samples relying heavily on axioms
jq 'select(.lean_metrics.total_axioms > 10) | {id: .sample_id, axioms: .lean_metrics.total_axioms}' output.jsonl
```

### Identify trivial proofs

```bash
# Find samples with low complexity
jq 'select(.lean_metrics.spec_complexity.avg_proof_steps < 2)' output.jsonl
```

## Architecture

- **Pure Python**: No external dependencies beyond standard libraries
- **Regex-based**: Fast pattern matching for Lean constructs
- **Incremental output**: Writes samples as computed (resume-friendly)
- **Error handling**: Failed samples written with `metrics_error` field

## Files

- `__init__.py` - Typer CLI entry point
- `models.py` - Pydantic models (StructureMetrics, ComplexityMetrics, LeanCodeMetrics, MetricsMetadata)
- `lean_parser.py` - Regex-based Lean code parsing and metrics extraction
- `processor.py` - JSONL processing orchestration
- `README.md` - This file

## Customization

### Adding New Metrics

To add new metrics:

1. **Update models** (`models.py`):
   ```python
   class StructureMetrics(BaseModel):
       # Add new field
       num_custom_construct: int = Field(description="...")
   ```

2. **Update parser** (`lean_parser.py`):
   ```python
   def extract_structure_metrics(lean_code: str) -> StructureMetrics:
       # Add extraction logic
       num_custom = len(re.findall(r"pattern", lean_code))

       return StructureMetrics(
           ...,
           num_custom_construct=num_custom,
       )
   ```

3. **Re-run metrics computation** on existing data

### Import Style

All imports use absolute paths (`from scripts.postproduction.metrics.X import Y`) for clarity and IDE support.

## Limitations

- **Regex-based**: Doesn't use full Lean parser, so complex patterns may be missed
- **No semantic analysis**: Counts syntactic constructs, doesn't understand proof semantics
- **Limited type analysis**: Can't extract full type signatures or check type correctness
- **No LSP integration**: Doesn't use Lean LSP for validation

For more sophisticated analysis, consider using Lean's metaprogramming APIs or LSP.

## Comparison with Existing Metrics

The benchmark already computes some metrics during generation (in `qa.json`):
- `num_sorries`: Total sorry count (duplicated here for convenience)
- `num_theorems`: Theorem count (duplicated here with more detail)
- `lines_code`: Total lines (less detailed than our structure metrics)

**Why compute again?**
1. **Separation of concerns**: Generation vs postproduction analysis
2. **More detail**: Per-file breakdown, complexity metrics not available during generation
3. **Recomputation**: Can recompute metrics after manual edits to Lean files
4. **Consistency**: Uniform metrics across merged datasets from different runs

## Notes

- **Idempotent**: Safe to re-run with same inputs (overwrites output file)
- **Fast**: Regex-based parsing is much faster than LLM-based grading
- **Gitignored**: Output directory `artifacts/dataset-out/` is gitignored
- **Memory**: Entire JSONL loaded into memory (typically <1GB for 10k samples)
- **Versioned**: Metrics version tracked in metadata for reproducibility
