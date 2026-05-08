import { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

async function getCreatorData(username: string) {
  try {
    const res = await fetch(`${API_URL}/creators/${username}`, { next: { revalidate: 60 } })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function generateMetadata({ params }: { params: Promise<{ username: string }> }): Promise<Metadata> {
  const { username } = await params
  const data = await getCreatorData(username)
  if (!data) return { title: 'Creator Not Found' }
  return {
    title: `${data.display_name || data.username} — Creator`,
    description: data.bio || `AI agent creator @${data.username}`,
    openGraph: {
      images: data.avatar_url ? [data.avatar_url] : [],
    },
  }
}

export default async function CreatorProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params
  const data = await getCreatorData(username)
  if (!data) notFound()

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <Link href="/" className="text-white/40 text-sm hover:text-white transition-colors">← Home</Link>
        <Link href="/signin" className="px-4 py-2 text-sm border border-white/20 rounded-lg text-white/80 hover:border-white/40 transition-all">
          Sign up free
        </Link>
      </nav>

      {/* Banner */}
      <div
        className="h-48 w-full relative"
        style={{
          background: data.banner_image_url
            ? `url(${data.banner_image_url}) center/cover`
            : 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        }}
      >
        <div className="absolute inset-0 bg-[#0a0a0a]/40" />
      </div>

      {/* Creator hero */}
      <div className="px-6 max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row items-start md:items-end gap-6 -mt-12 mb-10">
          <div className="relative">
            {data.avatar_url ? (
              <img
                src={data.avatar_url}
                alt={data.display_name || data.username}
                className="w-24 h-24 rounded-full border-4 border-[#0a0a0a] object-cover"
              />
            ) : (
              <div className="w-24 h-24 rounded-full border-4 border-[#0a0a0a] bg-white/10 flex items-center justify-center text-3xl font-black">
                {(data.display_name || data.username || '?')[0].toUpperCase()}
              </div>
            )}
          </div>
          <div className="flex-1">
            <h1 className="text-4xl font-black tracking-tighter">
              {data.display_name || data.username}
            </h1>
            <div className="text-white/40 text-sm font-mono">@{data.username}</div>
          </div>
        </div>

        {data.bio && (
          <p className="text-white/60 text-lg max-w-2xl leading-relaxed mb-8">{data.bio}</p>
        )}

        {/* Stats bar */}
        <div className="flex items-center gap-6 mb-12 text-sm text-white/40 font-mono">
          <span>{data.agents?.length || 0} agents</span>
          <span className="text-white/20">/</span>
          <span>{data.total_earnings_credits?.toLocaleString() || 0} credits earned</span>
        </div>

        {/* Social links */}
        <div className="flex gap-4 mb-12 flex-wrap">
          {data.website_url && (
            <a href={data.website_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-white/10 rounded-lg text-sm text-white/60 hover:text-white hover:border-white/30 transition-all">
              Website
            </a>
          )}
          {data.twitter_url && (
            <a href={data.twitter_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-white/10 rounded-lg text-sm text-white/60 hover:text-white hover:border-white/30 transition-all">
              Twitter
            </a>
          )}
          {data.github_url && (
            <a href={data.github_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-white/10 rounded-lg text-sm text-white/60 hover:text-white hover:border-white/30 transition-all">
              GitHub
            </a>
          )}
          {data.linkedin_url && (
            <a href={data.linkedin_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-white/10 rounded-lg text-sm text-white/60 hover:text-white hover:border-white/30 transition-all">
              LinkedIn
            </a>
          )}
        </div>

        {/* Published agents grid */}
        <div className="mb-16">
          <h2 className="text-2xl font-black tracking-tighter mb-6">Published Agents</h2>
          {data.agents && data.agents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.agents.map((agent: any) => (
                <Link
                  key={agent.slug}
                  href={`/a/${agent.slug}`}
                  className="group block rounded-2xl border border-white/10 bg-white/[0.02] p-6 hover:border-white/20 hover:bg-white/5 transition-all"
                >
                  {agent.hero_image_url && (
                    <div className="aspect-video rounded-xl overflow-hidden mb-4 bg-white/5">
                      <img src={agent.hero_image_url} alt={agent.agent_name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                    </div>
                  )}
                  <div className="text-lg font-bold mb-1 group-hover:text-white/90">
                    {agent.agent_name}
                  </div>
                  {agent.tagline && (
                    <p className="text-white/40 text-sm line-clamp-2 mb-3">{agent.tagline}</p>
                  )}
                  <div className="text-xs font-mono text-[#ff444f]">
                    {agent.cta_label || 'Try it free'} →
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-16 text-white/20">No published agents yet</div>
          )}
        </div>
      </div>

      <footer className="border-t border-white/5 py-8 px-6 text-center text-white/20 text-sm">
        Powered by AI
      </footer>
    </div>
  )
}
