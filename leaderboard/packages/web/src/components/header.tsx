'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Menu, X } from 'lucide-react'

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 flex h-16 items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center space-x-2">
            <span className="font-bold text-xl">fvspec</span>
            <Badge variant="outline" className="text-xs">
              PRE-ALPHA
            </Badge>
          </Link>
          {/* Desktop navigation */}
          <nav className="hidden md:flex gap-6">
            <Link
              href="/leaderboard"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Leaderboard
            </Link>
            <Link
              href="/dataset/341"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Dataset
            </Link>
            <Link
              href="/submit"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Submit
            </Link>
            <Link
              href="/paper"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Paper
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-2">
          {/* Desktop GitHub button */}
          <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex">
            <a href="https://github.com/GaloisInc/fvspec" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
          </Button>
          {/* Mobile menu button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>
      {/* Mobile navigation */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-4">
            <Link
              href="/leaderboard"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              Leaderboard
            </Link>
            <Link
              href="/dataset/341"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              Dataset
            </Link>
            <Link
              href="/submit"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              Submit
            </Link>
            <Link
              href="/paper"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              Paper
            </Link>
            <a
              href="https://github.com/GaloisInc/fvspec"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              GitHub →
            </a>
          </nav>
        </div>
      )}
    </header>
  )
}
