import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Empty turbopack config to silence webpack warning
  turbopack: {},
}

export default nextConfig
