# Axiomatised interfaces: how FV-Spec absorbs effectful source PBTs

A reviewer will reasonably ask: *the source PBTs come from real
production code. Real production code touches Redis, sockets, the
filesystem, the wall clock, GitHub webhooks. How can the resulting Lean
theorems possibly say anything meaningful about that?* The answer is
that the formalisation agent treats the effectful world as an
*uninterpreted interface*: the parts of the source that are essential
to the property under test are translated into Lean structures and
inductive types, and the parts that are mere plumbing — the database,
the queue, the system clock — are introduced as opaque `axiom`
declarations and threaded through the theorem statements as parameters.
A theorem holds *over all interpretations* of those axioms, which is
exactly the contract the original PBT was checking against the live
environment.

A canonical instance is `test_workflow_job_time_to_start`, drawn from
[`scality/runner-manager`][rm] (a GitHub Actions self-hosted runner
controller). The Python PBT initialises Redis-backed model classes,
runs an ORM migrator, calls `datetime.now()` to fabricate two timestamps
straddling a runner-startup timeout, enqueues a webhook through a
background job queue, and asserts on the resulting runner count. The
fvspec translation introduces seventeen axioms — including
`axiom Redis : Type`, `axiom Queue : Type`, `axiom State : Type`,
`axiom State.after_enqueue : State → RunnerGroup → WorkflowJobEvent →`
`ExtendedSettings → State`, and
`axiom get_runners : RunnerGroup → State → List Runner` — and then
states the behavioural contract purely in terms of these uninterpreted
state-transition operators:

```lean
theorem create_runner_when_above_timeout
  (...)
  (h_initial_count : (get_runners runner_group initial_state).length = 1)
  (h_below_max    : 1 < runner_group.max)
  (h_above_timeout : started_at - created_at > settings.timeout_runner)
  (h_enqueue : state_after_enqueue =
    State.after_enqueue initial_state runner_group webhook_updated settings)
  : (get_runners runner_group state_after_enqueue).length = 2 := by
  sorry
```

This is genuinely different from what a benchmark drawn from Mathlib,
HumanEval, or a pedagogical FV corpus can ask of a model. Those
corpora pre-select for problems that are *self-contained by
construction*: a number-theoretic identity, a small algorithm with no
side-effects, a closed-world data structure. FV-Spec's source
distribution does the opposite — it pre-selects for properties that
practitioners actually wanted to test, which means the theorems carry
the shape of real software: state machines, external services, time,
concurrency. The axiomatisation step is what converts that shape into a
well-formed proof obligation without losing it. A model proving
`create_runner_when_above_timeout` is reasoning about a scheduler's
state-transition semantics under a timeout precondition; the fact that
the underlying scheduler in production talks to Redis is no more
load-bearing in the theorem than the choice of register allocator is in
a correctness proof of a sorting algorithm. We claim this is the
honest way to ship FV evaluation problems sourced from real code, and
that no existing FV benchmark does it because none of them source from
real code in the first place.

[rm]: https://github.com/scality/runner-manager
