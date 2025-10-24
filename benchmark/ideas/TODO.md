# TODOs

## Tmpdir sandbox(?) is unable to start LSP server.

**Status**: ✅ SOLVED - Custom MCP tools with per-sample subprocess spawning (as of commit 03f7575)

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

**Why Attempted Solutions Don't Work**:

1. **Shared workspace for all samples** (attempted and reverted):
   - Would allow MCP server to have fixed workspace location
   - BUT: Breaks parallelism! All samples would overwrite the same `Fvspec/Spec.lean`
   - Parallel execution is mandatory (parallelism=128), so this is not viable

2. **Spawn new MCP server per sample**:
   - Would allow per-sample workspaces
   - BUT: Inefficient, may not be supported by inspect_ai's tool architecture
   - MCP server is spawned at task definition time, not per-sample

3. **Modify lean-lsp-mcp upstream**:
   - Would need to accept workspace path per tool call
   - Requires changes to lean-lsp-mcp tool itself
   - Not under our control

**Fundamental Conflict** (with inspect_ai's mcp_tools()):
- MCP LSP server needs: Fixed workspace location (spawned once at task creation)
- Parallel evaluation needs: Per-sample isolated workspaces (different paths per sample)
- These requirements are mutually exclusive with inspect_ai's mcp_tools() architecture

**Solution Implemented**:

Instead of using inspect_ai's `mcp_tools()` (which spawns one long-running MCP server), we created custom tool wrappers that spawn lean-lsp-mcp as a subprocess **per tool call**:

1. **Custom MCP client** (`call_lean_lsp_mcp()` in declaration.py):
   - Spawns `uvx lean-lsp-mcp` as subprocess for each tool call
   - Sets `LEAN_PROJECT_PATH` environment variable to the sample's workspace
   - Communicates via JSON-RPC 2.0 over stdio with proper MCP initialization handshake:
     1. Send `initialize` request (id=1) with protocol version "2024-11-05"
     2. Send `initialized` notification (no id)
     3. Send tool call request (id=2)
   - Returns results and terminates process

2. **Per-sample workspace isolation**:
   - Each sample gets its own tmpdir workspace (as before)
   - Each MCP tool call uses that sample's workspace via LEAN_PROJECT_PATH
   - No shared state between samples - fully parallelizable!

3. **Custom tool wrappers** (declaration.py):
   - `lean_diagnostic_messages()` - Get diagnostic messages for a Lean file
   - `lean_goal()` - Get proof goal at a specific location
   - More tools can be added easily by following the same pattern

4. **Integration**:
   - `lean_lsp_mcp_tools()` returns list of custom tools
   - task.py uses these instead of inspect_ai's `mcp_tools()`
   - Works seamlessly with `parallelism=128`

**Trade-offs**:
- ✅ Maintains per-sample isolation
- ✅ Fully parallelizable
- ✅ Works with existing tmpdir architecture
- ⚠️ Spawns lean-lsp-mcp process per tool call (overhead vs. long-running server)
- ⚠️ Doesn't maintain persistent LSP state between calls within a sample

The overhead is acceptable since:
- lean-lsp-mcp startup is reasonably fast (~1-2 seconds)
- Most samples only make a few LSP tool calls
- Parallel gains far outweigh per-call overhead

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
