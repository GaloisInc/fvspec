# Compilation Validation Report

> Generated 2026-04-12 19:28 UTC by `uv run postprod validate`

## Parameters

- **Input**: `fvspec-merged.jsonl`
- **Total records loaded**: 16749
- **Eligible after filtering**: 16748
  - `impl_autoform_success >= 1.0`: no
  - Has both `spec` and `impl`
- **Sample size**: 16748 (seed=42)
- **Parallelism**: 8
- **Timeout**: 60s per build
- **Results JSONL**: `fvspec-merged.validated.jsonl`

## Compilation Results

| Metric | Value |
|--------|-------|
| Total validated | 16748 |
| Compiles | 9415 (56.2%) |
| Fails | 7333 (43.8%) |
| Timeouts | 9 |
| Failure rate 95% CI | 43.8% +/- 0.8% |

## Turn Count Correlation

| Group | Mean turns | n |
|-------|-----------|---|
| Compiling | 10.3 | 8065 |
| Non-compiling | 14.3 | 7329 |

### Failure Rate by Turn Count

| Turns | Fails / Total | Rate |
|-------|--------------|------|
| 0-10 | 2043/6095 | 34% |
| 11-15 | 2723/4877 | 56% |
| 16-20 | 1549/2601 | 60% |
| 21-30 | 869/1517 | 57% |
| 31-50 | 140/290 | 48% |
| 51+ | 5/14 | 36% |

## Error Categories

| Category | Count | % of failures |
|----------|-------|--------------|
| unknown identifier / namespace | 2940 | 40% |
| failed to synthesize | 1361 | 19% |
| other | 1044 | 14% |
| syntax error | 989 | 13% |
| type mismatch | 684 | 9% |
| termination / well-founded | 253 | 3% |
| application error | 46 | 1% |
| timeout (nontermination) | 9 | 0% |
| declaration error | 7 | 0% |

## Common Error Patterns

Top 10 normalized error lines:

| Count | Pattern |
|-------|---------|
| 7324 | `error:build failed` |
| 7238 | `error:Lean exited with code 1` |
| 112 | `error:Fvspec/Impl.lean:37:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 108 | `error:Fvspec/Impl.lean:33:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 105 | `error:Fvspec/Impl.lean:38:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 104 | `error:Fvspec/Impl.lean:39:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 102 | `error:Fvspec/Impl.lean:36:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 99 | `error:Fvspec/Impl.lean:31:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 99 | `error:Fvspec/Impl.lean:34:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |
| 96 | `error:Fvspec/Impl.lean:28:0: aborting evaluation since the expression depends on the 'sorry' axiom, which can lead to runtime ` |

