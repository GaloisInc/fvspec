# Depmock Subagent TODOs

1. [x] Reorganize prompt templates into `templates/spec` and `templates/deps` with variant support.
2. [x] Prototype the autoformalization agent: wire prompts into an `@agent` that emits Lean dependencies and expose via `as_tool`.
3. [x] Implement caching: reuse prior Lean artifacts when the same dependency hash appears.
4. [x] Orchestrate per-sample flow: ensure the depmock tool runs before main fvspec prompts and writes Lean modules into run artifacts.
5. [x] Add CLI support: create `uv run fvspec deps autoformalize` command for targeted regeneration.
6. [ ] Integrate tests: add coverage ensuring the depmock agent generates compilable Lean and records outputs correctly.
