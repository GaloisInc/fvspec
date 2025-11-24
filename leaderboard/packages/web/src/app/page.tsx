import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ArrowRight } from 'lucide-react'

// Mock data - replace with API calls later
const topSubmissions = [
  {
    id: 1,
    rank: 1,
    model: 'GPT-4o',
    organization: 'OpenAI',
    score: 87.5,
    passRate: '175/200',
    status: 'verified',
  },
  {
    id: 2,
    rank: 2,
    model: 'Claude 3.5 Sonnet',
    organization: 'Anthropic',
    score: 84.2,
    passRate: '168/200',
    status: 'verified',
  },
  {
    id: 3,
    rank: 3,
    model: 'Gemini 2.0 Flash',
    organization: 'Google',
    score: 79.8,
    passRate: '159/200',
    status: 'verified',
  },
  {
    id: 4,
    rank: 4,
    model: 'Claude 3 Opus',
    organization: 'Anthropic',
    score: 76.3,
    passRate: '152/200',
    status: 'verified',
  },
  {
    id: 5,
    rank: 5,
    model: 'GPT-4 Turbo',
    organization: 'OpenAI',
    score: 73.1,
    passRate: '146/200',
    status: 'verified',
  },
]

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* Pre-Alpha Warning Banner */}
      <div className="border-b bg-yellow-500/10 border-yellow-500/20">
        <div className="container mx-auto px-4 py-3">
          <p className="text-center text-sm md:text-base font-semibold text-yellow-700 dark:text-yellow-400">
            ⚠️ PRE-ALPHA PREVIEW — Leaderboard shows mockup data. Paper abstract is draft stub. Do
            not share publicly. ⚠️
          </p>
        </div>
      </div>

      {/* Hero Section */}
      <section className="border-b bg-gradient-to-b from-background to-muted/20">
        <div className="container mx-auto px-4 py-16 md:py-24">
          <div className="max-w-3xl">
            <Badge variant="outline" className="mb-4 text-xs">
              PRE-ALPHA PREVIEW
            </Badge>
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-4">
              fvspec Leaderboard
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground mb-8">
              Evaluating AI models on formal verification tasks in Lean 4
            </p>
            <div className="flex flex-wrap gap-4">
              <Button size="lg" asChild>
                <Link href="/leaderboard">
                  View Full Leaderboard
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/submit">Submit Your Model</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="border-b">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold mb-4">About fvspec</h2>
            <p className="text-lg text-muted-foreground mb-8">
              fvspec is a benchmark for evaluating AI models on formal verification tasks. Models
              translate Python property-based tests into Lean 4 specifications, focusing on
              specification quality and structural faithfulness.
            </p>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">200</div>
                  <CardTitle className="text-base">Benchmark Problems (target)</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Real-world property-based tests from GitHub, not synthetic puzzles
                  </p>
                  <p className="text-xs text-muted-foreground italic mt-2">
                    Initial dataset is smaller and preliminary
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">2</div>
                  <CardTitle className="text-base">Verification Tracks</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Functional (FVAPPS-style) and MVCGen (imperative with Hoare logic)
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="text-4xl font-bold">?</div>
                  <CardTitle className="text-base">Model Submissions</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Cryptographically-attested results (leaderboard data is currently mockup)
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* Top Models Section */}
      <section className="border-b">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-3xl font-bold mb-2">Top Models</h2>
                <p className="text-muted-foreground mb-1">
                  Current leaders on the functional track
                </p>
                <p className="text-xs font-semibold text-yellow-700 dark:text-yellow-400">
                  ⚠️ MOCKUP DATA — All models, scores, and organizations below are placeholder
                  examples ⚠️
                </p>
              </div>
              <Button variant="outline" asChild>
                <Link href="/leaderboard">
                  View All
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Rank</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Organization</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead className="text-right">Pass Rate</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topSubmissions.map(submission => (
                      <TableRow key={submission.id}>
                        <TableCell className="font-medium">#{submission.rank}</TableCell>
                        <TableCell className="font-mono text-sm">{submission.model}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {submission.organization}
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          {submission.score}%
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {submission.passRate}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={submission.status === 'verified' ? 'default' : 'secondary'}
                          >
                            {submission.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Submit Section */}
      <section className="border-b bg-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl">Submit Your Model</CardTitle>
                <CardDescription className="text-base">
                  Want to see your model on the leaderboard? Submit your Lean 4 solutions for
                  evaluation.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Quick Requirements:</h3>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-2">
                    <li>GitHub repository with Lean 4 project</li>
                    <li>Commit SHA for reproducibility</li>
                    <li>
                      Solutions must build with <code className="font-mono">lake build</code>
                    </li>
                    <li>Cryptographic attestations will be generated</li>
                  </ul>
                </div>
                <Button asChild>
                  <Link href="/submit">
                    View Detailed Instructions
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
                        fvspec: Evaluating AI Models on Formal Verification Tasks
                      </CardTitle>
                      <CardDescription className="text-base">
                        Click to read the full paper
                      </CardDescription>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                  </div>
                </CardHeader>
                <CardContent>
                  <h3 className="font-semibold mb-3">Abstract</h3>
                  <p className="text-xs text-red-700 dark:text-red-400 mb-3 font-semibold">
                    ⚠️ DRAFT STUB — This is NOT the real abstract. Placeholder text only. ⚠️
                  </p>
                  <p className="text-muted-foreground leading-relaxed text-sm">
                    We present <strong className="text-foreground">fvspec</strong>, a benchmark for
                    evaluating AI models on formal verification tasks using Lean 4. Unlike existing
                    benchmarks that rely on synthetic problems, fvspec uses real-world
                    property-based tests extracted from GitHub repositories, ensuring ecological
                    validity and avoiding potential training data contamination. The benchmark
                    extends FVAPPS (Dougherty & Mehta, 2025) by focusing on specification quality
                    rather than complete implementations, and introduces two distinct verification
                    paradigms: functional (FVAPPS-style recursion) and mvcgen (imperative with Hoare
                    logic). We evaluate specifications using structural faithfulness metrics that
                    provide objective quality assessments without requiring complete proofs. Our
                    evaluation infrastructure integrates with the Lean Language Server Protocol
                    (LSP) via Model Context Protocol (MCP) tools, enabling interactive development
                    and immediate feedback. Initial results across leading language models
                    demonstrate significant variation in specification quality, with models showing
                    different strengths across verification paradigms. The benchmark is designed to
                    track progress in AI-assisted formal verification while maintaining rigorous
                    reproducibility through cryptographic attestations.
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
            <p className="text-xs font-semibold text-yellow-700 dark:text-yellow-400">
              ⚠️ PRE-ALPHA WEBSITE — Not ready for public sharing or distribution ⚠️
            </p>
            <p>
              fvspec extends{' '}
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
