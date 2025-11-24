import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Empty turbopack config to silence webpack warning
  turbopack: {},
  // Disable development features in production
  devIndicators: {
    appIsrStatus: false,
  },
  // Explicitly disable experimental features that scan local network
  experimental: {
    // Disable any local network discovery
  },
}

export default nextConfig
