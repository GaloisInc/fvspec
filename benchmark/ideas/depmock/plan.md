# Depmock Subagent Integration Plan

Goal: ship `uv run fvspec` with real dependency autoformalization by embedding the depmock agent as an inspect_ai subagent (agent-as-tool). No stretch goals, no future roadmap—just the blockers between today's implementation and a working multi-agent flow.

## TODO
1. [x] make sure it actually tries to implement the dep functions, instead of stubbing them with unit.
   - Fixed contradictory prompts: removed "Do not implement" from initial.prompt
   - Enhanced task_core.txt with explicit CRITICAL instructions to use autoformalize_dependency_tool
   - Ensured deps variant matches spec variant (functional/mvcgen) by extracting style from VariantConfig 
2. [x] In the tmp lean sandbox, make sure you're writing all deps to `Fvspec.Deps`, not `Fvspec.Deps.Whatever`. its ok to have all the dep functions just stacked in `Deps.lean`!
   - Fixed functional variant's translate.prompt to NOT include namespace blocks
   - Already correct in mvcgen variant
   - Runner aggregates all deps into single `namespace Fvspec.Deps` block 
