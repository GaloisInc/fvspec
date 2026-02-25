'use client'

import { useMemo } from 'react'
import type { DatasetSampleDetail } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Star, ExternalLink } from 'lucide-react'
import LZString from 'lz-string'
import { CodeBlock } from './code-block'
import { useBookmarks } from '@/hooks/useBookmarks'
import { SampleSelector } from './sample-selector'

interface DatasetExplorerProps {
  initialSample: DatasetSampleDetail
}

export function DatasetExplorer({ initialSample }: DatasetExplorerProps) {
  const { toggle, isBookmarked, hydrated } = useBookmarks()

  const currentBookmarked = hydrated && isBookmarked(initialSample.sample_id)

  /** Build a live.lean-lang.org URL with impl + spec merged into a single file */
  const playgroundUrl = useMemo(() => {
    const isImport = (line: string) => /^\s*import\s/.test(line)
    const splitImports = (src: string) => {
      const lines = src.split('\n')
      const imports: string[] = []
      const body: string[] = []
      for (const line of lines) {
        if (isImport(line)) imports.push(line.trim())
        else body.push(line)
      }
      return { imports, body: body.join('\n').replace(/^\n+/, '') }
    }

    const impl = splitImports(initialSample.impl)
    const spec = splitImports(initialSample.spec)

    // Deduplicate imports, drop "import Fvspec.Impl" (meaningless outside project)
    const allImports = [...new Set([...impl.imports, ...spec.imports])].filter(
      i => i !== 'import Fvspec.Impl'
    )

    const code = [allImports.join('\n'), '', impl.body, '', spec.body].join('\n')
    const compressed = LZString.compressToBase64(code).replace(/=*$/, '')
    return `https://live.lean-lang.org/#codez=${compressed}`
  }, [initialSample.impl, initialSample.spec])

  return (
    <div className="space-y-6">
      {/* Sample selector */}
      <SampleSelector
        activeSampleId={initialSample.sample_id}
        activeSampleName={initialSample.sample_name}
      />

      {/* Metadata display */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {initialSample.sample_name}
            <Badge variant="outline">ID: {initialSample.sample_id}</Badge>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => toggle(initialSample.sample_id, initialSample.sample_name)}
              title={currentBookmarked ? 'Remove bookmark' : 'Bookmark this sample'}
              className="ml-auto h-8 w-8"
            >
              <Star
                className={`h-4 w-4 ${currentBookmarked ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground'}`}
              />
            </Button>
          </CardTitle>
          {initialSample.realpbt_summary && (
            <CardDescription>{initialSample.realpbt_summary}</CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {initialSample.realpbt_repo_id !== undefined && (
              <Badge variant="outline" className="font-mono text-xs">
                Repo: {initialSample.realpbt_repo_id}
              </Badge>
            )}
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            {initialSample.difficulty_subjective_haiku != null && (
              <div>
                <div className="text-muted-foreground text-sm">Difficulty</div>
                <div className="text-2xl font-bold">
                  {initialSample.difficulty_subjective_haiku.toFixed(1)}
                </div>
              </div>
            )}
            {initialSample.realpbt_lines_pbt != null && (
              <div>
                <div className="text-muted-foreground text-sm">PBT Lines</div>
                <div className="text-2xl font-bold">{initialSample.realpbt_lines_pbt}</div>
              </div>
            )}
            {initialSample.lean_metrics?.total_lean_lines != null && (
              <div>
                <div className="text-muted-foreground text-sm">Lean Lines</div>
                <div className="text-2xl font-bold">
                  {initialSample.lean_metrics.total_lean_lines}
                </div>
              </div>
            )}
            {initialSample.num_theorems !== undefined && (
              <div>
                <div className="text-muted-foreground text-sm">Theorems</div>
                <div className="text-2xl font-bold">{initialSample.num_theorems}</div>
              </div>
            )}
            {initialSample.structural_faithfulness?.overall !== undefined && (
              <div>
                <div className="text-muted-foreground text-sm">Faithfulness</div>
                <div className="text-2xl font-bold">
                  {(Number(initialSample.structural_faithfulness.overall) * 100).toFixed(1)}%
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Code viewer with tabs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Code</CardTitle>
              <CardDescription>View Python source and generated Lean files</CardDescription>
            </div>
            <Button variant="outline" size="sm" className="gap-2" asChild>
              <a href={playgroundUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
                Open in Lean Playground
              </a>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="spec" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="python">Python</TabsTrigger>
              <TabsTrigger value="spec">Spec</TabsTrigger>
              <TabsTrigger value="impl">Impl</TabsTrigger>
            </TabsList>
            <TabsContent value="python" className="mt-4">
              <CodeBlock code={initialSample.realpbt_code ?? ''} language="python" />
            </TabsContent>
            <TabsContent value="spec" className="mt-4">
              <CodeBlock code={initialSample.spec} language="lean4" />
            </TabsContent>
            <TabsContent value="impl" className="mt-4">
              <CodeBlock code={initialSample.impl} language="lean4" />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
