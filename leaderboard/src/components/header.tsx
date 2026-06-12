'use client'

import Link from 'next/link'
import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
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
          </Link>
          {/* Desktop navigation - hidden on mobile */}
          <nav className="hidden md:flex gap-6">
            <Link href="/dataset" className={getLinkClassName('/dataset')}>
              Dataset
            </Link>
            <Link href="/paper" className={getLinkClassName('/paper')}>
              Paper
            </Link>
            <Link href="/about" className={getLinkClassName('/about')}>
              About
            </Link>
          </nav>
        </div>
        {/* External links on right - always visible on small+ screens */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex">
            <a href="https://arxiv.org/abs/2606.01008" target="_blank" rel="noopener noreferrer">
              arXiv
            </a>
          </Button>
          <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex">
            <a
              href="https://huggingface.co/datasets/GaloisInc/fvspec-pbt"
              target="_blank"
              rel="noopener noreferrer"
            >
              HF: PBT
            </a>
          </Button>
          <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex">
            <a
              href="https://huggingface.co/datasets/GaloisInc/fvspec-fv"
              target="_blank"
              rel="noopener noreferrer"
            >
              HF: FV
            </a>
          </Button>
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
              href="/about"
              className={getLinkClassName('/about')}
              onClick={() => setMobileMenuOpen(false)}
            >
              About
            </Link>
            <a
              href="https://arxiv.org/abs/2606.01008"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              arXiv →
            </a>
            <a
              href="https://huggingface.co/datasets/GaloisInc/fvspec-pbt"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              HuggingFace: PBT →
            </a>
            <a
              href="https://huggingface.co/datasets/GaloisInc/fvspec-fv"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              HuggingFace: FV →
            </a>
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
