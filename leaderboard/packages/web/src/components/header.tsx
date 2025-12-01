'use client'

import Link from 'next/link'
import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Menu, X } from 'lucide-react'

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const pathname = usePathname()

  const isActive = (path: string) => {
    if (path === '/') return pathname === '/'
    return pathname?.startsWith(path)
  }

  const getLinkClassName = (path: string) => {
    const baseClasses = 'text-sm font-medium transition-colors'
    const isLinkActive = isActive(path)

    return `${baseClasses} ${
      isLinkActive
        ? 'text-foreground border-b-2 border-primary'
        : 'text-muted-foreground hover:text-foreground'
    }`
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 flex h-16 items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Mobile menu button - on left side */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          <Link href="/" className="flex items-center space-x-2">
            <span className="font-bold text-xl">fvspec</span>
            <Badge variant="outline" className="text-xs">
              PRE-ALPHA
            </Badge>
          </Link>
          {/* Desktop navigation - hidden on mobile */}
          <nav className="hidden md:flex gap-6">
            <Link
              href="/dataset"
              className={getLinkClassName('/dataset')}
            >
              Dataset
            </Link>
            <Link
              href="/paper"
              className={getLinkClassName('/paper')}
            >
              Paper
            </Link>
            <Link
              href="/leaderboard"
              className={getLinkClassName('/leaderboard')}
            >
              Leaderboard
            </Link>
            <Link
              href="/submit"
              className={getLinkClassName('/submit')}
            >
              Submit
            </Link>
          </nav>
        </div>
        {/* GitHub button on right - always visible on small+ screens */}
        <div className="flex items-center">
          <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex">
            <a href="https://github.com/GaloisInc/fvspec" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
          </Button>
        </div>
      </div>
      {/* Mobile navigation */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-4">
            <Link
              href="/dataset"
              className={getLinkClassName('/dataset')}
              onClick={() => setMobileMenuOpen(false)}
            >
              Dataset
            </Link>
            <Link
              href="/paper"
              className={getLinkClassName('/paper')}
              onClick={() => setMobileMenuOpen(false)}
            >
              Paper
            </Link>
            <Link
              href="/leaderboard"
              className={getLinkClassName('/leaderboard')}
              onClick={() => setMobileMenuOpen(false)}
            >
              Leaderboard
            </Link>
            <Link
              href="/submit"
              className={getLinkClassName('/submit')}
              onClick={() => setMobileMenuOpen(false)}
            >
              Submit
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
