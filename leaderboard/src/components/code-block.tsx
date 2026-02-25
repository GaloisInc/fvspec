'use client'

import { useEffect, useState } from 'react'
import { codeToHtml } from 'shiki'

interface CodeBlockProps {
  code: string
  language: 'python' | 'lean4' | 'lean'
  className?: string
}

export function CodeBlock({ code, language, className = '' }: CodeBlockProps) {
  const [html, setHtml] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    async function highlight() {
      try {
        // Map 'lean' to 'lean4' for Shiki
        const lang = language === 'lean' ? 'lean4' : language

        const highlighted = await codeToHtml(code, {
          lang,
          themes: {
            light: 'github-light',
            dark: 'github-dark',
          },
        })

        if (mounted) {
          setHtml(highlighted)
          setLoading(false)
        }
      } catch (error) {
        console.error('Error highlighting code:', error)
        // Fallback to plain text
        if (mounted) {
          setHtml(`<pre><code>${escapeHtml(code)}</code></pre>`)
          setLoading(false)
        }
      }
    }

    highlight()

    return () => {
      mounted = false
    }
  }, [code, language])

  if (loading) {
    return (
      <div className={`rounded-lg bg-muted p-4 ${className}`}>
        <pre className="overflow-x-auto">
          <code className="text-sm">{code}</code>
        </pre>
      </div>
    )
  }

  return (
    <div
      className={`overflow-x-auto rounded-lg ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
