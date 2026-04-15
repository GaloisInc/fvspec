# Compilation Validation Report

> Generated 2026-04-09 13:39 UTC by `uv run postprod validate`

## Parameters

- **Input**: `fvspec-merged.jsonl`
- **Total records loaded**: 16749
- **Eligible after filtering**: 13111
  - `impl_autoform_success >= 1.0`: yes
  - Has both `spec` and `impl`
- **Sample size**: 400 (seed=42)
- **Parallelism**: 8
- **Timeout**: 60s per build
- **Results JSONL**: `fvspec-merged.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 400 |
| Compiles | 243 (60.8%) |
| Fails | 157 (39.2%) |
| Timeouts | 0 |
| Failure rate 95% CI | 39.4% +/- 4.8% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 10.4 | 208 |
| Non-compiling | 15.6 | 157 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 30/127 | 24% |
| 11-15 | 59/120 | 49% |
| 16-20 | 41/68 | 60% |
| 21-30 | 25/43 | 58% |
| 31-50 | 2/7 | 29% |

## Error Categories

| Category | Count | % of failures |
|----------|-------|--------------|
| unknown identifier / namespace | 63 | 40% |
| failed to synthesize | 31 | 20% |
| syntax error | 24 | 15% |
| type mismatch | 21 | 13% |
| other | 16 | 10% |
| termination / well-founded | 1 | 1% |
| application error | 1 | 1% |

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|
| 157 | `error:build failed` |
| 155 | `error:Lean exited with code 1` |
| 8 | `error:Fvspec/Impl.lean:51:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 6 | `error:Fvspec/Impl.lean:57:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 5 | `error:Fvspec/Impl.lean:151:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime` |
| 4 | `error:Fvspec/Impl.lean:26:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:157:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime` |
| 4 | `error:Fvspec/Impl.lean:40:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:48:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 4 | `error:Fvspec/Impl.lean:32:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |

