#import "@preview/charged-ieee:0.1.4": ieee
#import "@preview/cetz:0.4.2"
#import "fns.typ" as fns

#show: ieee.with(
  title: [From Property-Based Tests to Formal Proofs: \ A Benchmark for Lean 4 Specification Generation],
  abstract: [
    We present a benchmark for evaluating AI models on formal verification tasks, extending the RealPBT dataset of real-world Python property-based tests (PBTs) into Lean 4 specifications with `sorry` placeholders. Translating PBTs into formal specifications is challenging: it requires modelling Python library semantics in Lean, bridging the gap between input/output testing and structural proofs, and handling the inherent difficulties of dependently-typed programming. We describe a three-agent LLM pipeline for transpiling PBT suites into Lean specifications, evaluate coverage and quality metrics, and provide baselines for proof completion using several automated and model-based approaches. Our benchmark aims to drive progress on the underexplored problem of AI-assisted formal verification of real-world software.
  ],
  // TODO: authors
  authors: (),
  index-terms: ("Formal verification", "Property-based testing", "Lean 4", "Benchmark", "LLM"),
  bibliography: bibliography("refs.bib"),
  figure-supplement: [Fig.],
)

// ---------------------------------------------------------------------------
// 1. Introduction
// ---------------------------------------------------------------------------

= Introduction <sec:intro>

// What is PBT? What is RealPBT?
// What is Lean? Why benchmarking Lean is hard
// Summary of process
// Summary of results

#lorem(80)

// ---------------------------------------------------------------------------
// 2. Task Definition
// ---------------------------------------------------------------------------

= Task Definition <sec:task>

// Intuitive description of the task

#lorem(40)

== Running Example <sec:example>

// Tiny Hypothesis example -- adding two numbers

// Tiny corresponding Lean example -- adding two numbers in Lean

// Baseline example -- proof that adding two numbers is correct

#lorem(60)

== PBT vs. Proof <sec:pbt-vs-proof>

// Input/output vs. proofs over structure

#lorem(40)

== Challenges <sec:challenges>

// Library modelling
// Other difficulties

#lorem(40)

// ---------------------------------------------------------------------------
// 3. Pipeline
// ---------------------------------------------------------------------------

= Pipeline <sec:pipeline>

// Clean up dataset (already done by RealPBT)

#lorem(30)

== LLM-Based Transpilation <sec:transpilation>

// Three-agent design: impl, spec, units
// Why it's hard

#lorem(60)

== Cleanup and Quality Evaluation <sec:cleanup>

// Cleanup examples / quality evaluation process

#lorem(40)

== Metrics <sec:metrics>

// Coverage, structural faithfulness, quality metrics

#lorem(40)

// ---------------------------------------------------------------------------
// 4. Results
// ---------------------------------------------------------------------------

= Results <sec:results>

== Experimental Setup <sec:experimental-setup>

// Pipeline configuration, models used

#lorem(40)

== Coverage <sec:coverage>

// % coverage across the dataset

#lorem(40)

== Quality <sec:quality>

// % quality of generated specifications

#lorem(40)

== Baselines <sec:baselines>

// % baseline success for various tools / models

#lorem(40)

== Difficulty Stratification <sec:difficulty>

// Stratification of tasks by difficulty
// Human baselining ???

#figure(
  fns.difficulty-histogram(),
  caption: [Distribution of Haiku-assessed difficulty grades across the #fns.fvspec_n benchmark tasks.],
) <fig:difficulty>

#lorem(40)

// ---------------------------------------------------------------------------
// 5. Threats to Validity / Limitations
// ---------------------------------------------------------------------------

= Threats to Validity <sec:threats>

// No human baselines
// Partial coverage
// Other limitations

#lorem(40)

// ---------------------------------------------------------------------------
// 6. Related Work
// ---------------------------------------------------------------------------

= Related Work <sec:related>

// FVAPPS / Proving the Coding Interview
// Other formal verification benchmarks
// LLM + formal methods
// Various criticisms

#lorem(60)

// ---------------------------------------------------------------------------
// 7. Conclusion
// ---------------------------------------------------------------------------

= Conclusion <sec:conclusion>

#lorem(40)

== Future Work <sec:future>

#lorem(40)
