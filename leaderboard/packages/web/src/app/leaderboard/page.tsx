import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LeaderboardTable } from '@/components/leaderboard-table'

// Mock data - replace with API calls later
const mockSubmissions = [
  {
    id: 1,
    rank: 1,
    model: 'GPT-4o',
    organization: 'OpenAI',
    track: 'functional',
    score: 87.5,
    passRate: '175/200',
    avgTime: '45s',
    status: 'verified',
    date: '2025-10-25',
    commitSha: 'abc123f',
  },
  {
    id: 2,
    rank: 2,
    model: 'Claude 3.5 Sonnet',
    organization: 'Anthropic',
    track: 'functional',
    score: 84.2,
    passRate: '168/200',
    avgTime: '52s',
    status: 'verified',
    date: '2025-10-24',
    commitSha: 'def456a',
  },
  {
    id: 3,
    rank: 3,
    model: 'Gemini 2.0 Flash',
    organization: 'Google',
    track: 'functional',
    score: 79.8,
    passRate: '159/200',
    avgTime: '38s',
    status: 'verified',
    date: '2025-10-23',
    commitSha: 'ghi789b',
  },
  {
    id: 4,
    rank: 4,
    model: 'Claude 3 Opus',
    organization: 'Anthropic',
    track: 'functional',
    score: 76.3,
    passRate: '152/200',
    avgTime: '61s',
    status: 'verified',
    date: '2025-10-22',
    commitSha: 'pqr456e',
  },
  {
    id: 5,
    rank: 5,
    model: 'GPT-4 Turbo',
    organization: 'OpenAI',
    track: 'functional',
    score: 73.1,
    passRate: '146/200',
    avgTime: '48s',
    status: 'verified',
    date: '2025-10-21',
    commitSha: 'stu789f',
  },
  {
    id: 6,
    rank: 1,
    model: 'GPT-4o',
    organization: 'OpenAI',
    track: 'mvcgen',
    score: 72.3,
    passRate: '144/200',
    avgTime: '67s',
    status: 'verified',
    date: '2025-10-25',
    commitSha: 'jkl012c',
  },
  {
    id: 7,
    rank: 2,
    model: 'Claude 3.5 Sonnet',
    organization: 'Anthropic',
    track: 'mvcgen',
    score: 68.9,
    passRate: '137/200',
    avgTime: '71s',
    status: 'verified',
    date: '2025-10-24',
    commitSha: 'mno345d',
  },
  {
    id: 8,
    rank: 3,
    model: 'Gemini 2.0 Flash',
    organization: 'Google',
    track: 'mvcgen',
    score: 64.5,
    passRate: '129/200',
    avgTime: '58s',
    status: 'verified',
    date: '2025-10-23',
    commitSha: 'vwx012g',
  },
]

export const metadata = {
  title: 'Full Leaderboard - fvspec',
  description: 'Complete rankings for all models on the fvspec benchmark',
}

export default function LeaderboardPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">Full Leaderboard</h1>
          <p className="text-lg text-muted-foreground">
            Complete rankings for all models across verification tracks
          </p>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8">
        <Tabs defaultValue="functional" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-3">
            <TabsTrigger value="functional">Functional</TabsTrigger>
            <TabsTrigger value="mvcgen">MVCGen</TabsTrigger>
            <TabsTrigger value="overall">Overall</TabsTrigger>
          </TabsList>

          <TabsContent value="functional" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Functional Track</CardTitle>
                <CardDescription>
                  FVAPPS-style recursive implementations with Lean 4 specifications. Models must
                  translate Python property-based tests into functional Lean code with correctness
                  proofs.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LeaderboardTable submissions={mockSubmissions} track="functional" />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="mvcgen" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>MVCGen Track</CardTitle>
                <CardDescription>
                  Imperative implementations with Hoare logic verification. Models must provide
                  imperative code with pre/post-conditions and loop invariants verified using the
                  MVCGen framework.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LeaderboardTable submissions={mockSubmissions} track="mvcgen" />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="overall" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Overall Rankings</CardTitle>
                <CardDescription>
                  Combined performance across all tracks (coming soon)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12">
                  <p className="text-lg text-muted-foreground mb-4">
                    Overall rankings will be calculated based on weighted scores across all tracks.
                  </p>
                  <p className="text-sm text-muted-foreground">
                    We&apos;re still determining the best aggregation methodology to fairly compare
                    performance across different verification paradigms.
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>About Scoring</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                <strong className="text-foreground">Score:</strong> Percentage of benchmark problems
                successfully solved with verified specifications.
              </p>
              <p>
                <strong className="text-foreground">Pass Rate:</strong> Number of problems passed
                out of total benchmark size (200 problems).
              </p>
              <p>
                <strong className="text-foreground">Avg Time:</strong> Average time taken per
                problem, measured during evaluation.
              </p>
              <p>
                <strong className="text-foreground">Status:</strong> Verified submissions have
                cryptographic attestations proving reproducibility.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Evaluation Criteria</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>Models are evaluated on:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Structural faithfulness to original Python implementation</li>
                <li>Correctness of Lean 4 specifications</li>
                <li>Proper use of verification constructs (proofs, invariants)</li>
                <li>
                  Build success with <code className="font-mono">lake build</code>
                </li>
              </ul>
              <p className="pt-2">
                All evaluations run in sandboxed Docker containers with resource limits and network
                isolation.
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
