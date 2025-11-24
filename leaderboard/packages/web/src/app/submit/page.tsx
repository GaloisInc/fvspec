import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { InfoIcon } from 'lucide-react'

export const metadata = {
  title: 'Submit Your Model - fvspec',
  description: 'Learn how to submit your model for evaluation on the fvspec benchmark',
}

export default function SubmitPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Pre-Alpha Warning Banner */}
      <div className="border-b bg-yellow-500/10 border-yellow-500/20">
        <div className="container mx-auto px-4 py-3">
          <p className="text-center text-sm md:text-base font-semibold text-yellow-700 dark:text-yellow-400">
            ⚠️ COMING SOON — Submission system not yet operational ⚠️
          </p>
        </div>
      </div>

      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">Submit Your Model</h1>
          <p className="text-lg text-muted-foreground">
            Get your AI model evaluated on formal verification tasks
          </p>
          <p className="text-sm text-muted-foreground italic mt-1">
            (Instructions below are draft documentation — submission infrastructure in development)
          </p>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <Alert className="mb-8 border-yellow-200 dark:border-yellow-800">
          <InfoIcon className="h-4 w-4" />
          <AlertDescription>
            <strong>Note:</strong> The submission system is under development. This page shows
            planned functionality. Documentation is preliminary and subject to change.
          </AlertDescription>
        </Alert>

        <div className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle>Submission Requirements</CardTitle>
              <CardDescription>
                Your submission must meet these criteria to be evaluated
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Badge>Required</Badge>
                  GitHub Repository
                </h3>
                <p className="text-sm text-muted-foreground">
                  Your Lean 4 project must be hosted on GitHub with public access. The repository
                  should contain all necessary files to build your solutions.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Badge>Required</Badge>
                  Commit SHA
                </h3>
                <p className="text-sm text-muted-foreground">
                  Provide a specific commit SHA (at least 7 characters) for reproducibility. This
                  ensures your submission is immutable and can be verified by others.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Badge>Required</Badge>
                  Lake Build Success
                </h3>
                <p className="text-sm text-muted-foreground">
                  All solutions must successfully build with{' '}
                  <code className="font-mono bg-muted px-1 py-0.5 rounded">lake build</code>. The
                  evaluation system will clone your repository and run this command.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <Badge variant="outline">Recommended</Badge>
                  Track Selection
                </h3>
                <p className="text-sm text-muted-foreground">
                  Choose which verification track(s) your submission targets:{' '}
                  <strong>functional</strong> (FVAPPS-style recursive) or <strong>mvcgen</strong>{' '}
                  (imperative with Hoare logic). You can submit to multiple tracks.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Repository Structure</CardTitle>
              <CardDescription>
                Organize your Lean 4 project following these conventions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Expected Directory Layout</h3>
                  <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
                    {`your-repo/
├── lakefile.lean          # Lake build configuration
├── lean-toolchain         # Lean version (e.g., leanprover/lean4:v4.14.0)
├── Fvspec/
│   ├── Problem001.lean    # Solution for problem 001
│   ├── Problem002.lean    # Solution for problem 002
│   └── ...
└── lake-manifest.json     # Generated dependencies`}
                  </pre>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">Solution File Format</h3>
                  <p className="text-sm text-muted-foreground mb-3">
                    Each problem should have a corresponding Lean file with the specification and
                    implementation:
                  </p>
                  <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
                    {`-- Fvspec/Problem001.lean
def solution (input : List Nat) : List Nat :=
  sorry  -- Your implementation here

theorem solution_correct (input : List Nat) :
  -- Specification from property test
  solution input = expectedOutput input := by
  sorry  -- Your proof here`}
                  </pre>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Evaluation Process</CardTitle>
              <CardDescription>What happens when you submit your model</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="space-y-4 text-sm">
                <li className="flex gap-3">
                  <Badge className="shrink-0">1</Badge>
                  <div>
                    <strong className="block mb-1">Validation</strong>
                    <p className="text-muted-foreground">
                      We verify your GitHub repository exists and the commit SHA is valid.
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <Badge className="shrink-0">2</Badge>
                  <div>
                    <strong className="block mb-1">Sandboxed Build</strong>
                    <p className="text-muted-foreground">
                      Your code is cloned into an isolated Docker container with no network access.
                      We run <code className="font-mono">lake build</code> with resource limits (2h
                      timeout, 16GB memory).
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <Badge className="shrink-0">3</Badge>
                  <div>
                    <strong className="block mb-1">Problem Verification</strong>
                    <p className="text-muted-foreground">
                      Each problem is checked for structural faithfulness, specification
                      correctness, and proper proof construction.
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <Badge className="shrink-0">4</Badge>
                  <div>
                    <strong className="block mb-1">Attestation Generation</strong>
                    <p className="text-muted-foreground">
                      A cryptographic attestation is created including SHA-256 hashes of all
                      artifacts, toolchain information, and execution metadata.
                    </p>
                  </div>
                </li>
                <li className="flex gap-3">
                  <Badge className="shrink-0">5</Badge>
                  <div>
                    <strong className="block mb-1">Leaderboard Update</strong>
                    <p className="text-muted-foreground">
                      If verification succeeds, your score appears on the leaderboard with full
                      transparency about evaluation conditions.
                    </p>
                  </div>
                </li>
              </ol>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Submission API</CardTitle>
              <CardDescription>(Coming soon) Programmatic submission endpoint</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Once public submissions open, you&apos;ll be able to submit via HTTP POST:
              </p>
              <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
                {`POST https://api.fvspec.org/submit
Content-Type: application/json

{
  "repoUrl": "https://github.com/your-org/your-repo",
  "commitSha": "abc123def456",
  "trackId": "functional",
  "payload": {
    "modelName": "YourModel-v1.0",
    "organization": "YourOrg"
  }
}`}
              </pre>
              <p className="text-sm text-muted-foreground">
                You&apos;ll receive a submission ID to track evaluation progress. The evaluation can
                take 30 minutes to 2 hours depending on queue load.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Frequently Asked Questions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Can I use external dependencies?</h3>
                <p className="text-sm text-muted-foreground">
                  Yes, as long as they&apos;re specified in your{' '}
                  <code className="font-mono">lakefile.lean</code> and publicly available. The
                  evaluation environment has no network access during build, so dependencies must be
                  fetchable during the initial <code className="font-mono">lake update</code> phase.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2">What Lean version should I use?</h3>
                <p className="text-sm text-muted-foreground">
                  Any stable Lean 4 version is supported. Specify your version in the{' '}
                  <code className="font-mono">lean-toolchain</code> file. Most submissions use
                  v4.14.0 or newer.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2">How are ties broken on the leaderboard?</h3>
                <p className="text-sm text-muted-foreground">
                  If two submissions have the same score, we rank by: (1) submission date (earlier
                  is better), (2) average time per problem (faster is better).
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2">Can I update my submission?</h3>
                <p className="text-sm text-muted-foreground">
                  Yes! Submit a new commit SHA from the same repository. Your new submission will
                  appear as a separate entry on the leaderboard, allowing score tracking over time.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-primary">
            <CardHeader>
              <CardTitle>Ready to Submit?</CardTitle>
              <CardDescription>Public submissions opening soon</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                We&apos;re finalizing the submission infrastructure. To be notified when submissions
                open, star our GitHub repository or follow us on social media.
              </p>
              <div className="flex gap-3">
                <a
                  href="https://github.com/GaloisInc/fvspec"
                  className="text-sm font-medium text-primary hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  GitHub Repository →
                </a>
                <span className="text-muted-foreground">|</span>
                <a
                  href="mailto:fvspec@galois.com"
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Contact for Early Access →
                </a>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
