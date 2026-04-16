# Compilation Validation Report

> Generated 2026-04-16 12:22 UTC by `uv run postprod validate`

## Parameters

- **Input**: `feb03_sample200.jsonl`
- **Total records loaded**: 200
- **Eligible after filtering**: 200
  - `impl_autoform_success >= 1.0`: no
  - Has both `spec` and `impl`
- **Sample size**: 200 (seed=42)
- **Parallelism**: 8
- **Timeout**: 120s per build
- **Results JSONL**: `feb03_sample200.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 200 |
| Compiles | 200 (100.0%) |
| Fails | 0 (0.0%) |
| Timeouts | 0 |
| Failure rate 95% CI | 0.9% +/- 0.9% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 13.4 | 200 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 0/70 | 0% |
| 11-15 | 0/73 | 0% |
| 16-20 | 0/33 | 0% |
| 21-30 | 0/21 | 0% |
| 31-50 | 0/3 | 0% |

## Error Categories

_No compilation failures — 100% success._

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|

