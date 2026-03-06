# Compilation Validation Report

> Generated 2026-03-06 18:52 UTC by `uv run postprod validate`

## Parameters

- **Input**: `fvspec.jsonl`
- **Total records loaded**: 13313
- **Eligible after filtering**: 9675
  - `impl_autoform_success >= 1.0`: yes
  - Has both `spec` and `impl`
- **Sample size**: 400 (seed=42)
- **Parallelism**: 8
- **Timeout**: 60s per build
- **Results JSONL**: `fvspec.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 400 |
| Compiles | 190 (47.5%) |
| Fails | 210 (52.5%) |
| Timeouts | 0 |
| Failure rate 95% CI | 52.5% +/- 4.9% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 15.0 | 190 |
| Non-compiling | 15.4 | 210 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 39/84 | 46% |
| 11-15 | 83/162 | 51% |
| 16-20 | 55/92 | 60% |
| 21-30 | 31/53 | 58% |
| 31-50 | 2/9 | 22% |

### Failure Rate by Tool Calls

| Tool calls | Fails / Total | Rate |
|-----------|--------------|------|
| 0-5 | 11/24 | 46% |
| 6-10 | 85/170 | 50% |
| 11-20 | 94/169 | 56% |
| 21-50 | 20/37 | 54% |

## Error Categories

| Category | Count | % of failures |
|----------|-------|--------------|
| unknown identifier / namespace | 82 | 39% |
| failed to synthesize | 38 | 18% |
| syntax error | 34 | 16% |
| type mismatch | 28 | 13% |
| other | 23 | 11% |
| termination / well-founded | 3 | 1% |
| application error | 1 | 0% |
| declaration error | 1 | 0% |

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|
| 210 | `error:build failed` |
| 208 | `error:Lean exited with code 1` |
| 8 | `error:Fvspec/Impl.lean:51:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 7 | `error:Fvspec/Impl.lean:57:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:26:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:151:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime` |
| 4 | `error:Fvspec/Impl.lean:99:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:37:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:38:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:40:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |

