# TODOs

## IndexError in inspect_ai's json_changes function (Rare, Sample-Specific)

**Discovered**: Oct 23, 2025
**Status**: Workaround implemented via `--skip-index` flag (commit 432901c)

### Symptom

```
IndexError: list index out of range
  File ".venv/lib/python3.13/site-packages/inspect_ai/_util/json.py", line 125, in json_changes
```

Occurs during tool execution cleanup, consistently after ~2-3 samples with certain random seeds.

### Root Cause Analysis

This is a **latent bug in inspect_ai** that's triggered by specific sample structures. Our investigation revealed:

1. **Sample-Specific Trigger**: With `ranseed=3`, the bug triggers at sample #3: ID=38813 (`test_convolution_layout`)
   - Different seeds hit different samples, suggesting it's the sample content, not position
   - The bug is in inspect_ai's JSON state comparison logic during tool cleanup

2. **Sampling Method Divergence**: Indexed sampling and reservoir sampling produce **different sample orders** even with identical random seeds:
   - **Indexed sampling**: Uses `random.sample()` on line numbers, then seeks directly to selected lines
   - **Reservoir sampling**: Streams file sequentially, uses `random.randint()` for replacement decisions
   - These are fundamentally different algorithms that happen to share a seed parameter

3. **Why the Workaround Works**: `--skip-index` uses reservoir sampling, which produces a different sample order and happens to avoid the problematic sample at position #3 with ranseed=3

### Sample Order Evidence

Diagnostic script output for first 10 samples with ranseed=3:

**Indexed sampling**:
```
1. Sample ID=40913 name=test_lengths_mean
2. Sample ID=31059 name=test_remove_padding
3. Sample ID=38813 name=test_convolution_layout  ← IndexError triggers here
4. Sample ID=38350 name=test_show_pos_mean_valid
...
```

**Reservoir sampling**: (Different order, avoids the bug)

### Hypothesis

The problematic sample (test_convolution_layout) likely has:
- Complex nested tool calls
- Large JSON state changes
- Edge case in tool result structure

This causes inspect_ai's `json_changes()` function to attempt accessing a list index that doesn't exist when comparing state before/after tool execution.

### Workaround

**Temporary solution** (implemented):
```bash
uv run fvspec --skip-index
uv run fvspec compare-variants --skip-index
```

**Trade-off**: Sampling takes ~10 minutes instead of ~1 second, but avoids the problematic sample.

### Proper Fix (TODO)

1. **Isolate the problematic sample**: Extract sample ID=38813's full JSON to reproduce in minimal test case
2. **Debug inspect_ai internals**: Step through `inspect_ai/_util/json.py:125` with this sample to see why list access fails
3. **Report upstream**: File issue with inspect_ai project with minimal reproduction
4. **Possible local patch**: Add defensive bounds checking in our codebase if we vendor/fork inspect_ai

**Note**: This is NOT a bug in our sampling code - both methods produce valid, uniformly random samples. The bug is in inspect_ai's state comparison logic being exposed by certain sample structures.

### References

- Diagnostic script: `/tmp/test_sample_order.py`
- Implementation: `src/generate/scaffold/dataset.py:209-301`
- Documentation: `README.md:22-32`
- Commit: 432901c "Add --skip-index flag to work around IndexError bug"

## actually implement central fn (not just sig) at benchmark-generation-time.

Optionally drop it out / replace body with sorry later.

## ~~Are we sure it's writing the final dep output at the end?~~ ✅ VERIFIED

**Status**: Confirmed working correctly (Oct 29, 2025)

The final `Deps.lean` **is being written**. The confusion arose because:

1. **Writing happens inside tool calls**: When `depmock_autoformalize_{dep}` tools are called, they write individual modules to `deps/{module}.lean` and then call `_update_deps_lean()` which regenerates the consolidated `Deps.lean` file.

2. **Not visible in inspect logs**: Inspect logs show tool calls and their return messages, but not the file I/O operations happening inside tools.

3. **Code flow** (`agent.py:467-471`, `agent.py:491-538`):
   ```python
   # Each tool call writes individual module
   module_file = deps_dir / f"{module_name}.lean"
   module_file.write_text(lean_code)

   # Then regenerates Deps.lean from all modules
   deps_lean_content = _update_deps_lean(deps_dir, sample_dir)
   ```

4. **Verification**: Checked recent artifacts; `Deps.lean` files contain properly aggregated output with:
   - Deduplicated imports at the top
   - All module contents concatenated below
   - Example: `artifacts/runs/2025-10-28T21-12-45__control-functional/11080_test_dict_to_one_element_collections/Deps.lean`

**No code changes needed** - system is working as designed. 

## parallelize depagents

with trio? or with more standard concurrency. 

## Write up redundancy-reduction philosophy about templates in `./benchmark/AGENTS.md`, very briefly.

like a sentence. 
