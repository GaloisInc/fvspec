# Depmock Subagent Integration Plan

Goal: ship `uv run fvspec` with real dependency autoformalization by embedding the depmock agent as an inspect_ai subagent (agent-as-tool). No stretch goals, no future roadmap—just the blockers between today's implementation and a working multi-agent flow.

## Current Status (Oct 24, 2025)

**✅ SHIPPED - Depmock is fully integrated and working**

The dependency autoformalization pipeline is complete and production-ready:

### What's Working
1. **Agent Architecture**:
   - Main spec agent has `autoformalize_dependency_tool` available
   - Dependency subagent runs via `run_dependency_agent` in agent_runner.py
   - Both agents use lean-lsp-mcp tools (`lean_diagnostic_messages`, `lean_goal`) for verification

2. **File Organization**:
   - All dependencies consolidated into single `Deps.lean` file per sample
   - Wrapped in `namespace Fvspec.Deps` / `end Fvspec.Deps`
   - Manifest written to `deps_manifest.jsonl` at sample output root
   - No subdirectories, clean flat structure

3. **Caching & Efficiency**:
   - SHA256-based cache in `artifacts/depcache/`
   - Cache hits avoid redundant generation
   - Topological ordering respects import dependencies

4. **Tooling**:
   - Replaced all `lean_compile` (lake build) with `lean_diagnostic_messages` from MCP
   - Custom MCP client with proper handshake (initialize → initialized → tool call)
   - Per-sample workspace isolation maintains parallelism (parallelism=128)

5. **Variants**:
   - Functional style for recursive/mathematical functions
   - mvcgen style for imperative/stateful code
   - Deps variant automatically matches spec variant

### Architecture Highlights
- **Per-sample tmpdir workspaces**: Each sample gets isolated Lake project
- **MCP subprocess spawning**: Each tool call spawns `uvx lean-lsp-mcp` with `LEAN_PROJECT_PATH`
- **Parallel execution**: Full parallelism maintained with no shared state
- **No custom lake build**: All verification through lean-lsp-mcp protocol

### Files Written Per Sample
```
artifacts/runs/{timestamp}__{variant}/{sample_id}/
├── Deps.lean              # Consolidated dependencies with namespace
├── deps_manifest.jsonl    # Dependency metadata
├── Spec.lean              # Main spec code
├── datapoint.json         # Input metadata
└── qa.json                # Quality metrics
```

### Known Issues
None blocking. The IndexError in inspect_ai (TODO.md) is unrelated to depmock and has a workaround.

## Completed Tasks
1. [x] make sure it actually tries to implement the dep functions, instead of stubbing them with unit.
   - Fixed contradictory prompts: removed "Do not implement" from initial.prompt
   - Enhanced task_core.txt with explicit CRITICAL instructions to use autoformalize_dependency_tool
   - Ensured deps variant matches spec variant (functional/mvcgen) by extracting style from VariantConfig
2. [x] In the tmp lean sandbox, make sure you're writing all deps to `Fvspec.Deps`, not `Fvspec.Deps.Whatever`. its ok to have all the dep functions just stacked in `Deps.lean`!
   - Fixed functional variant's translate.prompt to NOT include namespace blocks
   - Already correct in mvcgen variant
   - Runner aggregates all deps into single `namespace Fvspec.Deps` block
3. [x] MCP integration with per-sample workspaces
   - Custom MCP client with subprocess spawning per tool call
   - Proper JSON-RPC 2.0 handshake implementation
   - Maintains parallel execution with isolated workspaces
4. [x] Remove lean_compile in favor of MCP tools
   - All agents use lean_diagnostic_messages for verification
   - Consistent tooling across main and dependency agents
   - No custom lake build subprocess management 
