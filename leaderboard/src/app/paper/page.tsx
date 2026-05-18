import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export const metadata = {
  title: 'Paper — FVSpec',
  description:
    'FVSpec: Real-World Property-Based Tests as Lean Challenges. A benchmark for evaluating AI models on real-world formal software verification.',
}

export default function PaperPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <Badge className="mb-4" variant="outline">
            Research Paper · NeurIPS 2026 (Evaluations &amp; Datasets)
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            FVSpec: Real-World Property-Based Tests as Lean Challenges
          </h1>
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span>Galois, Inc.</span>
            <span>•</span>
            <span>Funded by ARIA (Advanced Research + Invention Agency)</span>
          </div>
          <div className="mt-6 flex gap-4">
            <Button variant="outline" asChild>
              <a href="/fvspec-paper.pdf" target="_blank" rel="noopener">
                Download PDF
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a
                href="https://github.com/GaloisInc/fvspec"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub
              </a>
            </Button>
          </div>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <article className="prose prose-gray dark:prose-invert max-w-none">
          <Card className="mb-8">
            <CardContent className="pt-6">
              <h2 className="text-xl font-bold mb-4">Abstract</h2>
              <p className="text-muted-foreground leading-relaxed">
                We present a benchmark for evaluating AI models and agents on real-world formal
                software verification tasks. We first scrape 11,039 property-based tests (PBTs)
                from real-world Python repositories, then automatically translate them into Lean
                4 specifications with <code className="font-mono">sorry</code> placeholders.
                Translating PBTs into Lean specifications is challenging: it requires modeling
                Python semantics in Lean, inferring the logical property encoded in an
                imperative PBT, and handling the inherent difficulties of dependently-typed
                programming in a seldom-used language. We describe a three-agent LLM pipeline
                for transpiling PBTs into Lean specifications, evaluate coverage and quality
                metrics, and provide baselines for proof generation using several automated and
                model-based approaches. Our benchmark aims to drive progress on the
                underexplored problem of AI-assisted formal verification of real-world software,
                which is of increasing interest as AI produces more and more of the world&apos;s
                code.
              </p>
            </CardContent>
          </Card>

          <section>
            <h2>1. Introduction</h2>
            <p>
              Several AI safety proposals are premised on implementing safeguards by way of{' '}
              <em>formal verification</em> (FV) — that is, software systems that can produce
              and unequivocally certify mathematical proofs. ARIA&apos;s Safeguarded AI,
              Guaranteed Safe AI, and Scalable Formal Oversight, among others, all suggest that
              in the future, all AI-generated software will be formally verified by autonomous
              FV agents, who will steer interactive theorem provers in much the same way that
              coding agents currently steer software production.
            </p>
            <p>
              The only way FV can play this role is if agents can conduct verification work at
              least as well and as quickly as they can produce code. Otherwise, FV becomes a
              bottleneck and will naturally wither under the capital pressure to iterate. There
              is currently little evidence that such capabilities are possible. To achieve them,
              we would first need high-quality benchmarks to train on. Existing benchmarks are
              too small, focused on advanced mathematics rather than engineering, or derived
              from expert-driven verification projects which are quite different from what you
              would get were you to verify the average software project.
            </p>
            <p>
              In light of the limitations of prior works, we generate a new benchmark, FVSpec,
              from public uses of property-based testing (PBT). While FV itself is rarely used
              in software development, PBT is a &ldquo;close sibling&rdquo; technology which has
              seen significant adoption. In both FV and PBT, engineers write{' '}
              <em>specifications</em>: logical properties that the software must obey. In FV,
              the property is proved using mathematical techniques — almost-perfect confidence,
              but requires proof engineering by highly expert teams. In PBT, the code is
              randomly tested — a push-button process with no proof engineering, providing only
              statistical assurance.
            </p>
            <p>
              We scrape 11,039 PBTs written in Python&apos;s Hypothesis framework. Each PBT can
              be seen as a formal conjecture about a piece of Python code, which the author
              would like to either substantiate (prove) or disprove. We refer to our scraped
              PBT corpus as <strong>FVSpec:PBT</strong>. To make it possible for an AI to
              resolve these conjectures, we translate both code and PBTs to Lean. We refer to
              our resultant corpus of Lean translations as <strong>FVSpec:FV</strong>.
            </p>
            <p>
              The result is 9,415 Lean 4 verification challenges. Each consists of four
              artifacts: the original Python implementation; the original Python PBT exercising
              it; a complete Lean implementation of the same function; and a Lean theorem
              statement of the property with a <code>sorry</code> for the proof. Unlike existing
              FV benchmarks, each problem corresponds to real-world software written by
              engineers with no formal verification experience — putting our problems out of
              distribution relative to anything an AI is likely to have memorized.
            </p>
            <h3>Contributions</h3>
            <ul>
              <li>
                <strong>FVSpec:PBT</strong> — a corpus of 11,039 deduplicated Python
                property-based tests scraped from 333 open-source repositories, the first large,
                license-clean PBT dataset drawn from ordinary software development (no
                competition problems, no curated ITP code).
              </li>
              <li>
                <strong>FVSpec:FV</strong> — 9,415 Lean 4 formal verification challenge samples
                (mean ~8 theorems per sample; 75,005 theorems total) lifted from 2,772 of those
                PBTs by an agentic transpilation pipeline with iterative LSP repair, each
                annotated with structural faithfulness scores (median 0.65), a difficulty label
                (62% hard, ~70% calibrated), and full artifact metadata.
              </li>
              <li>
                <strong>Baseline evaluations</strong> of Claude Sonnet 4.6, Claude Opus 4.7,
                and GPT 5.4, showing mean 70% on easy problems and mean 49% on hard problems.
              </li>
              <li>
                <strong>Open-source release</strong> of the full pipeline — scraper, dependency
                extractor, formalization agent, and post-production scripts — under an
                MIT/Apache dual license.
              </li>
            </ul>
          </section>

          <section>
            <h2>2. Property-Based Test Corpus (FVSpec:PBT)</h2>
            <p>
              We scrape real-world Python property-based tests from public GitHub repositories
              that depend on Hypothesis. Our scraper operates in three stages.{' '}
              <em>Discovery:</em> we crawl the Hypothesis dependency graph and persist 19,808
              unique <code>owner/repo</code> pairs into a static snapshot.{' '}
              <em>Licensing:</em> we skip repositories with an explicitly non-permissive license
              (AGPL, GPL, LGPL, MPL), and record the license string alongside each
              repository&apos;s metadata. <em>Extraction:</em> we shallow-clone each accepted
              repository, locate PBTs via <code>ripgrep</code>, and parse the surrounding
              Python to recover the transitive closure of locally-defined functions called
              therein.
            </p>
            <p>
              A 24-hour run produced 54,345 raw PBTs. The GitHub dependency graph surfaces many
              forks of the same upstream, so we group repositories by base name, retain the
              most-starred canonical fork per group, and drop tests whose whitespace-normalized
              SHA-256 already appears in the canonical set. After deduplication the working
              corpus is <strong>11,039 PBTs across 333 repositories</strong> owned by 281
              distinct GitHub users, spanning 303 distinct upstream project names.
            </p>
            <h3>Diversity</h3>
            <p>
              A perennial concern with scraped benchmarks is concentration: SWE-bench, for
              instance, draws all 2,294 of its task instances from just 12 repositories, with{' '}
              <code>django</code> alone supplying 37%. Our corpus is far more spread out — no
              single repository contributes more than 8.7% of the PBTs, the top ten together
              contribute 58.5%, and most contributing repositories are unstarred personal
              projects rather than curated showcase code. The median PBT is just 13 LoC, but
              exercises around 3× its own length in project code.
            </p>
          </section>

          <section>
            <h2>3. The PBT → FV Pipeline</h2>
            <p>
              We lift each PBT into a Lean (<code>Impl.lean</code>, <code>Spec.lean</code>)
              pair in three phases: function discovery, agentic transpilation, and
              post-production.
            </p>
            <h3>Function discovery</h3>
            <p>
              For each PBT we use tree-sitter to extract the function under test (FUT) and the
              transitive closure of its locally-defined dependencies. When discovery fails —
              typically due to metaclasses, decorators, or other dynamic dispatch — we emit a
              stub FUT with generic type parameters so the formalization agent still receives
              well-formed input.
            </p>
            <h3>Agentic transpilation</h3>
            <p>
              A single formalization agent translates each sample, producing both{' '}
              <code>Impl.lean</code> (a computable port of the FUT and its dependencies, no{' '}
              <code>sorry</code>) and <code>Spec.lean</code> (one theorem per Hypothesis
              assertion, with proofs left as <code>sorry</code>). After each generation step we
              type-check the output via the Lean LSP (over MCP) and <code>lake build</code>;
              on failure, the compiler diagnostics are fed back to the agent and a revised
              translation is requested. The loop terminates on success or after 16
              tool-iterations.
            </p>
            <h3>Post-production and structural faithfulness</h3>
            <p>
              We extract LLM turn counts from the raw <code>.eval</code> archives, collapse
              runs into a single JSONL, deduplicate by sample id, re-run <code>lake build</code>{' '}
              and drop failures, and assign a binary easy/hard label using{' '}
              <code>claude-haiku-4-5</code> as judge. We score each sample using{' '}
              <em>structural faithfulness</em>, a fixed weighted average of five sub-scores
              measuring how much of a Python-side artifact survives translation:
            </p>
            <pre className="text-sm">
              <code>
                S = 0.25·S_param + 0.25·S_type + 0.20·S_strat + 0.20·S_assert + 0.10·S_dep
              </code>
            </pre>
            <p>
              capturing parameter coverage, type correspondence, strategy coverage, assertion
              coverage, and dependency coverage. Sub-scores ship alongside the overall score so
              consumers can re-weight or filter.
            </p>
            <h3>Pipeline yield</h3>
            <p>
              The published FVSpec:FV dataset contains <strong>9,415 samples</strong> drawn
              from <strong>2,772 distinct PBTs</strong>: formalization succeeded for 2,772 of
              11,039 input PBTs (25%); the rest were dropped by <code>lake build</code>. The
              mean sample carries 8 theorems (median 6, max 66) and median structural
              faithfulness 0.65. A complete Lean implementation was generated for 59% of
              samples; the remaining 41% ship against a stub <code>Impl.lean</code>. The Claude
              Haiku grader splits the dataset 62%/38% hard/easy.
            </p>
          </section>

          <section>
            <h2>4. Benchmark Characterization &amp; Baselines</h2>
            <p>
              Translation quality, evaluated by structural faithfulness, shows a clear mode
              above 0.5 — the majority of translations preserve the essential structure of the
              source PBT. Type correspondence (1.00) and assertion coverage (0.97) are
              near-saturated, while parameter coverage (0.24) and dependency coverage (0.48)
              are the weak links.
            </p>
            <p>
              We evaluate three frontier models (Claude Sonnet 4.6, Claude Opus 4.7, and GPT
              5.4) on 100 randomly sampled easy problems and 100 hard problems. Each model has
              access to the Lean LSP via MCP tools and is scored on two metrics: a binary{' '}
              <em>proved</em> flag (zero <code>sorry</code> remaining and{' '}
              <code>lake build</code> succeeds) and <em>partial credit</em> (fraction of{' '}
              <code>sorry</code> placeholders removed). Across the three models, mean
              performance is <strong>70% on easies</strong> and <strong>49% on hards</strong>,
              confirming the benchmark is far from saturated.
            </p>
          </section>

          <section>
            <h2>5. Threats to Validity</h2>
            <p>
              The most consequential threat is whether theorems stated over uninterpreted
              axioms actually mean anything about the original Python. Most PBTs in our corpus
              touch Redis, sockets, the filesystem, the wall clock, webhook queues, and so
              forth. The formalization agent handles this by treating the effectful world as an{' '}
              <em>uninterpreted interface</em>: parts of the source essential to the property
              are translated into Lean structures and inductive types; parts that are pure
              plumbing are introduced as opaque <code>axiom</code> declarations and threaded
              through the theorem as parameters. The resulting theorem holds over all
              interpretations of those axioms, which is exactly the contract the original PBT
              was checking against the live environment.
            </p>
            <p>
              The axiomatization move is not a universal solvent. Properties fundamentally
              about timing, memory, or ordering of side effects cannot be witnessed by
              uninterpreted axioms. Effectful code disguised as pure code may be inlined as if
              pure, producing a theorem that compiles but does not constrain the original
              behavior. And axioms necessarily omit consistency guarantees, ordering, or
              failure modes of the real APIs they stand in for.
            </p>
            <p>
              Other threats: specifications are translated rather than hand-written, so some
              may not faithfully represent the original PBT (our structural-faithfulness score
              is a heuristic). Difficulty labels come from an LLM grader whose judgments are
              imperfect and uncalibrated against human expert performance. The 41% stub-Impl
              tail weakens the proof obligation: the theorem is well-typed but the body it
              constrains is opaque. We do not measure human expert performance and therefore
              cannot calibrate difficulty against the proof effort required of skilled humans.
            </p>
          </section>

          <section>
            <h2>6. Conclusion</h2>
            <p>
              FVSpec is a benchmark of 9,415 Lean 4 formal verification challenges derived from
              11,039 real-world Python property-based tests scraped from 333 open-source
              repositories. Unlike prior FV benchmarks — which draw from expert-written ITP
              code, competitive programming problems, or curated verification exercises —
              FVSpec sources its specifications directly from practicing engineers who had no
              formal verification intent. Baseline evaluations of two frontier models confirm
              that the benchmark is far from saturated, particularly on hard problems, leaving
              substantial room for progress on AI-assisted formal verification of ordinary
              software. Natural extensions include incorporating PBTs from other languages
              (Haskell/QuickCheck, C++/RapidCheck, TypeScript/fast-check) and other ITPs (Coq,
              Isabelle, F⋆, Verus), and using disproved properties as seeds for program-repair
              challenges — bugs the original developer&apos;s test harness missed, now made
              precise in Lean.
            </p>
          </section>

          <section className="mt-12 border-t pt-8">
            <h2>Acknowledgments</h2>
            <p>
              This work was funded by the Advanced Research + Invention Agency (ARIA). We
              thank the Lean community for infrastructure support and the open-source
              maintainers whose property-based tests form our benchmark dataset.
            </p>
          </section>
        </article>
      </main>
    </div>
  )
}
