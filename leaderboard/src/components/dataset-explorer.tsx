'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import type { DatasetSampleDetail, DatasetSampleListItem } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Shuffle, Star, Download, Search, ChevronDown, Loader2, ExternalLink } from 'lucide-react'
import LZString from 'lz-string'
import { CodeBlock } from './code-block'
import { useBookmarks } from '@/hooks/useBookmarks'

// Client component - use relative URL that goes through Next.js route handler
const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

/** Default page size for the sample list API */
const PAGE_LIMIT = 50

interface DatasetExplorerProps {
  initialSample: DatasetSampleDetail
}

export function DatasetExplorer({ initialSample }: DatasetExplorerProps) {
  const router = useRouter()
  const [samples, setSamples] = useState<DatasetSampleListItem[]>([])
  const [totalSamples, setTotalSamples] = useState(0)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBookmarkedOnly, setShowBookmarkedOnly] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { bookmarks, toggle, isBookmarked, count, hydrated, exportBookmarks } = useBookmarks()

  /** Fetch samples from the paginated API */
  const fetchSamples = useCallback(
    async (searchQuery: string, pageNum: number, append: boolean) => {
      setLoading(true)
      try {
        const params = new URLSearchParams({
          page: String(pageNum),
          limit: String(PAGE_LIMIT),
        })
        if (searchQuery) params.set('q', searchQuery)

        const res = await fetch(`${API_URL}/dataset/list?${params}`)
        if (!res.ok) throw new Error('Failed to load sample list')

        const data: {
          samples: DatasetSampleListItem[]
          total: number
          page: number
          limit: number
        } = await res.json()

        setSamples(prev => (append ? [...prev, ...data.samples] : data.samples))
        setTotalSamples(data.total)
        setPage(data.page)
        setHasMore(data.page * data.limit < data.total)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load samples')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  /** Initial load */
  useEffect(() => {
    fetchSamples('', 1, false)
  }, [fetchSamples])

  /** Debounced search on query change */
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchSamples(query, 1, false)
    }, 250)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, fetchSamples])

  /** Load more when scrolling near bottom of the dropdown list */
  const handleScroll = useCallback(() => {
    const el = listRef.current
    if (!el || loading || !hasMore) return

    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (nearBottom) {
      fetchSamples(query, page + 1, true)
    }
  }, [loading, hasMore, query, page, fetchSamples])

  /** Close dropdown when clicking outside */
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  /** When showing bookmarks, use the full bookmarks store (not the paginated API results) */
  const displayedSamples = useMemo(() => {
    if (!showBookmarkedOnly) return samples
    return Array.from(bookmarks.values())
      .map(b => ({ sample_id: b.sample_id, sample_name: b.sample_name }))
      .sort((a, b) => a.sample_id - b.sample_id)
  }, [samples, showBookmarkedOnly, bookmarks])

  const handleSampleSelect = (sampleId: number) => {
    setOpen(false)
    router.push(`/dataset/${sampleId}`)
  }

  const handleRandomSample = async () => {
    if (showBookmarkedOnly && displayedSamples.length > 0) {
      const randomIndex = Math.floor(Math.random() * displayedSamples.length)
      router.push(`/dataset/${displayedSamples[randomIndex].sample_id}`)
      return
    }
    try {
      // Fetch total count to pick a random page/offset
      const res = await fetch(`${API_URL}/dataset/list?limit=1`)
      if (!res.ok) return
      const data: { total: number } = await res.json()
      const randomOffset = Math.floor(Math.random() * data.total) + 1
      const randomRes = await fetch(`${API_URL}/dataset/list?page=${randomOffset}&limit=1`)
      if (!randomRes.ok) return
      const randomData: { samples: DatasetSampleListItem[] } = await randomRes.json()
      if (randomData.samples.length > 0) {
        router.push(`/dataset/${randomData.samples[0].sample_id}`)
      }
    } catch {
      // Fallback: use currently loaded samples
      if (samples.length > 0) {
        const randomIndex = Math.floor(Math.random() * samples.length)
        router.push(`/dataset/${samples[randomIndex].sample_id}`)
      }
    }
  }

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
      {/* Pre-alpha warning banner */}
      <Alert>
        <AlertDescription>
          <strong>Early Development Dataset:</strong> This preview contains {totalSamples} samples
          while we work out generation pipeline kinks.
        </AlertDescription>
      </Alert>

      {/* Sample selector */}
      <Card>
        <CardHeader>
          <CardTitle>Sample Selection</CardTitle>
          <CardDescription>Search and choose a benchmark sample to explore</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          {/* Searchable combobox */}
          <div ref={containerRef} className="relative min-w-0 flex-1">
            <div className="relative">
              <Search className="text-muted-foreground pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" />
              <Input
                ref={inputRef}
                placeholder={`Search ${totalSamples} samples...`}
                value={
                  open
                    ? query
                    : query || `${initialSample.sample_id} - ${initialSample.sample_name}`
                }
                onChange={e => {
                  setQuery(e.target.value)
                  if (!open) setOpen(true)
                }}
                onFocus={() => setOpen(true)}
                className="pl-9 pr-9"
              />
              <button
                type="button"
                className="text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2"
                onClick={() => {
                  setOpen(prev => !prev)
                  if (!open) inputRef.current?.focus()
                }}
                aria-label="Toggle sample list"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>

            {open && (
              <div
                ref={listRef}
                onScroll={handleScroll}
                className="border-input bg-popover text-popover-foreground absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border shadow-md"
              >
                {error && <div className="text-destructive px-3 py-2 text-sm">{error}</div>}
                {displayedSamples.length === 0 && !loading && (
                  <div className="text-muted-foreground px-3 py-6 text-center text-sm">
                    No samples found.
                  </div>
                )}
                {displayedSamples.map(sample => (
                  <button
                    key={sample.sample_id}
                    type="button"
                    className={`hover:bg-accent hover:text-accent-foreground w-full cursor-pointer px-3 py-2 text-left text-sm ${
                      sample.sample_id === initialSample.sample_id
                        ? 'bg-accent text-accent-foreground'
                        : ''
                    }`}
                    onClick={() => handleSampleSelect(sample.sample_id)}
                  >
                    <span className="text-muted-foreground mr-2 font-mono text-xs">
                      {sample.sample_id}
                    </span>
                    {sample.sample_name}
                  </button>
                ))}
                {loading && (
                  <div className="flex items-center justify-center py-3">
                    <Loader2 className="text-muted-foreground h-4 w-4 animate-spin" />
                  </div>
                )}
                {hasMore && !loading && (
                  <div className="text-muted-foreground px-3 py-2 text-center text-xs">
                    Scroll for more results
                  </div>
                )}
              </div>
            )}
          </div>

          <Button
            variant="outline"
            onClick={handleRandomSample}
            disabled={totalSamples === 0}
            title="Random sample"
            className="gap-2"
          >
            <Shuffle className="h-4 w-4" />
            <span className="hidden sm:inline">Random</span>
          </Button>
          <Button
            variant={showBookmarkedOnly ? 'default' : 'outline'}
            onClick={() => setShowBookmarkedOnly(prev => !prev)}
            title="Show bookmarked only"
            className="gap-2"
          >
            <Star className={`h-4 w-4 ${showBookmarkedOnly ? 'fill-current' : ''}`} />
            <span className="hidden sm:inline">Bookmarked</span>
            {hydrated && count > 0 && (
              <Badge variant="secondary" className="ml-1 text-xs">
                {count}
              </Badge>
            )}
          </Button>
          {hydrated && count > 0 && (
            <Button
              variant="outline"
              onClick={exportBookmarks}
              title="Export bookmarks as JSON"
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline">Export</span>
            </Button>
          )}
        </CardContent>
      </Card>

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
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
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
