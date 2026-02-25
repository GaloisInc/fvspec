'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { DatasetSampleListItem } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Shuffle, Star, Download, Search, ChevronDown, Loader2 } from 'lucide-react'
import { useBookmarks } from '@/hooks/useBookmarks'

const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

/** Default page size for the sample list API */
const PAGE_LIMIT = 50

/** Difficulty filter presets based on bimodal distribution of haiku scores */
type DifficultyPreset = 'easy' | 'medium' | 'hard'
const DIFFICULTY_RANGES: Record<DifficultyPreset, [number, number]> = {
  easy: [0, 3],
  medium: [4, 6],
  hard: [7, 10],
}

interface SampleSelectorProps {
  activeSampleId?: number
  activeSampleName?: string
}

const DIFFICULTY_PRESETS: DifficultyPreset[] = ['easy', 'medium', 'hard']

function parseDifficultyParam(param: string | null): Set<DifficultyPreset> {
  if (!param) return new Set()
  return new Set(
    param
      .split(',')
      .filter((v): v is DifficultyPreset => DIFFICULTY_PRESETS.includes(v as DifficultyPreset))
  )
}

export function SampleSelector({ activeSampleId, activeSampleName }: SampleSelectorProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [samples, setSamples] = useState<DatasetSampleListItem[]>([])
  const [totalSamples, setTotalSamples] = useState(0)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBookmarkedOnly, setShowBookmarkedOnly] = useState(false)
  const [difficultyFilters, setDifficultyFilters] = useState<Set<DifficultyPreset>>(() =>
    parseDifficultyParam(searchParams.get('difficulty'))
  )

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { bookmarks, count, hydrated, exportBookmarks } = useBookmarks()

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

  /** Filter samples by bookmark mode and/or difficulty preset */
  const displayedSamples = useMemo(() => {
    let result: DatasetSampleListItem[] = showBookmarkedOnly
      ? Array.from(bookmarks.values())
          .map(b => ({ sample_id: b.sample_id, sample_name: b.sample_name }))
          .sort((a, b) => a.sample_id - b.sample_id)
      : samples

    if (difficultyFilters.size > 0) {
      result = result.filter(s => {
        const d = s.difficulty_subjective_haiku
        if (d == null) return false
        return Array.from(difficultyFilters).some(preset => {
          const [min, max] = DIFFICULTY_RANGES[preset]
          return d >= min && d <= max
        })
      })
    }

    return result
  }, [samples, showBookmarkedOnly, bookmarks, difficultyFilters])

  /** Build a URL preserving the current difficulty filter params */
  const buildSampleUrl = useCallback(
    (sampleId: number) => {
      const params = new URLSearchParams()
      if (difficultyFilters.size > 0) {
        params.set('difficulty', Array.from(difficultyFilters).join(','))
      }
      const qs = params.toString()
      return `/dataset/${sampleId}${qs ? `?${qs}` : ''}`
    },
    [difficultyFilters]
  )

  const handleSampleSelect = (sampleId: number) => {
    setOpen(false)
    router.push(buildSampleUrl(sampleId))
  }

  const handleRandomSample = async () => {
    if ((showBookmarkedOnly || difficultyFilters.size > 0) && displayedSamples.length > 0) {
      const randomIndex = Math.floor(Math.random() * displayedSamples.length)
      router.push(buildSampleUrl(displayedSamples[randomIndex].sample_id))
      return
    }
    try {
      const res = await fetch(`${API_URL}/dataset/list?limit=1`)
      if (!res.ok) return
      const data: { total: number } = await res.json()
      const randomOffset = Math.floor(Math.random() * data.total) + 1
      const randomRes = await fetch(`${API_URL}/dataset/list?page=${randomOffset}&limit=1`)
      if (!randomRes.ok) return
      const randomData: { samples: DatasetSampleListItem[] } = await randomRes.json()
      if (randomData.samples.length > 0) {
        router.push(buildSampleUrl(randomData.samples[0].sample_id))
      }
    } catch {
      if (samples.length > 0) {
        const randomIndex = Math.floor(Math.random() * samples.length)
        router.push(buildSampleUrl(samples[randomIndex].sample_id))
      }
    }
  }

  const inputDisplayValue = open
    ? query
    : query || (activeSampleId != null ? `${activeSampleId} - ${activeSampleName}` : '')

  return (
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
              value={inputDisplayValue}
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
                    activeSampleId != null && sample.sample_id === activeSampleId
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
        {DIFFICULTY_PRESETS.map(preset => (
          <Button
            key={preset}
            variant={difficultyFilters.has(preset) ? 'default' : 'outline'}
            size="sm"
            onClick={() =>
              setDifficultyFilters(prev => {
                const next = new Set(prev)
                if (next.has(preset)) next.delete(preset)
                else next.add(preset)
                return next
              })
            }
            title={`Filter by ${preset} difficulty (${DIFFICULTY_RANGES[preset][0]}-${DIFFICULTY_RANGES[preset][1]})`}
          >
            {preset.charAt(0).toUpperCase() + preset.slice(1)}
          </Button>
        ))}
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
  )
}
