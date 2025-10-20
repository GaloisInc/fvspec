# Depmock Subagent TODOs

1. [x] Reorganize prompt templates into `templates/spec` and `templates/deps` with variant support.
2. [x] Prototype the autoformalization agent: wire prompts into an `@agent` that emits Lean dependencies and expose via `as_tool`.
3. [ ] Implement caching: reuse prior Lean artifacts when the same dependency hash appears.
4. [ ] Orchestrate per-sample flow: ensure the depmock tool runs before main fvspec prompts and writes Lean modules into run artifacts.
5. [ ] Add CLI support: create `uv run deps-autoformalize` command for targeted regeneration.
6. [ ] Integrate tests: add coverage ensuring the depmock agent generates compilable Lean and records outputs correctly.
