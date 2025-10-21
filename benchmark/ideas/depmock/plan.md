# Depmock Subagent Integration Plan

Goal: ship `uv run fvspec` with real dependency autoformalization by embedding the depmock agent as an inspect_ai subagent (agent-as-tool). This document captures the minimum work required to replace the current stub executor with a functioning subagent loop. No stretch goals, no future roadmap—just the blockers between today’s implementation and a working multi-agent flow.

See also: `benchmark/ideas/docs/multiagent.md` for the Inspect multi-agent tooling notes harvested during indexing.

---

## 1. Desired Runtime Flow

When `uv run fvspec` executes a sample:

1. `depmock_setup` prepares dependency metadata and writes cached stubs (already in place).
2. Before the main spec solver runs, a dependency autoformalizer subagent should:
   - Receive the `DependencyPayload` and diagnostics, if any.
   - Call the prompt scaffolding (`functional`/`mvcgen`) and produce Lean code.
   - Invoke `lean_compile` (via the subagent’s tool loop) to validate the result, retrying on recoverable errors.
   - Persist the final Lean output + provenance through the existing cache/telemetry hooks.
3. The main spec solver then runs with access to the generated dependency modules.

This mirrors several patterns from the Inspect docs:
- Treat the dependency translator as its own agent (`dependency_autoformalizer`).
- Wrap it with `as_tool()` so the parent agent can call it during the tool loop.
- Use `basic_agent` to orchestrate retry/backoff and track attempts via `AgentState`.

---

## 2. Subagent Architecture

### 2.1 Components

| Component | Responsibility |
|-----------|----------------|
| `dependency_autoformalizer` (existing) | Build system/user prompts; store context in `inspect_ai.util.store()`. |
| **New** `dependency_agent_solver` | Call `dependency_autoformalizer` and `lean_compile()` inside a `basic_agent` loop. |
| `autoformalize_dependency_tool()` | Wrap `dependency_autoformalizer` using `as_tool()` so it can be mounted by another agent. |
| **New** `run_dependency_agent()` | Thin harness that instantiates the solver, passes in `DependencyExecutionRequest`, and returns `DependencyResult`. |
| CLI executor (`run_dependency_autoformalizer`) | Replace stub executor with calls to `run_dependency_agent()`. |

### 2.2 Inspect Patterns

Drawing from https://inspect.aisi.org.uk/multi-agent.html:

- **Agent-as-tool**: `as_tool(dependency_autoformalizer)` lets the parent solver treat the subagent like any other tool call; we then mount it inside a `basic_agent` that also has access to `lean_compile()`.
- **Retry semantics**: leverage `basic_agent(max_attempts=N)` to control how many times the subagent can refine output before returning failure.
- **State sharing**: we already stash payload/variant in `store()`; extend this to include the most recent Lean diagnostics so retries can access them.
- **Partial failures**: when retries are exhausted, convert the subagent’s final outcome into a `DependencyRecoverableError` or `DependencyFatalError` so the outer invocation layer can log telemetry.

---

## 3. Action Items

### 3.1 Agent Harness

1. Implement `generate/scaffold/depmock/agent_runner.py` (or similar):
   - Build a minimal inspect_ai `Task` with:
     ```python
     dependency_task = Task(
         dataset=MemoryDataset([Sample(id=cache_key, input="")]),
         solver=[
             system_message(system_prompt),
             use_tools([autoformalize_dependency_tool(), lean_compile()]),
             basic_agent(max_attempts=requested_attempts),
         ],
     )
     ```
   - Provide a tiny `GenerateConfig` matching `cfg.agent.model`.
   - Run `eval(dependency_task, ...)` with `display="none"`, `log_samples=False`, `trace=False`, writing logs into the existing artifacts directory (reuse `dependency_report.json` path or a temp subdir).
   - Extract the assistant output (Lean code) plus `state.store()` for diagnostics.

2. Translate the eval result into `DependencyResult`:
   - `lean_code` = assistant `.completion`.
   - `diagnostics` = values captured in `store()` (e.g., Lean error message) or the latest tool call output.
   - On failure, raise `DependencyRecoverableError` or `DependencyFatalError` based on exit reason.

### 3.2 Invocation Layer Wiring

1. In `run_dependency_autoformalizer`, replace the stub `executor` with a call to `run_dependency_agent()`.
2. Ensure attempt counts / diagnostics from `basic_agent` propagate back so provenance metadata stays accurate.
3. Respect `max_attempts` from CLI by passing it through to `basic_agent`.
4. Maintain existing caching: persist results with `CacheProvenance(model=cfg.agent.model, attempts=attempt_count, diagnostics=...)`.

### 3.3 Lean Validation Integration

1. Confirm the subagent’s tool stack includes a `lean_compile()` call; rely on tool results to mark success vs. recoverable failure.
2. On recoverable failure (non-zero exit code, diagnostics mentioning missing constants, etc.), loop back with diagnostics to the user prompt (`_dependency_autoformalizer` already accepts a `diagnostics` string).
3. On fatal failure (e.g., repeated syntax errors, timeouts), bubble up `DependencyFatalError` so the CLI summaries stay informative.

---

## 4. Testing & Verification

1. **Unit tests**
   - Add tests in `tests/dep/` covering `run_dependency_agent()` with a mocked inspect_ai `eval` call. Use a fake model (or monkeypatch `eval`) to return canned Lean code / diagnostics.
2. **Integration smoke**
   - Run `uv run fvspec deps autoformalize --sample-size 1 --dry-run` to confirm the plumbing still works with stubs.
   - Run without `--dry-run` once the agent is hooked up. Validate Lean modules created and `dependency_report.json` contains real `status="success"` entries.
3. **Lean validation path**
   - Run `uv run fvspec deps autoformalize --sample-size 1 --validate` and ensure `Deps.lean` is typechecked and validation results are recorded.

---

# Deliverable Checklist

- [x] `run_dependency_autoformalizer` invokes the real subagent via `run_dependency_agent()`.
- [x] Subagent uses inspect_ai `basic_agent` + `autoformalize_dependency_tool()` + `lean_compile()` to produce Lean code.
- [ ] Telemetry (`dependency_report.json`, cache metadata, validation logs) captures actual agent attempts/diagnostics.
- [ ] `uv run fvspec deps autoformalize` works end-to-end, and `uv run fvspec` automatically leverages the generated dependencies for the main spec solver.
