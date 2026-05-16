import '../styles/globals.css'
import localFont from 'next/font/local'
import { Toaster } from 'react-hot-toast'
import { SecurityInit } from '../components/common/SecurityInit'

const inter = localFont({
  src: [
    { path: '../public/fonts/inter-400.woff2', weight: '400', style: 'normal' },
    { path: '../public/fonts/inter-500.woff2', weight: '500', style: 'normal' },
    { path: '../public/fonts/inter-600.woff2', weight: '600', style: 'normal' },
    { path: '../public/fonts/inter-700.woff2', weight: '700', style: 'normal' },
  ],
  display: 'swap',
  fallback: ['system-ui', 'sans-serif'],
})

export const metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'https://synkora.ai'),
  title: 'Synkora – Open-Source LLM Application Platform',
  description: 'Multitenant, API-first platform for building, deploying, and managing AI agents. Multi-provider LLM support, RAG, tool registry, and full observability. Self-host or cloud.',
  openGraph: {
    title: 'Synkora – Open-Source LLM Application Platform',
    description: 'Multitenant, API-first platform for building, deploying, and managing AI agents. Multi-provider LLM support, RAG, tool registry, and full observability. Self-host or cloud.',
    type: 'website',
    siteName: 'Synkora',
    images: [{ url: '/hero-image.jpg', width: 1200, height: 630, alt: 'Synkora – Open-Source LLM Platform' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Synkora – Open-Source LLM Application Platform',
    description: 'Multitenant, API-first platform for building, deploying, and managing AI agents. Multi-provider LLM support, RAG, tool registry, and full observability. Self-host or cloud.',
    images: ['/hero-image.jpg'],
  },
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Synkora',
  applicationCategory: 'DeveloperApplication',
  operatingSystem: 'Web',
  description: 'Multitenant, API-first open-source LLM application platform for building, deploying, and managing AI agents.',
  url: 'https://synkora.ai',
  softwareVersion: 'latest',
  license: 'https://opensource.org/licenses/MIT',
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'USD',
    description: 'Free tier available. Self-hostable.',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className} suppressHydrationWarning>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: 'Synkora',
            url: 'https://synkora.ai',
            potentialAction: {
              '@type': 'SearchAction',
              target: { '@type': 'EntryPoint', urlTemplate: 'https://synkora.ai/alternatives?q={search_term_string}' },
              'query-input': 'required name=search_term_string',
            },
          }) }}
        />
        <SecurityInit />
        {children}
        <Toaster 
          position="top-right"
          toastOptions={{
            // Success toasts - green
            success: {
              duration: 4000,
              style: {
                background: '#f0fdf4', // green-50
                color: '#14532d', // green-900
                border: '2px solid #22c55e', // green-500
                padding: '16px',
                borderRadius: '12px',
                fontWeight: '500',
                boxShadow: '0 10px 15px -3px rgba(34, 197, 94, 0.2), 0 4px 6px -2px rgba(34, 197, 94, 0.1)',
              },
              iconTheme: {
                primary: '#22c55e', // green-500
                secondary: '#f0fdf4', // green-50
              },
            },
            // Error toasts
            error: {
              duration: 5000,
              style: {
                background: '#fee2e2', // red-100
                color: '#7f1d1d', // red-900
                border: '2px solid #ef4444', // red-500
                padding: '16px',
                borderRadius: '12px',
                fontWeight: '500',
                boxShadow: '0 10px 15px -3px rgba(239, 68, 68, 0.2), 0 4px 6px -2px rgba(239, 68, 68, 0.1)',
              },
              iconTheme: {
                primary: '#ef4444', // red-500
                secondary: '#fef2f2', // red-50
              },
            },
            // Loading toasts - new brand color
            loading: {
              style: {
                background: '#ffffff',
                color: '#1f2937', // gray-800
                border: '2px solid #ff444f',
                padding: '16px',
                borderRadius: '12px',
                fontWeight: '500',
                boxShadow: '0 10px 15px -3px rgba(255, 68, 79, 0.2), 0 4px 6px -2px rgba(255, 68, 79, 0.1)',
              },
              iconTheme: {
                primary: '#ff444f',
                secondary: '#ffffff',
              },
            },
            // Default/custom toasts
            style: {
              background: '#ffffff',
              color: '#1f2937', // gray-800
              border: '2px solid #ff444f',
              padding: '16px',
              borderRadius: '12px',
              fontWeight: '500',
              boxShadow: '0 10px 15px -3px rgba(255, 68, 79, 0.2), 0 4px 6px -2px rgba(255, 68, 79, 0.1)',
            },
          }}
        />
      </body>
    </html>
  )
}
