# Compilation Validation Report

> Generated 2026-03-30 14:56 UTC by `uv run postprod validate`

## Parameters

- **Input**: `fvspec-mar30.jsonl`
- **Total records loaded**: 454
- **Eligible after filtering**: 454
  - `impl_autoform_success >= 1.0`: yes
  - Has both `spec` and `impl`
- **Sample size**: 454 (seed=42)
- **Parallelism**: 8
- **Timeout**: 60s per build
- **Results JSONL**: `fvspec-mar30.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 454 |
| Compiles | 454 (100.0%) |
| Fails | 0 (0.0%) |
| Timeouts | 0 |
| Failure rate 95% CI | 0.4% +/- 0.4% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 0.0 | 431 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 0/431 | 0% |

## Error Categories

_No compilation failures — 100% success._

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|

