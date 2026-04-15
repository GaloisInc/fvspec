# Spin: FV-Spec → NeurIPS 2026 Evaluations & Datasets Track

Source for the target venue:
<https://blog.neurips.cc/2026/03/23/introducing-the-evaluations-datasets-track-at-neurips-2026/>

## What the track actually wants

The old "Datasets & Benchmarks Track" is now the **Evaluations & Datasets
(E&D) Track**. Reframing, not rebrand:

- Evaluation is a **scientific object** in its own right, not a procedural
  step on the way to a model paper.
- Definition is broad: "Processes, practices, tools, and resources for
  making evaluative claims about AI/ML systems, including — but not limited
  to — datasets, benchmarks, user studies, simulators, auditing, red-teaming
  methods..."
- Stated motivation: as ML matures, "evaluation methodology more frequently
  determines the conclusions we draw." Disagreement often stems from
  "differences in evaluation design, assumptions, and reporting practices."
- Things the CFP explicitly welcomes:
  - Analyses of limitations / failure modes of existing evaluation
    practices.
  - Studies of benchmark saturation and overfitting.
  - Rigorous reproductions and stress-tests of prior evaluations.
  - Documentation methodologies that improve evaluative claims.
  - Datasets with clear explanations of scope, assumptions, and limitations.
  - Negative results and critical analyses.
- **Hard requirement**: a dataset must articulate its "relationship to
  evaluative claims" and spell out how models trained/used with it should be
  *meaningfully assessed*. Just dumping data is out of scope.
- Submissions do **not** need novel models or SOTA baselines. Advancing
  understanding of evaluation practices is sufficient.

Implication: the reviewers will be reading for epistemic hygiene, not for a
leaderboard win. This is very good for us — we do not (yet) have baselines
that make a pretty table. We *do* have a lot to say about what a meaningful
evaluation of AI-assisted formal verification looks like.

---

## Angles to spin (ranked, best-fit first)

### 1. "FV benchmarks are contaminated; we built one that structurally can't be."

The strongest story for this venue. Existing Lean/FV benchmarks
(miniCodeProps, CLEVER, Verina, VeriBench, LeanDojo, CoqStoq) draw from
pedagogical corpora, HumanEval derivatives, or Mathlib — all of which appear
many times over in pretraining, often with proofs attached. We translate
from a **sibling domain** (Hypothesis PBTs) that has never been formally
verified by anyone. The evaluative claim — "model X can prove property Y" —
is defensible here in a way it is not for benchmarks that quietly measure
memorisation.

Spin moves:
- Lead with a *meta-contribution*: a critique of how current FV benchmarks
  enable unfalsifiable claims of progress, then present FV-Spec as the
  corrective.
- Include a contamination audit of prior benchmarks (grep frontier model
  training-data proxies for theorem statements; cite the overlap between
  Mathlib and LeanDojo).
- Position the *source domain shift* (PBT → proof) as a principled defence
  against saturation: new PBTs are written every week, so the benchmark is
  refreshable on a schedule.

### 2. "Structural faithfulness is a new evaluation methodology for translation benchmarks."

Any benchmark built by LLM translation inherits a *second-order* evaluation
problem: how do you know the translated task still measures what the
original measured? We have an answer — a programmatic decomposition into
parameter coverage, type correspondence, strategy coverage, assertion
coverage, and dependency coverage, yielding a weighted score. Reviewers at
an *evaluation* venue should find this more interesting than the benchmark
itself.

Spin moves:
- Promote the faithfulness metric from §3 subsection to a **first-class
  contribution** with its own section, validation study, and ablations.
- Compare against the obvious alternatives (LLM-judge of equivalence,
  round-trip back-translation, pairwise execution testing) and show where
  each fails.
- Release the metric as a reusable tool, not just as a column in our
  dataset — a documentation methodology improving evaluative claims, which
  is one of the CFP's explicit calls.

### 3. "A foundational oracle converts translation noise into useful signal."

The standard complaint about LLM-translated benchmarks: some fraction of
items are semantically wrong. Our frame flips this: because Lean is a
foundational theorem prover, *every well-typed theorem is a real challenge
problem*, even if it drifts from the source PBT. A mistranslated theorem is
still a theorem. This is a genuinely interesting epistemological point that
suits the venue's "scope, assumptions, limitations" requirement.

Spin moves:
- Dedicate a subsection to "what our benchmark actually evaluates" — it is
  *not* a measurement of how well a model understands Python code; it is a
  measurement of how well a model discharges Lean goals drawn from a
  realistic distribution of software properties.
- Be explicit about the assumption chain: (Python PBT ≈ developer's real
  belief) → (Lean translation ≈ Python PBT) → (Lean proof ⇒ Lean theorem).
  Only the last link is airtight. The middle is what the faithfulness
  metric measures. The first is unchanged from ordinary PBT practice.

### 4. "Difficulty distribution as an evaluation artefact, not a nuisance."

We have Haiku-assessed 1–10 difficulty per item, plus a clear view that the
distribution covers trivial-for-AI through open-math-problem. Most benchmark
papers hide this. We can foreground it: *difficulty-stratified reporting*
is the right way to make evaluative claims about FV systems, because a
single pass@1 number across a mixed-difficulty benchmark is almost
meaningless.

Spin moves:
- Add per-stratum baselines instead of a single aggregate. Even two crude
  baselines (tactic hammer, frontier model) become interesting when broken
  out by difficulty bucket.
- Show that existing benchmarks have narrow difficulty ranges (they do —
  pedagogical problems cluster) and ours does not.
- Argue this is why cross-benchmark comparison in FV has been broken: you
  cannot compare "71% on CLEVER" to "44% on Verina" without the difficulty
  distribution.

### 5. "No human baselines, and why that's defensible here."

Already in the draft as a threat to validity. The E&D track rewards honest
negative-space discussion. Reframe: human baselines on FV tasks are not
merely unavailable, they are **not the right comparator** — human proof
engineers aren't trying to do what the AI is doing (cold-start, no repo
context, no collaborator). State what *would* be a better comparator
(calibrated difficulty + tactic-hammer floor + frontier-model ceiling) and
deliver that instead.

### 6. "Negative result on the TypeScript extension."

We briefly considered TypeScript PBTs and dropped it because the ecosystem
is immature. The CFP explicitly welcomes negative results. A short, honest
subsection documenting what failed and why is cheap to add and flatters the
venue.

### 7. "Benchmark-as-process, not benchmark-as-artefact."

The pipeline is the contribution as much as the dataset is: tree-sitter
discovery + impl agent + spec agent + units agent + LSP repair loop +
faithfulness grading + difficulty grading. Spin the whole pipeline as a
**reusable evaluation-construction toolkit** for turning any PBT corpus
into a proof benchmark. Future researchers can apply it to QuickCheck,
RapidCheck, Hedgehog, etc. — i.e. we are proposing a methodology, not just
shipping files.

### 8. "Program repair as a downstream evaluation mode."

Mike's future-work bullet (if a property is disproven, synthesise a patch)
becomes a second evaluation mode packaged with the same dataset: proof
generation *or* counter-example-driven repair. Two evaluative claims for
the price of one corpus, each with a different epistemic profile.

---

## Recommended framing for the paper

Use **(1) + (2)** as the headline contributions and demote the benchmark
itself to the infrastructure that makes those contributions possible:

> "We argue that current AI-for-FV benchmarks conflate three distinct
> evaluative claims — memorisation, proof search, and library modelling —
> and cannot separate them because their source problems are contaminated
> and pedagogical. We propose *translation from a sibling domain* as a
> methodology for building evaluations that isolate the second claim, and
> *structural faithfulness* as a documentation standard that lets readers
> audit the translation. FV-Spec is our instantiation: N thousand Lean
> theorems translated from real-world Hypothesis PBTs, each annotated with
> a five-dimensional faithfulness score and a calibrated difficulty grade.
> Baselines are illustrative rather than definitive; our primary
> contribution is the evaluation design itself."

This reads as an E&D paper. The current draft reads as a benchmarks-track
paper. The difference is ~2 sections of reframing and one honest
re-ordering of contributions — the research is the same.

---

## What to NOT lean on

- Pure size ("thousands rather than hundreds"). The venue doesn't care.
- Leaderboard narrative. We don't have one yet, and the CFP says we don't
  need one.
- Safeguarded AI / ARIA framing in the lede. Keep it as motivation, not as
  the pitch — reviewers will be mixed on policy-adjacent framings, and the
  evaluation-methodology frame is strictly stronger.
- "We used MCP / Claude / agents." Implementation detail. Foreground the
  pipeline's evaluation-construction properties, not its stack.

---

## Concrete next actions if we adopt this spin

1. Rewrite the abstract and §1 around claims (1) and (2). Half a day.
2. Promote structural faithfulness to its own section with a validation
   study (sample N items, hand-label semantic equivalence, correlate with
   the metric). One-to-two days of labelling plus writing.
3. Add a contamination audit table comparing FV-Spec against
   miniCodeProps / CLEVER / Verina / VeriBench / LeanDojo on provenance,
   prior-verification status, and difficulty spread. Half a day.
4. Break baseline results out by difficulty stratum. Depends on what we
   already have from `/baselines`.
5. Write the TypeScript negative-result paragraph. Thirty minutes.
6. Add a "what this benchmark does and does not evaluate" subsection with
   the explicit assumption chain from angle (3). One hour.
