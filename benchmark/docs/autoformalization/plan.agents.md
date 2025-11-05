## TODOs

## fix manual agent loops, use inspect primitives:
 Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ Refactor Plan: Replace Manual Loops with inspect_ai Primitives

 Goal: Eliminate manual agent loops in function_impl_agent and spec_generation_agent by using inspect_ai's
 generate_loop().

 Phase 1: Refactor function_impl_agent (benchmark/src/generate/scaffold/formalize/impl/function_agent.py)

 1. Replace manual loop (lines 128-258) with model.generate_loop():
   - Remove the for attempt in range(max_attempts) loop
   - Remove manual tool execution logic (~80 lines)
   - Call await get_model().generate_loop(messages, tools=tools, max_iterations=max_attempts)
   - Keep validation logic after loop completes
 2. Simplify tool registry (lines 121-126):
   - Remove tools_by_name dict construction (generate_loop handles this)
 3. Update imports: Add from inspect_ai.model import get_model

 Files modified: 1 file, ~100 lines removed, ~5 lines added

 Phase 2: Refactor spec_generation_agent (benchmark/src/generate/scaffold/formalize/spec/agent.py)

 1. Replace manual loop (lines 104-227) with same pattern as Phase 1
 2. Keep spec-specific validation (compiles + has_sorry checks)

 Files modified: 1 file, ~100 lines removed, ~5 lines added

 Phase 3: Test & Validate

 1. Run existing tests: uv run pytest benchmark/tests/
 2. Run end-to-end generation: Test with sample datapoints
 3. Verify LSP tool calls work: Check logs for lean_diagnostic_messages, lean_goal, etc.

 Expected outcome: Identical behavior with 200+ fewer lines of code

### change tests so that they reflect new structure
(impl vs spec, not calling it depmock)
