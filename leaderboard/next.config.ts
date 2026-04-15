import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Empty turbopack config to silence webpack warning
  turbopack: {},
  // Include pre-computed dataset files in serverless function bundles
  outputFileTracingIncludes: {
    '/api/**': ['./data/**'],
  },
}

export default nextConfig
