# Template Redundancy Analysis Report
## fvspec Benchmark Template Directory Structure

Generated: 2025-10-29
Location: /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates

---

## SECTION 1: DIRECTORY STRUCTURE OVERVIEW

### Template Organization

```
templates/
├── spec/
│   ├── common/
│   │   ├── initial.prompt (19 lines)
│   │   ├── fragments/
│   │   │   ├── task_core.prompt (6 lines)
│   │   │   ├── output_format.prompt (1 line)
│   │   │   ├── lsp_tools.prompt (17 lines)
│   │   │   ├── metrics.prompt (4 lines)
│   │   │   └── dependency_formalization.prompt (10 lines)
│   │   └── README.md (102 lines)
│   └── variants/
│       ├── control-functional/ (20 lines system.prompt)
│       ├── control-mvcgen/ (192 lines system.prompt)
│       └── terse-functional/ (20 lines system.prompt)
│
└── deps/
    ├── common/
    │   ├── refine.prompt.template (14 lines)
    │   └── strings.toml (51 lines)
    └── variants/
        ├── functional/
        │   ├── system.prompt (26 lines)
        │   └── translate.prompt.template (65 lines)
        └── mvcgen/
            ├── system.prompt (27 lines)
            └── translate.prompt.template (64 lines)
```

Total template lines: 485 (across 12 prompt/template files)

---

## SECTION 2: CONTENT ANALYSIS BY FRAGMENT

### 2.1 LSP Tools Description

**Status**: SHARED fragment in spec/common/fragments/lsp_tools.prompt

**Content Summary**: 
- Lists 4 LSP tools: lean_diagnostic_messages, lean_goal, lean_multi_attempt, lean_local_search
- Explains purpose and usage of each tool
- Specifies file path conventions for Fvspec/Spec.lean

**Duplicated Across**:
1. spec/variants/control-functional/system.prompt
   - Line 7: {% include 'common/fragments/lsp_tools.prompt' %}
2. spec/variants/control-mvcgen/system.prompt  
   - Line 161: {% include 'common/fragments/lsp_tools.prompt' %}
3. spec/variants/terse-functional/system.prompt
   - Line 14: Lists tools inline (NOT using fragment)
   
**Issue**: Terse variant does NOT use the fragment - contains inline version (3 lines)

---

### 2.2 Output Format Instructions

**Status**: SHARED fragment in spec/common/fragments/output_format.prompt

**Content**: 1 line: "Always respond with Lean 4 code in code tags: <code>theorem x : 1 = 1 := sorry</code>"

**Used By**:
1. spec/variants/control-functional/system.prompt (line 5)
2. spec/variants/control-mvcgen/system.prompt (line 159)
3. spec/common/initial.prompt - does NOT directly include it

**Issue**: Spec initial prompt has similar but separate wording: "Provide code in tags: <code>...</code>"
- Fragment says "Always respond with Lean 4 code in code tags"
- Initial prompt says "Provide code in tags"
- Could be unified

---

### 2.3 Metrics Description

**Status**: SHARED fragment in spec/common/fragments/metrics.prompt

**Content** (4 lines):
```
## Metrics
You will report two metrics for each translation:
- **Faithfulness** (X/10): How well the Lean 4 code captures the semantics...
- **Interest** (X/10): The intricacy of the generated Lean 4 specification...
```

**Used By**:
1. spec/variants/control-functional/system.prompt (line 20)
2. spec/variants/control-mvcgen/system.prompt - CUSTOM text (lines 177-181)
3. spec/variants/terse-functional/system.prompt - CUSTOM text (lines 17-20)

**Issue**: 
- control-mvcgen and terse-functional have CUSTOM metrics sections that duplicate the core concept
- They should all reference the common fragment for consistency

---

### 2.4 Lean Task Core Description

**Status**: SHARED fragment in spec/common/fragments/task_core.prompt

**Content** (6 lines):
```
## Task
Translate Python property-based tests (written with Hypothesis) into Lean 4 
theorem statements and function signatures. You're declaring theorems and 
signatures with `sorry` placeholders...
```

**Conditional Logic**: Includes dependency_formalization.txt if deps > 0

**Used By**:
1. spec/variants/control-functional/system.prompt (line 3)
2. spec/variants/control-mvcgen/system.prompt (line 3)

**Not Used By**: spec/variants/terse-functional/system.prompt
- Reason: Terse variant provides minimal instructions inline

---

### 2.5 Dependency Formalization

**Status**: SHARED fragment in spec/common/fragments/dependency_formalization.prompt

**Content** (10 lines):
- Workflow instructions for dependency formalization
- Step-by-step process: call tools → wait → write spec → import

**Conditional**: Jinja2 {% if deps|length > 0 %} guard

**Used By**:
1. spec/common/fragments/task_core.prompt (nested include, line 5)
2. Indirectly via control-functional and control-mvcgen variants

**Issue**: Referenced but file points to non-existent 'dependency_formalization.txt' (should be .prompt)

---

## SECTION 3: DUPLICATED CONTENT BLOCKS (>3 lines)

### 3.1 LSP Tools Description Block

**Location A**: spec/common/fragments/lsp_tools.prompt (lines 1-17)
**Location B**: spec/variants/terse-functional/system.prompt (lines 14-17)

**Status**: DUPLICATED (terse variant doesn't use fragment)
**Lines**: 4 lines of core content duplicated

```
Available: `lean_diagnostic_messages("Fvspec/Spec.lean")`, 
`lean_goal("Fvspec/Spec.lean", line)`, 
`lean_multi_attempt`, `lean_local_search`. 
Use to verify type correctness.
```

---

### 3.2 Output Code Format Block

**Location A**: spec/common/fragments/output_format.prompt (1 line)
**Location B**: spec/variants/terse-functional/system.prompt (line 12)
**Location C**: spec/variants/control-functional/system.prompt (line 5)
**Location D**: spec/variants/control-mvcgen/system.prompt (line 159)

**Status**: Output format concept duplicated with slight variations
- Fragment: "Always respond with Lean 4 code in code tags: <code>theorem x : 1 = 1 := sorry</code>"
- Terse: "Provide code in tags: <code>...</code>"
- Core-functional/mvcgen: Uses fragment

---

### 3.3 Metrics Reporting Instructions

**Location A**: spec/common/fragments/metrics.prompt (4 lines)
**Location B**: spec/variants/control-mvcgen/system.prompt (lines 177-181)
**Location C**: spec/variants/terse-functional/system.prompt (lines 17-20)

**Status**: DUPLICATED with minor variations
**Lines**: 4 lines concept duplicated

```
## Metrics
Report two scores:
- **Faithfulness** (X/10): How well Lean captures Python semantics
- **Interest** (X/10): Complexity/sophistication of specification
```

---

### 3.4 Lean System Prompt Introduction

**Location A**: spec/variants/control-functional/system.prompt (line 1)
**Location B**: spec/variants/control-mvcgen/system.prompt (line 1)

**Status**: DIFFERENT introductions (not duplicated)
- control-functional: "You are an expert at declaring Lean 4 theorems..."
- control-mvcgen: "You are an expert at declaring verified imperative programs in Lean 4..."

---

### 3.5 Process/Workflow Instructions

**Location A**: spec/variants/control-functional/system.prompt (lines 9-20)
**Status**: UNIQUE to control-functional (6-step process)

**Location B**: spec/variants/control-mvcgen/system.prompt (lines 5-192)
**Status**: EXTENSIVE mvcgen-specific instructions (not shared)

**Issue**: No shared "process" fragment - each variant has its own workflow

---

## SECTION 4: DEPS TEMPLATES ANALYSIS

### 4.1 LSP Tools in Deps Templates

**Location A**: deps/variants/functional/system.prompt (lines 8-26)
**Location B**: deps/variants/mvcgen/system.prompt (lines 9-27)

**Status**: NEARLY IDENTICAL (18-19 lines each)

**Content**:
```
## Lean LSP Tools

You have access to executable LSP tools...
Available tools:
- `lean_diagnostic_messages` - Get structured diagnostics
- `lean_goal` - View proof state at specific location
- `lean_multi_attempt` - Try multiple tactics in parallel
- `lean_local_search` - Search for definitions/theorems

How to use these tools:
1. Call them as actual tool calls
2. Wait for tool result before proceeding
3. Use feedback to refine code
4. Do NOT write as text - use actual tool call mechanism

Important: Your Lean code will be written to temporary file...
```

**Duplication**: 18 lines identical between both variants
**Extraction Opportunity**: HIGH - Create deps/common/lsp_tools.template

---

### 4.2 Namespace/Module Guidelines

**Location A**: deps/variants/functional/translate.prompt.template (line 54)
**Location B**: deps/variants/mvcgen/translate.prompt.template (line 53)

**Status**: IDENTICAL instructions

**Content**:
```
Ensure the resulting definitions reside in the module `{{ lean_module_qualified }}` 
(file stem `{{ lean_file_stem }}.lean`). 
Do NOT include a `namespace` block in this module; the aggregation logic will 
wrap all dependencies in a single namespace block in the aggregated `Deps.lean` 
file. Write all definitions as if they are already inside the correct namespace.
```

**Duplication**: 4 lines identical
**Extraction Opportunity**: HIGH - Create deps/common/module_guidelines.template

---

### 4.3 Output Format in Deps

**Location A**: deps/variants/functional/translate.prompt.template (lines 60-63)
**Location B**: deps/variants/mvcgen/translate.prompt.template (lines 59-62)

**Status**: IDENTICAL output format

**Content**:
```
## Output Format
When you have finalized your implementation, respond with Lean 4 code 
wrapped in `<code>...</code>` tags.

Example format: <code>def helper : Nat := 42</code>
```

**Duplication**: 4 lines identical
**Extraction Opportunity**: MEDIUM - Create deps/common/output_format.template

---

### 4.4 Transparent/Computable Emphasis

**Location A**: deps/variants/functional/system.prompt (lines 3-4)
**Location B**: deps/variants/functional/translate.prompt.template (lines 2, 52)
**Location C**: deps/variants/mvcgen/system.prompt (lines 3, 5)
**Location D**: deps/variants/mvcgen/translate.prompt.template (lines 2, 54, 56)

**Status**: REPEATED CONCEPT

**Theme**: Emphasis on transparent, pure definitions; avoid axioms/opaque
**Duplication**: 3+ lines repeats across 4 files

**Extraction Opportunity**: HIGH - Create deps/common/computable_requirements.template

---

### 4.5 Refine Template (Error Recovery)

**Location**: deps/common/refine.prompt.template (14 lines)

**Status**: UNIQUE - no duplication found
**Content**: Error message + instructions for retrying after compilation failure

---

## SECTION 5: CROSS-TEMPLATE PATTERNS

### 5.1 LSP Tool Descriptions Pattern

**Locations**:
- spec/common/fragments/lsp_tools.prompt (17 lines)
- deps/variants/functional/system.prompt (18 lines)
- deps/variants/mvcgen/system.prompt (19 lines)
- spec/variants/terse-functional/system.prompt (4 lines, simplified)

**Status**: MOSTLY DUPLICATED with style variations
- spec version: Concise, file-path specific
- deps versions: Detailed, includes implementation instructions

**Duplication**: 10+ lines conceptually duplicated

---

### 5.2 Transparency/Computability Requirements

**Across All Files**:
- spec/variants/control-functional/system.prompt: Line 1 mentions pure functional
- spec/variants/control-mvcgen/system.prompt: Lines 5-32 extensive patterns
- deps/variants/functional/system.prompt: Lines 3-4, 5
- deps/variants/mvcgen/system.prompt: Lines 3, 5

**Status**: CONCEPTUAL DUPLICATION
**Theme**: "Keep definitions transparent, use def with sorry not axiom, maintain computability"

---

### 5.3 Output Code Format Pattern

**Locations**:
- spec/common/fragments/output_format.prompt (1 line)
- spec/variants/terse-functional/system.prompt (1 line, simplified)
- deps/variants/functional/translate.prompt.template (4 lines)
- deps/variants/mvcgen/translate.prompt.template (4 lines)
- deps/common/refine.prompt.template (1 line, CRITICAL wrapper)

**Status**: DUPLICATED with variations
**Duplication**: 2-4 line blocks repeated 3+ times

---

## SECTION 6: EXTRACTABLE FRAGMENTS INVENTORY

### Current Shared Fragments in spec/common/fragments/:
1. task_core.prompt (6 lines) - WELL EXTRACTED
2. output_format.prompt (1 line) - MINIMAL
3. lsp_tools.prompt (17 lines) - WELL EXTRACTED
4. metrics.prompt (4 lines) - WELL EXTRACTED
5. dependency_formalization.prompt (10 lines) - WELL EXTRACTED

**Coverage**: 38 lines shared (good!)

---

### RECOMMENDED NEW FRAGMENTS FOR DEPS:

#### 1. deps/common/lsp_tools.template
**Source**: deps/variants/functional/system.prompt lines 8-26
**Source**: deps/variants/mvcgen/system.prompt lines 9-27
**Lines**: 18-19 (DUPLICATE)
**Savings**: 18-19 lines × 2 files = 36-38 lines

#### 2. deps/common/module_guidelines.template
**Source**: Both translate.prompt.template files
**Lines**: 4 (identical in both)
**Savings**: 4 lines × 2 files = 8 lines

#### 3. deps/common/output_format.template
**Source**: Both translate.prompt.template files lines 60-63
**Lines**: 4 (identical in both)
**Savings**: 4 lines × 2 files = 8 lines

#### 4. deps/common/computable_requirements.template
**Source**: All deps files
**Lines**: Conceptual consolidation of 3-5 line blocks
**Savings**: 10+ lines across 4 files

#### 5. spec/common/fragments/process.template (optional)
**Source**: spec/variants/control-functional/system.prompt lines 9-20
**Lines**: 6 (but may be intentionally different per variant)
**Decision**: KEEP VARIANT-SPECIFIC (control-functional is unique; control-mvcgen has completely different process)

---

## SECTION 7: LARGE BLOCK DUPLICATIONS (>3 LINES)

### CRITICAL FINDING 1: LSP Tools Block in deps/

```
deps/variants/functional/system.prompt (lines 8-26):
## Lean LSP Tools

You have access to executable LSP tools for interactive Lean development. 
These are real tools you can call - do NOT write them as text in angle brackets.

Available tools:
- `lean_diagnostic_messages` - Get structured diagnostics (errors, warnings, info)
- `lean_goal` - View proof state at a specific location
- `lean_multi_attempt` - Try multiple tactics in parallel
- `lean_local_search` - Search for definitions/theorems in local project and stdlib

**How to use these tools:**
1. Call them as actual tool calls (your framework will execute them)
2. Wait for the tool result before proceeding
3. Use the feedback to refine your code
4. Do NOT write `<lean_diagnostic_messages>` or similar as text - use the actual tool call mechanism

**Important**: Your Lean code will be written to a temporary file in your workspace. 
Use the file path provided in error messages when calling these tools.

Use these tools iteratively to check and refine your implementation 
before providing the final `<code>...</code>` response.
```

EXACT DUPLICATE found in:
deps/variants/mvcgen/system.prompt (lines 9-27)

**Status**: 19-line EXACT DUPLICATION
**Extraction**: CREATE deps/common/lsp_tools.template
```

---

### CRITICAL FINDING 2: Module Guidelines in deps/

```
Both translate.prompt.template files contain IDENTICAL text:

Ensure the resulting definitions reside in the module `{{ lean_module_qualified }}` 
(file stem `{{ lean_file_stem }}.lean`). **Do NOT include a `namespace` block in 
this module; the aggregation logic will wrap all dependencies in a single namespace 
block in the aggregated `Deps.lean` file. Write all definitions as if they are 
already inside the correct namespace.**
```

**Status**: 4-line EXACT DUPLICATION
**Extraction**: CREATE deps/common/module_guidelines.template

---

### CRITICAL FINDING 3: Output Format in deps/

```
## Output Format
When you have finalized your implementation, respond with Lean 4 code wrapped 
in `<code>...</code>` tags.

Example format: <code>def helper : Nat := 42</code>

Use LSP tools to iteratively check and refine your code before providing 
the final `<code>...</code>` response.
```

**Status**: 4-line concept DUPLICATED in both translate.prompt.template files
**Extraction**: CREATE deps/common/output_format.template

---

### FINDING 4: Namespace Declaration Warning

**Location A**: deps/variants/functional/translate.prompt.template (line 54)
**Location B**: deps/variants/mvcgen/translate.prompt.template (line 53)

**Content**:
```
Do NOT include a `namespace` block in this module; the aggregation logic 
will wrap all dependencies in a single namespace block in the aggregated 
`Deps.lean` file.
```

**Status**: 2-line CRITICAL instruction duplicated
**Importance**: HIGH - this is a key constraint

---

## SECTION 8: INCONSISTENCIES & ISSUES

### Issue 1: Terse Variant Not Using Fragments
**File**: spec/variants/terse-functional/system.prompt
**Problem**: Contains inline LSP tools description instead of using fragment
**Impact**: Duplicates 4 lines of spec/common/fragments/lsp_tools.prompt
**Solution**: Update to use {% include 'common/fragments/lsp_tools.prompt' %}

---

### Issue 2: Metrics Description Duplication
**Files**: 
- spec/common/fragments/metrics.prompt (4 lines)
- spec/variants/control-mvcgen/system.prompt (5 lines custom)
- spec/variants/terse-functional/system.prompt (4 lines custom)

**Problem**: Two variants have custom metrics sections instead of using fragment
**Impact**: Duplicates core concept in 3 places
**Solution**: All should reference common/fragments/metrics.prompt

---

### Issue 3: File Extension Mismatch
**File**: spec/common/fragments/task_core.prompt
**Content**: References dependency_formalization.txt (line 5)
**Problem**: File is named dependency_formalization.prompt (not .txt)
**Impact**: Jinja2 include may fail
**Solution**: Update reference to .prompt extension

---

### Issue 4: Deps Fragments Not Created
**Status**: deps/common/ has only refine.prompt.template + strings.toml
**Problem**: No shared LSP tools or module guidelines fragments
**Impact**: 36+ lines duplicated across functional/mvcgen variants
**Solution**: Create 3-4 new common fragments

---

## SECTION 9: RECOMMENDATION SUMMARY

### HIGH PRIORITY - Fix Existing Issues:
1. **Create deps/common/lsp_tools.template** (36-38 lines saved)
2. **Create deps/common/module_guidelines.template** (8 lines saved)
3. **Create deps/common/output_format.template** (8 lines saved)
4. **Fix file extension**: task_core.prompt line 5 (dependency_formalization.txt → .prompt)
5. **Update terse variant**: Use fragment for LSP tools (4 lines saved)
6. **Consolidate metrics**: Both custom variants use fragment (8 lines saved)

**Total Savings**: ~60-70 lines of duplicated content

---

### MEDIUM PRIORITY - Consistency Improvements:
1. **Create deps/common/computable_requirements.template**
   - Consolidate transparency/axiom warnings
   - Used by all deps files
   
2. **Create spec/common/fragments/initial_output_format.prompt**
   - Align output format wording in initial prompts
   - Currently slight variations exist

---

### LOW PRIORITY - Consider But Not Critical:
1. **Create shared process fragment?**
   - control-functional process (6 steps) is different from control-mvcgen (70+ lines)
   - Each variant intentionally has unique approach
   - RECOMMENDATION: Keep variant-specific

2. **Unify LSP tools across spec + deps?**
   - spec version: brief, file-path specific
   - deps version: detailed, implementation-focused
   - RECOMMENDATION: Keep separate (different audiences/purposes)

---

## SECTION 10: IMPLEMENTATION ROADMAP

### Phase 1: Critical Fixes (5 files changed)
```
1. Fix: spec/common/fragments/task_core.prompt
   - Line 5: change "dependency_formalization.txt" to "dependency_formalization.prompt"

2. Create: deps/common/lsp_tools.template
   - Copy content from deps/variants/functional/system.prompt lines 8-26
   
3. Create: deps/common/module_guidelines.template
   - Copy from both translate.prompt.template files (identical)
   
4. Create: deps/common/output_format.template
   - Copy from both translate.prompt.template files (identical)
   
5. Update: spec/variants/terse-functional/system.prompt
   - Replace inline LSP tools (lines 14-17) with: {% include 'common/fragments/lsp_tools.prompt' %}
```

**Expected Result**: 
- Eliminate 18-line LSP duplication in deps
- Eliminate 8-line module guidelines duplication
- Eliminate 8-line output format duplication
- Eliminate 4-line LSP duplication in spec/terse-functional

### Phase 2: Variant Consolidation (2 files changed)
```
1. Update: spec/variants/control-mvcgen/system.prompt
   - Replace custom metrics (lines 177-181) with: {% include 'common/fragments/metrics.prompt' %}

2. Update: spec/variants/terse-functional/system.prompt
   - Replace custom metrics (lines 17-20) with: {% include 'common/fragments/metrics.prompt' %}
```

**Expected Result**: 
- Eliminate 8 lines of metrics duplication

### Phase 3: Optional Enhancement (1 file created)
```
1. Create: deps/common/computable_requirements.template
   - Consolidate transparency/axiom guidance
   - Include in both system.prompt files
   
2. Create: spec/common/fragments/output_code_format.prompt
   - Align output format specifications
   - Slight variations in current implementation
```

---

## APPENDIX A: FILE PATHS (ABSOLUTE)

### Spec Templates:
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/variants/control-functional/system.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/variants/control-mvcgen/system.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/variants/terse-functional/system.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/initial.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/fragments/task_core.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/fragments/output_format.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/fragments/lsp_tools.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/fragments/metrics.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/spec/common/fragments/dependency_formalization.prompt

### Deps Templates:
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/deps/variants/functional/system.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/deps/variants/functional/translate.prompt.template
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/deps/variants/mvcgen/system.prompt
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/deps/variants/mvcgen/translate.prompt.template
- /home/q/Work/safeguarded/aria/fvspec/benchmark/src/generate/templates/deps/common/refine.prompt.template

---

## APPENDIX B: QUICK REFERENCE TABLE

| Fragment | Current Location | Line Count | Duplicated In | Type | Priority |
|----------|------------------|-----------|----------------|------|----------|
| LSP Tools | spec/common/fragments/ | 17 | terse-functional, deps (×2) | Critical | HIGH |
| Module Guidelines | None (in translate templates) | 4 | deps functional + mvcgen | Critical | HIGH |
| Output Format | spec/common/fragments/ | 1 | terse-functional, deps (×2) | Existing | MEDIUM |
| Metrics | spec/common/fragments/ | 4 | control-mvcgen, terse-functional | Existing | MEDIUM |
| Computable Reqs | None | 3+ | All deps files | Conceptual | MEDIUM |
| Task Core | spec/common/fragments/ | 6 | control-functional, control-mvcgen | Existing | LOW |
| Refine Error | deps/common/ | 14 | - | Unique | NONE |

