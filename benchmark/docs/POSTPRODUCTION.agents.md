# Enrich QA with True Turn Counts from `.eval` Files

## Motivation

`qa.json` has `token_usage_breakdown[].num_toolcalls` per subagent, but no true **turn count** (number of LLM generation rounds). Tool calls ≠ turns: a model can batch multiple tool calls in one turn, or generate a turn with no tool calls.

The `.eval` zip files contain the ground truth in `store.*_conversation` arrays (per-subagent message lists with roles).

## Data Availability (verified)

- **1:1 mapping** between `.eval` sample IDs and `qa.json` directories (500/500 in tested run, zero mismatches)
- `spec_conversation` / `units_conversation`: present in ~99.6% of samples
- `impl_conversation`: present in ~74% (missing = failed before that stage → default to 0)
- Sample ID matching: strip `_epoch_1.json` suffix from eval zip entry name

## Approach

### Two-phase tool

**Phase 1: Enrich `qa.json` files in-place** (operates on `artifacts/runs/`)

For each run directory:
1. Open each `.eval` zip
2. For each sample entry, extract from `store`:
   - `impl_conversation`, `spec_conversation`, `units_conversation`
   - Count messages by role: `assistant` = turns, `tool` = tool responses
3. Also extract from `events`:
   - Count `model` events (global true turn count across all subagents)
   - Count `tool` events (global true tool call count)
4. Patch the matching `qa.json` with new fields (see schema below)

**Phase 2: Re-merge into JSONL** (run existing `merge` tool)

After enriching `qa.json` files, re-run `uv run merge` to propagate the new fields into `fvspec.jsonl`.

### New `qa.json` fields

```json
{
  "turn_counts": {
    "impl": { "turns": 4, "tool_calls": 3 },
    "spec": { "turns": 4, "tool_calls": 3 },
    "units": { "turns": 1, "tool_calls": 0 },
    "total_turns": 9,
    "total_tool_calls": 6
  }
}
```

Where:
- `turns` = number of `assistant` role messages in `store.*_conversation`
- `tool_calls` = number of `tool` role messages in `store.*_conversation`
- `total_turns` / `total_tool_calls` = sum across subagents (or from top-level `events` if more accurate)

Missing conversations default to `{"turns": 0, "tool_calls": 0}`.

## Implementation

New postproduction script: `src/scripts/postproduction/turncount/`

Follows existing patterns (typer CLI, rich progress, resume-safe):

```
turncount/
├── __init__.py      # CLI: `uv run turncount <runs-dir>`
├── extractor.py     # .eval zip parsing, conversation counting
├── models.py        # Pydantic models for TurnCounts
└── README.md
```

**Entry point** registered in `pyproject.toml`:
```toml
turncount = "scripts.postproduction.turncount:app"
```

**CLI interface:**
```bash
# Enrich all qa.json files in a runs directory
uv run turncount artifacts/runs/

# Enrich a specific run
uv run turncount artifacts/runs/2025-12-18T14-48-17__idx43000-43500__control-functional/

# Skip already-enriched qa.json files (resume-safe)
uv run turncount artifacts/runs/ --force  # re-compute even if turn_counts exists
```

**Core logic** (`extractor.py`):
1. `find_eval_files(run_dir) -> list[Path]` — glob for `*.eval`
2. `extract_turn_counts(eval_path) -> dict[str, TurnCounts]` — open zip, iterate samples, count roles in conversations
3. `patch_qa_json(qa_path, turn_counts)` — read, merge, write back

**Resume-safety:** Skip `qa.json` files that already have `turn_counts` key (unless `--force`).

## Merge integration

The `merge` tool's `prune.py` uses a blocklist (`FIELDS_TO_REMOVE`) — any field **not** in that set passes through automatically. Since `turn_counts` is not blocklisted, it will flow into `fvspec.jsonl` with no changes to `prune.py`.

### Caveat: preserving `graded` and `metrics` fields

The existing `fvspec.jsonl` may already have `graded` (from `uv run grader`) and `metrics` (from `uv run metrics`) fields that were computed in earlier postproduction steps. A naive `uv run merge` will regenerate the JSONL from `qa.json` files alone, which do **not** contain these fields—so they would be lost.

**Options:**
1. **Re-run grader + metrics after merge** — simplest but expensive (grader uses LLM calls).
2. **Pre-merge join** — before merging, read the existing `fvspec.jsonl`, index `graded` and `metrics` by `sample_id`, then patch them back into the merged output.
3. **Extend merge to accept a "carry-forward" JSONL** — pass the old JSONL as an argument and have merge preserve specified fields from it when the sample already exists.

Until one of these is implemented, **do not blindly re-run `uv run merge`** if the current JSONL already has graded/metrics data—those fields will be dropped.

## Validation

After enrichment, spot-check a few samples:
```bash
# Compare qa.json turn_counts against manual .eval inspection
python3 -c "
import zipfile, json
z = zipfile.ZipFile('path/to/file.eval')
d = json.loads(z.read('samples/XXXXX_epoch_1.json'))
for key in ['impl_conversation', 'spec_conversation', 'units_conversation']:
    conv = d.get('store', {}).get(key, [])
    print(f'{key}: {sum(1 for m in conv if m[\"role\"]==\"assistant\")} turns')
"
```
