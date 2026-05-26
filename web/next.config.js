const { withSentryConfig } = require('@sentry/nextjs')
const path = require('path')
const withBundleAnalyzer =
  process.env.ANALYZE === 'true'
    ? require('@next/bundle-analyzer')({ enabled: true })
    : (config) => config

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '..'),
  // Never expose source maps to the browser in production (regardless of Sentry config)
  productionBrowserSourceMaps: false,

  // Transpile ESM-only packages
  transpilePackages: ['remark-gfm', 'chart.js', 'react-chartjs-2', 'mermaid'],
  
  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '9000',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'localhost',
        port: '9000',
        pathname: '/**',
      },
    ],
    unoptimized: process.env.NODE_ENV === 'development',
  },

  // Explicitly scope Turbopack to the web app root so it doesn't infer the
  // monorepo root from sibling lockfiles and watch more files than necessary.
  turbopack: {
    root: path.join(__dirname),
  },

  // Headers for security
  async headers() {
    const isDev = process.env.NODE_ENV === 'development'
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

    // Build CSP — restrict where scripts can connect to prevent XSS token exfiltration
    const cspDirectives = [
      "default-src 'self'",
      // Next.js requires unsafe-inline for hydration scripts; unsafe-eval for some libs
      // Cloudflare injects beacon.min.js at the edge — must be explicitly allowed
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://static.cloudflareinsights.com https://synkora.ai",
      // Tailwind and styled components require unsafe-inline for styles
      "style-src 'self' 'unsafe-inline'",
      // Images from self, data URIs, blobs, and any HTTPS source (for user avatars etc.)
      // In development, also allow HTTP for local MinIO presigned URLs
      isDev ? "img-src 'self' data: blob: https: http:" : "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      // Critical: restrict where JS can make network requests — blocks token exfiltration
      [
        "connect-src 'self'",
        apiUrl,
        // WebSocket for real-time features
        apiUrl.replace('http', 'ws'),
        // Widget API access — always allowed so embedded widget.js works in any environment
        'https://api.synkora.ai',
        'wss://api.synkora.ai',
        // Sentry error reporting (self-hosted + cloud)
        'https://*.sentry.io',
        'https://ingest.sentry.io',
        'https://logs.synkora.ai',
        // Cloudflare Analytics beacon
        'https://cloudflareinsights.com',
        process.env.NEXT_PUBLIC_LOGS_URL || '',
        process.env.NEXT_PUBLIC_SENTRY_HOST || '',
        // S3/MinIO presigned URL uploads go directly from the browser
        isDev ? 'http://localhost:9000' : '',
        process.env.NEXT_PUBLIC_MINIO_PUBLIC_URL || '',
      ].filter(Boolean).join(' '),
      "worker-src 'self' blob:",
      // Allow iframes for document embedding, Office Online, and video providers
      [
        "frame-src 'self'",
        apiUrl,
        'https://view.officeapps.live.com',
        'https://www.youtube.com',
        'https://www.youtube-nocookie.com',
        'https://player.vimeo.com',
        isDev ? 'http://localhost:9000' : '',
        process.env.NEXT_PUBLIC_MINIO_PUBLIC_URL || '',
      ].filter(Boolean).join(' '),
      // Prevent clickjacking (replaces X-Frame-Options)
      "frame-ancestors 'none'",
      // Prevent base tag injection
      "base-uri 'self'",
      // Prevent form hijacking
      "form-action 'self'",
      // Upgrade HTTP requests to HTTPS in production
      isDev ? '' : 'upgrade-insecure-requests',
    ].filter(Boolean)

    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: cspDirectives.join('; '),
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          // X-XSS-Protection intentionally omitted — deprecated and can introduce
          // reflected XSS in some browsers. CSP provides XSS protection instead.
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            // microphone=(self) allows the page itself to request mic access
            // (needed for the widget's voice input). cross-origin iframes remain blocked.
            value: 'camera=(), microphone=(self), geolocation=()',
          },
          // Cross-Origin isolation — prevent Spectre/Meltdown side-channel leaks.
          // Using 'credentialless' instead of 'require-corp': still provides isolation
          // but allows cross-origin resources (MinIO images, CDN assets) without requiring
          // them to send Cross-Origin-Resource-Policy headers.
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'credentialless',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-site',
          },
          // HSTS belongs on the frontend (HTML) server, not the API backend.
          // Only set in production to avoid locking development browsers into HTTPS.
          ...(!isDev ? [{
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains; preload',
          }] : []),
        ],
      },
      // Extension auth page — Chrome's launchWebAuthFlow loads this in an internal
      // HTTPS window that enforces X-Frame-Options. Remove the framing restriction
      // only for this route; all other pages remain protected.
      {
        source: '/extension-auth',
        headers: [
          { key: 'X-Frame-Options', value: '' },
          {
            key: 'Content-Security-Policy',
            value: cspDirectives.filter(d => !d.startsWith('frame-ancestors')).join('; '),
          },
        ],
      },
      // Public agent landing pages — relax COEP so YouTube/Vimeo iframes work
      {
        source: '/a/:path*',
        headers: [
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'unsafe-none',
          },
        ],
      },
      // CORS headers for widget.js to allow embedding on external sites
      {
        source: '/widget.js',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value: '*',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin',
          },
          {
            key: 'Cache-Control',
            // No caching in development so changes are instant.
            // In production, bump the ?v= query param on deploy to bust CDN cache.
            value: isDev ? 'no-store' : 'public, max-age=3600, s-maxage=3600',
          },
        ],
      },
    ]
  },

  // Rewrites for API proxy in development
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL
    if (!apiUrl) return []
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ]
  },
}

const analyzedConfig = withBundleAnalyzer(nextConfig)

module.exports = process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(analyzedConfig, {
      org: process.env.SENTRY_ORG || '',
      project: process.env.SENTRY_PROJECT || '',
      silent: true,
      widenClientFileUpload: true,
      hideSourceMaps: true,
      disableLogger: true,
    })
  : analyzedConfig
