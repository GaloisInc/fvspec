# TODOs

## Tmpdir sandbox(?) is unable to start LSP server.

**Status**: Known limitation - MCP tools don't work with per-sample tmpdir workspaces
**Workaround**: Use `--no-mcp` flag (or set `use_mcp=False` in code)

This was found in `uv run inspect view` (on oct24-2025):
```
Tool: lean_diagnostic_messages (0.5 sec)
lean_diagnostic_messages(file_path: "/tmp/tmp.eOiLb6kBuO/Fvspec/Spec.lean")
Invalid Lean file path: Unable to start LSP server or load file
```

We also see in inspect logs:
```
No valid lean project path found. ... or set the LEAN_PROJECT_PATH environment variable.
```

**Root Cause**:
The `lean-lsp-mcp` server is spawned once at task creation time via `mcp_server_stdio()`, but each sample has its own tmpdir workspace (e.g., `/tmp/tmp.eOiLb6kBuO/`). The MCP server can't dynamically switch between workspaces for different samples.

**Why `lean_compile()` works but MCP tools don't**:
- `lean_compile()` spawns `lake build` as a subprocess with `cwd=workspace` per sample
- MCP tools use a single long-running LSP server process that doesn't know which workspace to use

**Possible Solutions** (not yet implemented):
1. Spawn a new MCP server per sample (inefficient, may not be supported by inspect_ai)
2. Use a shared workspace for all samples (defeats isolation purpose of tmpdir)
3. Modify lean-lsp-mcp to accept `LEAN_PROJECT_PATH` per request (requires upstream changes)

**Current Recommendation**: Use `--no-mcp` flag. The `lean_compile()` tool provides sufficient typechecking functionality.

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
