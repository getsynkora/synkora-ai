import { MetadataRoute } from 'next'

const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://synkora.ai'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [
        '/dashboard/',
        '/api/',
        '/war-room/',
        '/live-lab/',
        '/signup',
        '/signin',
        '/verify-email',
        '/reset-password',
        '/forgot-password',
        '/accept-invite',
      ],
    },
    sitemap: `${BASE_URL}/sitemap.xml`,
  }
}
