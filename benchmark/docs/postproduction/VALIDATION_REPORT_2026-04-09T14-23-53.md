# Compilation Validation Report

> Generated 2026-04-09 14:23 UTC by `uv run postprod validate`

## Parameters

- **Input**: `fvspec-merged.jsonl`
- **Total records loaded**: 16749
- **Eligible after filtering**: 13111
  - `impl_autoform_success >= 1.0`: yes
  - Has both `spec` and `impl`
- **Sample size**: 13111 (seed=42)
- **Parallelism**: 8
- **Timeout**: 60s per build
- **Results JSONL**: `fvspec-merged.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 13111 |
| Compiles | 7594 (57.9%) |
| Fails | 5517 (42.1%) |
| Timeouts | 9 |
| Failure rate 95% CI | 42.1% +/- 0.8% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 10.0 | 6246 |
| Non-compiling | 15.7 | 5514 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 892/3891 | 23% |
| 11-15 | 2307/4044 | 57% |
| 16-20 | 1401/2265 | 62% |
| 21-30 | 777/1295 | 60% |
| 31-50 | 133/253 | 53% |
| 51+ | 4/12 | 33% |

## Error Categories

| Category | Count | % of failures |
|----------|-------|--------------|
| unknown identifier / namespace | 2270 | 41% |
| failed to synthesize | 915 | 17% |
| other | 762 | 14% |
| syntax error | 731 | 13% |
| type mismatch | 571 | 10% |
| termination / well-founded | 228 | 4% |
| application error | 30 | 1% |
| timeout (nontermination) | 9 | 0% |
| declaration error | 1 | 0% |

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|
| 5508 | `error:build failed` |
| 5435 | `error:Lean exited with code 1` |
| 91 | `error:Fvspec/Impl.lean:33:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 88 | `error:Fvspec/Impl.lean:39:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 86 | `error:Fvspec/Impl.lean:37:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 85 | `error:Fvspec/Impl.lean:38:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 82 | `error:Fvspec/Impl.lean:36:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 81 | `error:Fvspec/Impl.lean:34:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 79 | `error:Fvspec/Impl.lean:32:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 79 | `error:Fvspec/Impl.lean:40:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |

