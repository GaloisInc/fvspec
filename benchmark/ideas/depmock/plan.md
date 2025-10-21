# Depmock Subagent Integration Plan

Goal: ship `uv run fvspec` with real dependency autoformalization by embedding the depmock agent as an inspect_ai subagent (agent-as-tool). No stretch goals, no future roadmap—just the blockers between today’s implementation and a working multi-agent flow.

## TODO
1. [ ] make sure it actually tries to implement the dep functions, instead of stubbing them with unit. 
