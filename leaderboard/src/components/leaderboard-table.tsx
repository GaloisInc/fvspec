'use client'

import { useState, useMemo } from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type Submission = {
  id: number
  rank: number
  model: string
  organization: string
  track: string
  score: number
  passRate: string
  avgTime: string
  status: string
  date: string
  commitSha: string
}

type SortField = 'rank' | 'score' | 'date'
type SortOrder = 'asc' | 'desc'

export function LeaderboardTable({
  submissions,
  track,
}: {
  submissions: Submission[]
  track: string
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<SortField>('rank')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')

  const filteredAndSorted = useMemo(() => {
    let filtered = submissions.filter(s => s.track === track)

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(
        s =>
          s.model.toLowerCase().includes(searchQuery.toLowerCase()) ||
          s.organization.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal: number
      let bVal: number

      if (sortField === 'date') {
        aVal = new Date(a.date).getTime()
        bVal = new Date(b.date).getTime()
      } else {
        aVal = a[sortField]
        bVal = b[sortField]
      }

      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal
    })

    return filtered
  }, [submissions, track, searchQuery, sortField, sortOrder])

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-end">
        <div className="flex-1">
          <Label htmlFor="search">Search models or organizations</Label>
          <Input
            id="search"
            placeholder="Filter by model or organization..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="mt-1"
          />
        </div>
        <div className="flex gap-2">
          <div>
            <Label htmlFor="sort-field">Sort by</Label>
            <Select value={sortField} onValueChange={v => setSortField(v as SortField)}>
              <SelectTrigger id="sort-field" className="w-32 mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rank">Rank</SelectItem>
                <SelectItem value="score">Score</SelectItem>
                <SelectItem value="date">Date</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="sort-order">Order</Label>
            <Select value={sortOrder} onValueChange={v => setSortOrder(v as SortOrder)}>
              <SelectTrigger id="sort-order" className="w-32 mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">Ascending</SelectItem>
                <SelectItem value="desc">Descending</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Rank</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Organization</TableHead>
              <TableHead className="text-right">Score</TableHead>
              <TableHead className="text-right">Pass Rate</TableHead>
              <TableHead className="text-right">Avg Time</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAndSorted.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                  No submissions found matching your filters.
                </TableCell>
              </TableRow>
            ) : (
              filteredAndSorted.map(submission => (
                <TableRow key={submission.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">#{submission.rank}</TableCell>
                  <TableCell className="font-mono text-sm">{submission.model}</TableCell>
                  <TableCell className="text-muted-foreground">{submission.organization}</TableCell>
                  <TableCell className="text-right font-semibold">{submission.score}%</TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {submission.passRate}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {submission.avgTime}
                  </TableCell>
                  <TableCell>
                    <Badge variant={submission.status === 'verified' ? 'default' : 'secondary'}>
                      {submission.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{submission.date}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredAndSorted.length} of {submissions.filter(s => s.track === track).length}{' '}
        submissions
      </div>
    </div>
  )
}
