'use client'

import { useCallback, useSyncExternalStore } from 'react'

const STORAGE_KEY = 'fvspec-bookmarks'

export interface BookmarkEntry {
  sample_id: number
  sample_name: string
  bookmarked_at: string
}

type Listener = () => void

/** Module-level store so all hook instances share the same snapshot. */
let listeners: Listener[] = []
let cachedSnapshot: Map<number, BookmarkEntry> | null = null

function emitChange() {
  cachedSnapshot = null // invalidate cache so getSnapshot re-reads
  for (const l of listeners) l()
}

function subscribe(listener: Listener): () => void {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter(l => l !== listener)
  }
}

function readFromStorage(): Map<number, BookmarkEntry> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Map()
    const entries: BookmarkEntry[] = JSON.parse(raw)
    return new Map(entries.map(e => [e.sample_id, e]))
  } catch {
    return new Map()
  }
}

function getSnapshot(): Map<number, BookmarkEntry> {
  if (cachedSnapshot === null) {
    cachedSnapshot = readFromStorage()
  }
  return cachedSnapshot
}

const emptyMap = new Map<number, BookmarkEntry>()

function getServerSnapshot(): Map<number, BookmarkEntry> {
  return emptyMap
}

function persistAndNotify(map: Map<number, BookmarkEntry>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(map.values())))
  emitChange()
}

export function useBookmarks() {
  const bookmarks = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

  const hydrated = typeof window !== 'undefined'

  const toggle = useCallback((sample_id: number, sample_name: string) => {
    const current = readFromStorage()
    if (current.has(sample_id)) {
      current.delete(sample_id)
    } else {
      current.set(sample_id, {
        sample_id,
        sample_name,
        bookmarked_at: new Date().toISOString(),
      })
    }
    persistAndNotify(current)
  }, [])

  const isBookmarked = useCallback((sample_id: number) => bookmarks.has(sample_id), [bookmarks])

  const clearAll = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    emitChange()
  }, [])

  const exportBookmarks = useCallback(() => {
    const data = Array.from(bookmarks.values())
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `fvspec-bookmarks-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [bookmarks])

  return {
    bookmarks,
    count: bookmarks.size,
    hydrated,
    toggle,
    isBookmarked,
    clearAll,
    exportBookmarks,
  }
}
