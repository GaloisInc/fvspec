import Image from 'next/image'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export const metadata = {
  title: 'Paper — FVSpec',
  description:
    'FVSpec: Real-World Property-Based Tests as Lean Challenges. A benchmark for evaluating AI models on real-world formal software verification.',
}

const figures = [
  {
    src: '/figures/pipeline_cost.png',
    alt: 'Pipeline cost breakdown across formalization stages',
    caption: 'Figure 1. Compute cost of the PBT → FV pipeline, broken down by stage.',
  },
  {
    src: '/figures/structural_faithfulness.png',
    alt: 'Distribution of structural faithfulness scores',
    caption: 'Figure 2. Structural faithfulness of translations, with a clear mode above 0.5.',
  },
  {
    src: '/figures/difficulty_distribution.png',
    alt: 'Distribution of easy/hard difficulty labels across the dataset',
    caption: 'Figure 3. Easy/hard difficulty split assigned by the Claude Haiku grader.',
  },
  {
    src: '/figures/baselines_pass_at_k_curve.png',
    alt: 'Baseline pass@k curves for Sonnet, Opus, and GPT',
    caption:
      'Figure 4. Pass@k for Claude Sonnet 4.6, Claude Opus 4.7, and GPT 5.4 on easy vs. hard problems.',
  },
]

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
          <div className="mt-6 flex flex-wrap gap-4">
            <Button variant="outline" asChild>
              <a href="/fvspec_anon.pdf" target="_blank" rel="noopener">
                Download PDF
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://arxiv.org/abs/2606.01008" target="_blank" rel="noopener noreferrer">
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
        <Card className="mb-10">
          <CardContent className="pt-6">
            <h2 className="text-xl font-bold mb-4">Abstract</h2>
            <p className="text-muted-foreground leading-relaxed">
              We present a benchmark for evaluating AI models and agents on real-world formal
              software verification tasks. We first scrape 11,039 property-based tests (PBTs) from
              real-world Python repositories, then automatically translate them into Lean 4
              specifications with <code className="font-mono">sorry</code> placeholders. Translating
              PBTs into Lean specifications is challenging: it requires modeling Python semantics in
              Lean, inferring the logical property encoded in an imperative PBT, and handling the
              inherent difficulties of dependently-typed programming in a seldom-used language. We
              describe a three-agent LLM pipeline for transpiling PBTs into Lean specifications,
              evaluate coverage and quality metrics, and provide baselines for proof generation
              using several automated and model-based approaches. Our benchmark aims to drive
              progress on the underexplored problem of AI-assisted formal verification of real-world
              software, which is of increasing interest as AI produces more and more of the
              world&apos;s code.
            </p>
          </CardContent>
        </Card>

        <section className="mb-10">
          <h2 className="text-xl font-bold mb-6">Figures</h2>
          <div className="grid gap-8">
            {figures.map(fig => (
              <figure key={fig.src} className="space-y-3">
                <div className="rounded-lg border bg-white p-4">
                  <Image
                    src={fig.src}
                    alt={fig.alt}
                    width={1600}
                    height={1000}
                    className="h-auto w-full"
                    sizes="(max-width: 768px) 100vw, 768px"
                  />
                </div>
                <figcaption className="text-sm text-muted-foreground">{fig.caption}</figcaption>
              </figure>
            ))}
          </div>
        </section>

        <section className="border-t pt-8">
          <p className="text-muted-foreground">
            For the full paper — including methodology, dataset construction, baseline experiments,
            and threats to validity — see the{' '}
            <a href="/fvspec_anon.pdf" target="_blank" rel="noopener" className="underline">
              PDF
            </a>{' '}
            or the{' '}
            <a
              href="https://arxiv.org/abs/2606.01008"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              arXiv version
            </a>
            .
          </p>
        </section>
      </main>
    </div>
  )
}
