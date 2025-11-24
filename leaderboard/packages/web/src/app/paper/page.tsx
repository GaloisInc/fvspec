import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export const metadata = {
  title: 'Research Paper - fvspec',
  description: 'Read the full research paper on the fvspec benchmark',
}

export default function PaperPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Pre-Alpha Warning Banner */}
      <div className="border-b bg-red-500/10 border-red-500/20">
        <div className="container mx-auto px-4 py-3">
          <p className="text-center text-sm md:text-base font-semibold text-red-700 dark:text-red-400">
            ⚠️ STUB CONTENT — This is NOT the real paper. All text is AI-generated placeholder. ⚠️
          </p>
        </div>
      </div>

      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <Badge className="mb-4" variant="destructive">
            DRAFT STUB (NOT REAL PAPER)
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            fvspec: Evaluating AI Models on Formal Verification Tasks
          </h1>
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span>Authors: [To be added]</span>
            <span>•</span>
            <span>Institution: Galois, Inc.</span>
            <span>•</span>
            <span>Funding: ARIA (Advanced Research + Invention Agency)</span>
          </div>
          <div className="mt-6 flex gap-4">
            <Button variant="outline" asChild>
              <a href="/fvspec-paper.pdf" target="_blank" rel="noopener">
                Download PDF
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://arxiv.org/abs/XXXXX" target="_blank" rel="noopener noreferrer">
                arXiv
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
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-950/20 border-2 border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm font-semibold text-red-800 dark:text-red-300 mb-2">
              ⚠️ NOTICE: THIS IS NOT THE REAL PAPER ⚠️
            </p>
            <p className="text-xs text-red-700 dark:text-red-400 mb-2">
              This entire page contains AI-generated stub text for UI/UX mockup purposes ONLY. The
              abstract, results, claims, and references are all fake placeholder content.
            </p>
            <p className="text-xs font-semibold text-red-800 dark:text-red-300">
              Treat this exactly like lorem ipsum — it is NOT ready for reading, review, citation,
              or distribution.
            </p>
          </div>

          <Card className="mb-8 border-red-500/20 bg-red-500/5">
            <CardContent className="pt-6">
              <h2 className="text-xl font-bold mb-2">Abstract</h2>
              <p className="text-xs text-red-700 dark:text-red-400 font-semibold mb-4 uppercase">
                Stub text — Not the real abstract
              </p>
              <p className="text-muted-foreground leading-relaxed">
                We present <strong>fvspec</strong>, a benchmark for evaluating AI models on formal
                verification tasks using Lean 4. Unlike existing benchmarks that rely on synthetic
                problems, fvspec uses real-world property-based tests extracted from GitHub
                repositories, ensuring ecological validity and avoiding potential training data
                contamination. The benchmark extends FVAPPS (Dougherty & Mehta, 2025) by focusing on
                specification quality rather than complete implementations, and introduces two
                distinct verification paradigms: functional (FVAPPS-style recursion) and mvcgen
                (imperative with Hoare logic). We evaluate specifications using structural
                faithfulness metrics that provide objective quality assessments without requiring
                complete proofs. Our evaluation infrastructure integrates with the Lean Language
                Server Protocol (LSP) via Model Context Protocol (MCP) tools, enabling interactive
                development and immediate feedback. Initial results across leading language models
                demonstrate significant variation in specification quality, with models showing
                different strengths across verification paradigms. The benchmark is designed to
                track progress in AI-assisted formal verification while maintaining rigorous
                reproducibility through cryptographic attestations.
              </p>
            </CardContent>
          </Card>

          <section>
            <h2>1. Introduction</h2>
            <p>
              Formal verification—the process of mathematically proving software correctness—has
              traditionally required significant expertise and manual effort. Recent advances in
              large language models (LLMs) have sparked interest in automating aspects of this
              process, particularly for translating informal specifications into formal ones and
              generating proof sketches.
            </p>
            <p>
              However, evaluating progress in AI-assisted formal verification faces several
              challenges:
            </p>
            <ul>
              <li>
                <strong>Benchmark contamination:</strong> Synthetic problems may appear in training
                data
              </li>
              <li>
                <strong>Limited scope:</strong> Existing benchmarks focus on narrow problem classes
              </li>
              <li>
                <strong>Proof completeness bias:</strong> Requiring complete proofs excludes
                assessment of specification quality
              </li>
              <li>
                <strong>Reproducibility:</strong> Lack of standardized evaluation environments
              </li>
            </ul>
            <p>
              fvspec addresses these challenges through three key design decisions: (1) using
              real-world property-based tests from GitHub, (2) evaluating specification quality
              independently of proof completion, and (3) providing cryptographic attestations for
              all evaluation results.
            </p>
          </section>

          <section>
            <h2>2. Benchmark Design</h2>

            <h3>2.1 Problem Selection</h3>
            <p>
              We curate problems from real-world Python codebases that use Hypothesis for
              property-based testing. Each problem consists of:
            </p>
            <ul>
              <li>A Python function implementation</li>
              <li>One or more property-based tests using Hypothesis</li>
              <li>Dependency specifications and type annotations</li>
            </ul>
            <p>
              Problems are selected based on criteria including: implementation complexity (10-100
              lines), diverse algorithmic patterns, minimal external dependencies, and clear
              property specifications.
            </p>

            <h3>2.2 Verification Tracks</h3>
            <p>
              fvspec includes two distinct verification paradigms to assess model capabilities
              across different proof styles:
            </p>

            <h4>Functional Track</h4>
            <p>
              Following FVAPPS methodology, models translate Python code into recursive Lean 4
              functions. Specifications are expressed as theorems relating inputs to expected
              outputs, emphasizing structural correspondence with the original implementation.
            </p>

            <h4>MVCGen Track</h4>
            <p>
              Models produce imperative Lean 4 code using the MVCGen framework for Hoare logic
              verification. This requires identifying loop invariants, pre/post-conditions, and
              assertions, testing models&apos; ability to work with state-based reasoning.
            </p>

            <h3>2.3 Evaluation Metrics</h3>
            <p>We assess submissions using multiple dimensions:</p>
            <ul>
              <li>
                <strong>Structural Faithfulness:</strong> AST similarity to original Python
              </li>
              <li>
                <strong>Specification Correctness:</strong> Type-checking and semantic validity
              </li>
              <li>
                <strong>Build Success:</strong> Ability to compile with <code>lake build</code>
              </li>
              <li>
                <strong>Proof Progress:</strong> (Optional) Percentage of proof obligations
                discharged
              </li>
            </ul>
            <p>
              Notably, we use <code>sorry</code> placeholders rather than <code>axiom</code> to
              maintain computational properties while allowing partial specifications.
            </p>
          </section>

          <section>
            <h2>3. Infrastructure</h2>

            <h3>3.1 Interactive Development via MCP</h3>
            <p>
              We integrate Lean&apos;s Language Server Protocol with the Model Context Protocol,
              providing models with real-time feedback during specification generation. This enables
              iterative refinement based on type errors and proof state information.
            </p>

            <h3>3.2 Evaluation Environment</h3>
            <p>All submissions are evaluated in sandboxed Docker containers with:</p>
            <ul>
              <li>Network isolation (--network none)</li>
              <li>Resource limits (16GB memory, 2 hour timeout)</li>
              <li>Fixed Lean toolchain versions</li>
              <li>Deterministic dependency resolution</li>
            </ul>

            <h3>3.3 Cryptographic Attestations</h3>
            <p>
              Each evaluation produces a signed attestation including SHA-256 hashes of all
              artifacts, toolchain information, execution metadata, and runner trust level. This
              ensures full reproducibility and enables independent verification of results.
            </p>
          </section>

          <section>
            <h2>4. Initial Results</h2>
            <p>
              We evaluated several leading language models on an initial dataset of 200 problems.
              Preliminary results show:
            </p>
            <ul>
              <li>GPT-4o achieves 87.5% on functional track, 72.3% on MVCGen</li>
              <li>Claude 3.5 Sonnet: 84.2% functional, 68.9% MVCGen</li>
              <li>Significant variance in structural faithfulness across models</li>
              <li>Functional specifications generally easier than imperative with invariants</li>
            </ul>
            <p>
              Detailed analysis reveals that models struggle most with: (1) complex loop invariants,
              (2) dependent type refinements, and (3) maintaining correspondence with nested Python
              comprehensions.
            </p>
          </section>

          <section>
            <h2>5. Related Work</h2>
            <p>
              <strong>FVAPPS</strong> (Dougherty & Mehta, 2025): Our primary inspiration, focusing
              on coding interview problems with complete proofs.
            </p>
            <p>
              <strong>LeanDojo</strong>: Provides infrastructure for learning-based theorem proving
              but focuses on tactic generation rather than specification.
            </p>
            <p>
              <strong>ProofGPT/PISA</strong>: Evaluate proof search capabilities on existing Lean
              libraries, complementary to our specification-focused approach.
            </p>
            <p>
              <strong>SWE-bench</strong>: Software engineering benchmark using real GitHub issues;
              we adopt similar principles of ecological validity.
            </p>
          </section>

          <section>
            <h2>6. Conclusion and Future Work</h2>
            <p>
              fvspec provides a rigorous benchmark for tracking progress in AI-assisted formal
              verification. By emphasizing specification quality over proof completion and using
              real-world test cases, we aim to drive research toward practical verification
              assistance tools.
            </p>
            <p>Future directions include:</p>
            <ul>
              <li>Expanding to additional proof assistants (Coq, Isabelle)</li>
              <li>Multi-turn evaluation with LSP feedback loops</li>
              <li>Fine-grained error analysis and debugging scenarios</li>
              <li>Integration with continuous evaluation infrastructure</li>
            </ul>
          </section>

          <section>
            <h2>References</h2>
            <ol className="text-sm space-y-2">
              <li>
                Dougherty, D. and Mehta, S. (2025). &quot;Proving the Coding Interview: Formal
                Verification of Programming Puzzles.&quot; arXiv:2502.05714
              </li>
              <li>
                Yang, K. et al. (2023). &quot;LeanDojo: Theorem Proving with Retrieval-Augmented
                Language Models.&quot; NeurIPS 2023.
              </li>
              <li>
                Jiang, A. et al. (2023). &quot;Draft, Sketch, and Prove: Guiding Formal Theorem
                Provers with Informal Proofs.&quot; ICLR 2023.
              </li>
              <li>
                Jimenez, C. et al. (2024). &quot;SWE-bench: Can Language Models Resolve Real-world
                GitHub Issues?&quot; ICLR 2024.
              </li>
              <li>
                MacKinnon, D. et al. (2021). &quot;MVCGen: A Framework for Teaching Program
                Verification to Novices.&quot; PLDI 2021 Workshop.
              </li>
            </ol>
          </section>

          <section className="mt-12 border-t pt-8">
            <h2>Acknowledgments</h2>
            <p>
              This work was funded by the Advanced Research + Invention Agency (ARIA) under the
              Safeguarded AI programme. We thank the Lean community for infrastructure support and
              the open-source maintainers whose property-based tests form our benchmark dataset.
            </p>
          </section>
        </article>
      </main>
    </div>
  )
}
