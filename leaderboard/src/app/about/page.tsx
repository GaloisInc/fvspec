import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export const metadata = {
  title: 'About — FVSpec',
  description:
    'About FVSpec and acknowledgments — the people and organizations behind the benchmark, dataset, and scraping infrastructure.',
}

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="border-b">
        <div className="container mx-auto px-4 py-8">
          <Badge className="mb-4" variant="outline">
            About
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight mb-4">About FVSpec</h1>
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span>Galois, Inc.</span>
            <span>•</span>
            <span>Funded by ARIA (Advanced Research + Invention Agency)</span>
          </div>
        </div>
      </div>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <Card className="mb-10">
          <CardContent className="pt-6">
            <p className="text-muted-foreground leading-relaxed">
              FVSpec is a benchmark for evaluating AI models and agents on real-world formal
              software verification. It extends{' '}
              <a
                href="https://arxiv.org/abs/2502.05714"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                FVAPPS
              </a>{' '}
              with real-world property-based tests scraped from open-source Python repositories and
              translated into Lean 4 specifications. The work is conducted at{' '}
              <a
                href="https://galois.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                Galois, Inc.
              </a>{' '}
              and funded by the{' '}
              <a
                href="https://aria.org.uk"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                Advanced Research + Invention Agency (ARIA)
              </a>
              .
            </p>
          </CardContent>
        </Card>

        <section className="mb-10">
          <h2 className="text-xl font-bold mb-4">Acknowledgments</h2>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Beyond the core authorship, FVSpec would not have been possible without the
            contributions of many people and teams.
          </p>
          <ul className="space-y-4 text-muted-foreground leading-relaxed">
            <li>
              <a
                href="https://boehs.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                Evan Boehs
              </a>{' '}
              and{' '}
              <a
                href="https://jakegines.in/about"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                Jake Ginesin
              </a>{' '}
              for their work on the property-based test scraper.
            </li>
            <li>
              <a
                href="https://www.linkedin.com/in/jfcastano"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                Juan Castaño
              </a>{' '}
              for setting up the database and AWS infrastructure used for scraping.
            </li>
            <li>
              <a
                href="https://benchify.com"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                Benchify
              </a>{' '}
              for their collaboration.
            </li>
            <li>
              The Galois program-management, IT, and contracting staff whose support made this work
              possible.
            </li>
          </ul>
          <p className="text-muted-foreground leading-relaxed mt-6">
            Additional acknowledgments for the broader property-based test dataset — including the{' '}
            <a
              href="https://dali.dartmouth.edu/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              Dartmouth DALI Lab
            </a>{' '}
            for extending the scraper to support TypeScript PBTs — are listed with the{' '}
            <a
              href="https://huggingface.co/datasets/GaloisInc/fvspec-pbt"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              PBT dataset
            </a>
            .
          </p>
        </section>
      </main>
    </div>
  )
}
