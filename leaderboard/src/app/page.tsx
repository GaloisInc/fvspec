import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ArrowRight } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="border-b bg-gradient-to-b from-background to-muted/20">
        <div className="container mx-auto px-4 py-16 md:py-24">
          <div className="max-w-3xl">
            <Badge variant="outline" className="mb-4 text-xs">
              FVSpec
            </Badge>
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-4">
              Real-World Property-Based Tests as Lean Challenges
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground mb-8">
              A benchmark for evaluating AI models and agents on real-world formal software
              verification.
            </p>
            <div className="flex flex-wrap gap-4">
              <Button size="lg" asChild>
                <Link href="/dataset">
                  Explore the Dataset
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/paper">Read the Paper</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="border-b">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold mb-4">About FVSpec</h2>
            <p className="text-lg text-muted-foreground mb-4">
              We scrape 11,039 property-based tests (PBTs) from real-world Python repositories, then
              automatically translate them into Lean 4 specifications with{' '}
              <code className="font-mono text-sm">sorry</code> placeholders. The result is a corpus
              of 9,415 Lean 4 verification challenges authored, in effect, by practicing engineers
              who had no formal verification goal in mind — putting our problems out of distribution
              relative to anything an AI is likely to have memorized.
            </p>
            <p className="text-lg text-muted-foreground mb-8">
              Translating PBTs into Lean specifications is challenging: it requires modeling Python
              semantics in Lean, inferring the logical property encoded in an imperative PBT, and
              handling the inherent difficulties of dependently-typed programming in a seldom-used
              language. We describe a three-agent LLM pipeline for transpilation, evaluate coverage
              and quality metrics, and provide baselines for proof generation using several
              automated and model-based approaches.
            </p>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">11,039</div>
                  <CardTitle className="text-base">Property-Based Tests</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Deduplicated Hypothesis PBTs scraped from public GitHub
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">9,415</div>
                  <CardTitle className="text-base">Lean 4 Challenges</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Samples lifted from 2,772 PBTs (~8 theorems each, 75,005 total)
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">333</div>
                  <CardTitle className="text-base">Source Repositories</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Permissively-licensed Python projects from 281 distinct GitHub owners
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">62%</div>
                  <CardTitle className="text-base">Hard Problems</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Classified as hard by a calibrated difficulty predictor — far from saturated
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* Baselines Section */}
      <section className="border-b">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold mb-2">Baselines</h2>
            <p className="text-muted-foreground mb-8">
              We evaluate frontier models on 100 randomly sampled easy problems and 100 hard
              problems. Each model has access to the Lean LSP via MCP tools and is scored on a
              binary <em>proved</em> flag (zero <code className="font-mono text-sm">sorry</code>{' '}
              remaining and <code className="font-mono text-sm">lake build</code> succeeds) and{' '}
              <em>partial credit</em> (fraction of <code className="font-mono text-sm">sorry</code>{' '}
              placeholders removed).
            </p>
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">
                  Across Claude Sonnet 4.6, Claude Opus 4.7, and GPT 5.4, models average{' '}
                  <strong>70%</strong> on easy problems and <strong>49%</strong> on hard problems —
                  the benchmark is far from saturated.
                </p>
                <Button variant="outline" asChild className="mt-6">
                  <Link href="/paper">
                    See full results
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Paper Section */}
      <section className="border-b">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <Link href="/paper" className="block group">
              <Card className="transition-all hover:shadow-lg hover:border-primary/50">
                <CardHeader>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <Badge className="mb-3">Research Paper</Badge>
                      <CardTitle className="text-2xl mb-2 group-hover:text-primary transition-colors">
                        FVSpec: Real-World Property-Based Tests as Lean Challenges
                      </CardTitle>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                  </div>
                </CardHeader>
                <CardContent>
                  <h3 className="font-semibold mb-3">Abstract</h3>
                  <p className="text-muted-foreground leading-relaxed text-sm">
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
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto text-center text-sm text-muted-foreground space-y-3">
            <p>
              FVSpec extends{' '}
              <a
                href="https://arxiv.org/abs/2502.05714"
                className="hover:underline font-medium"
                target="_blank"
                rel="noopener noreferrer"
              >
                FVAPPS
              </a>{' '}
              with real-world property-based tests. Funded by{' '}
              <a
                href="https://aria.org.uk"
                className="hover:underline font-medium"
                target="_blank"
                rel="noopener noreferrer"
              >
                ARIA
              </a>
              .
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
