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

Several AI safety proposals are premised on AI-driven _formal verification_ (FV); this is a core hypothesis of the ARIA Safeguarding AI program and the related Guaranteed Safe AI agenda. If FV is to play this role, it must scale to the complexities of real-world engineered systems, but today we have little evidence whether such capabilities are possible. Relevant benchmarks are mostly either small datasets crafted by hand, larger datasets extracted from expert-driven verification projects, or are focused on advanced mathematics rather than engineering. None of these are likely to be representative of real-world engineering tasks.

We generate our benchmark from public uses of _property-based testing_ (PBT). While FV itself is rarely used in software development, PBT is a 'close sibling' technology which has seen significant adoption. In both FV and PBT, engineers write _specifications_---logical properties that the software must obey. For example, we might require that a Python function `double(x)` always returns `2*x`. The difference lies in how this property is checked. In FV, the property is _proved_ using mathematical techniques---this results in almost-perfect confidence, but requires _proof engineering_ by highly expert teams. In PBT, the code is randomly tested---e.g. for random values of `x`. This is a push-button process with no proof engineering.

PBT is typically much cheaper than formal verification, and as a result has seen wider adoption. We build our benchmark from a dataset of 54k permissively-licensed PBTs written in Python's Hypothesis framework. Each PBT in our dataset can be seen as a small theorem about a piece of Python code. To make it possible for an AI to prove or refute these theorems, we translate both code and PBTs to the theorem prover Lean, which is becoming the de-facto standard in AI formal verification. This approach has been pioneered by Dougherty and Mehta on the FVAPPS verification benchmark. In FVAPPS, source programs were taken from the APPS benchmark by Hendrycks et al, translated to PBTs, then lifted to theorems. We apply the same process at scale to PBTs found in the wild.

We use AI-driven translation to generate Lean programs and theorems at scale. LLMs are quite good at program translation, and FVAPPS has shown that this approach is practical for constructing Lean theorems. The result is tens of thousands of verification challenges, each consisting of (1) a program and (2) a desired specification, both written in Lean. Unlike existing FV benchmarks, each problem corresponds to properties of real-world software written by engineers with no formal verification experience.

// TODO: Summary of results

// ---------------------------------------------------------------------------
// 2. Task Definition
// ---------------------------------------------------------------------------

= Task Definition <sec:task>

// Intuitive description of the task

Each problem in the benchmark consists of (1) a URL pointing to the original property-based test, function, and license information, (2) a property written in Lean, and (3) a function written in Lean. The AI's task is to complete the proof, replacing the `sorry` placeholder with a valid Lean proof term.

== Running Example <sec:example>

// Tiny Hypothesis example -- adding two numbers

// Tiny corresponding Lean example -- adding two numbers in Lean

// Baseline example -- proof that adding two numbers is correct

#lorem(60)

== PBT vs. Proof <sec:pbt-vs-proof>

// Input/output vs. proofs over structure

In PBT, a property is checked by randomly generating inputs and testing them---the process is push-button but provides only statistical confidence. In FV, the property is _proved_ using mathematical techniques, providing near-perfect confidence but requiring proof engineering. Translating a PBT into a formal specification thus involves a shift from input/output testing to proofs over the structure of the program. The FVAPPS pipeline filters nonsensical theorems, but any discrepancies that remain will not affect the usefulness of the dataset. Because the Lean theorem prover provides a 'perfect' oracle, every theorem we generate is a useful challenge problem, even if it differs from the original PBT. In fact, some PBTs in our input dataset will be naturally false due to undetected edge cases.

== Challenges <sec:challenges>

// Library modelling
// Other difficulties

Formal verification is unusually difficult to benchmark for two reasons. *Problem 1:* Just as with advanced mathematics, formal verification tasks are highly varied, and constructing interesting problems requires considerable expertise. FV tasks also vary in difficulty---they can be as shallow as checking the type-safety of simple functions, or as deep as proving an unsolved mathematical theorem such as the Collatz Conjecture. Our benchmark avoids the need to select and hand-build challenge problems by translating naturally occurring PBT problems written by real-world engineers. *Problem 2:* Formal verification is little used outside academia. As a result, there are few natural datasets, and those that exist are fragmented between multiple FV tools (e.g. SAW/Cryptol for cryptographic systems, ACL2/Coq for traditional software verification, Lean for mathematics, SPIN/TLA+ for protocol analysis). Public FV examples are often pedagogical exercises for which the proof exists in many different forms in the training set. Our benchmark solves this problem by translating from a 'close sibling' domain, PBT, where many more datapoints exist. As a result, most theorems in our benchmark will have never been verified by anyone.

// ---------------------------------------------------------------------------
// 3. Pipeline
// ---------------------------------------------------------------------------

= Pipeline <sec:pipeline>

// Clean up dataset (already done by RealPBT)

Our pipeline is modelled on the one used by Dougherty and Mehta for FVAPPS. We begin with the RealPBT dataset, which has already been cleaned and filtered.

== LLM-Based Transpilation <sec:transpilation>

// Three-agent design: impl, spec, units
// Why it's hard

Our three-agent transpilation pipeline operates as follows:

- Identify target property-based tests on Github covered by permissive licenses.
- Using a mix of syntactic translation and code-focused LLM, translate to Lean code and properties. As in FVAPPS, we iteratively repair partially-successful translations over multiple steps.
- Use Lean's property-based testing framework Plausible alongside the code-focused LLM to filter poor-quality translations, and target them for repair.

Based on FVAPPS, we are confident that smaller problems and code can be easily transpiled using an LLM. Larger examples may fail or generate poor-quality translations. In such cases, we fall back to syntactic translation, which we expect to produce less understandable but more predictable results, and then use LLMs for targeted quality improvement.

== Cleanup and Quality Evaluation <sec:cleanup>

// Cleanup examples / quality evaluation process

In some cases, transpilation may generate less useful specification/program pairs. For example, a common failure in FVAPPS was type restriction in specifications, such as translating a signed integer into an unsigned natural. We investigate pairwise testing between original and translated programs to detect such discrepancies. We filter and review challenge problems (akin to the SWE-bench Verified effort), build clear and usable documentation, and develop a website with leaderboards.

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

We note that the theorems we construct _may be false_---this is desirable because the AI has the opportunity to contradict the theorem (and perhaps identify a counter-example). Because the Lean theorem prover is a so-called _foundational_ tool, once a theorem is verified or contradicted, we have near-perfect confidence the answer is correct. However, because our specifications are translated rather than hand-written, some may not faithfully represent the original PBT. We expect our benchmark to exhibit a wide range of difficulty, including many problems that are trivial for current AIs, and many harder problems, including some insurmountable even to world-expert human teams.

// ---------------------------------------------------------------------------
// 6. Related Work
// ---------------------------------------------------------------------------

= Related Work <sec:related>

// FVAPPS / Proving the Coding Interview
// Other formal verification benchmarks
// LLM + formal methods
// Various criticisms

Our work extends the FVAPPS benchmark by Dougherty and Mehta, which pioneered AI-driven translation of coding problems into Lean theorems. In FVAPPS, source programs were taken from the APPS benchmark by Hendrycks et al, translated to PBTs, then lifted to theorems. We apply the same process at scale to PBTs found in the wild, rather than synthetic coding challenges.

Relevant benchmarks in formal verification include DafnyBench, a small hand-crafted benchmark, work on neural synthesis for SMT-assisted proof-oriented programming using expert-driven verification projects, and FrontierMath, which is focused on advanced mathematics rather than engineering. None of these are likely to be representative of real-world engineering tasks.

We also note the broader context of AI safety proposals premised on AI-driven formal verification, including the Guaranteed Safe AI agenda. If FV is to play this role, it must scale to the complexities of real-world engineered systems. Our benchmark is designed to measure whether such capabilities are possible.

// ---------------------------------------------------------------------------
// 7. Conclusion
// ---------------------------------------------------------------------------

= Conclusion <sec:conclusion>

#lorem(40)

== Future Work <sec:future>

Several extensions are possible:

- Add examples from other languages with significant usage of PBT, e.g. Haskell/QuickCheck, C++/RapidCheck.
- Translate our benchmark to other theorem proving systems, e.g. Coq, Isabelle, F\*, etc.
- More advanced website features, such as prediction markets about when the benchmark will be saturated, and a pipeline for submitting code to the leaderboard which we then persist into a training or SFT dataset.

Our benchmark will also be useful for developing new techniques in program repair and synthesis. If a property is disproven, this creates a new interesting challenge, namely to synthesize a patch to the original function such that the theorem now holds. We hypothesize that many such bugs will be particularly subtle and interesting edge cases since, by definition, in most cases they were not detected by the original developer's PBT harness.
