import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { AnimatedLanding } from './AnimatedLanding'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

async function getAgentLanding(slug: string) {
  try {
    const res = await fetch(`${API_URL}/api/public/agents/${slug}`, {
      cache: 'no-store',
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const data = await getAgentLanding(slug)
  if (!data) return { title: 'Agent Not Found' }
  return {
    title: data.seo_title || data.agent_name || slug,
    description: data.seo_description || data.tagline,
    openGraph: {
      title: data.seo_title || data.agent_name,
      description: data.seo_description || data.tagline,
      images: data.og_image_url ? [data.og_image_url] : data.hero_image_url ? [data.hero_image_url] : [],
    },
  }
}

export default async function AgentLandingPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const data = await getAgentLanding(slug)
  if (!data) notFound()

  return <AnimatedLanding data={data} slug={slug} />
}
