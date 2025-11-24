import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export function Header() {
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
          <nav className="hidden md:flex gap-6">
            <Link
              href="/leaderboard"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Leaderboard
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
          <Button variant="outline" size="sm" asChild>
            <a href="https://github.com/GaloisInc/fvspec" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
          </Button>
        </div>
      </div>
    </header>
  )
}
