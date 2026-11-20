import { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getTranslations } from 'next-intl/server'

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
    title: `${data.display_name || data.username}, Creator`,
    description: data.bio || `AI agent creator @${data.username}`,
    openGraph: {
      images: data.avatar_url ? [data.avatar_url] : [],
    },
  }
}

export default async function CreatorProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const t = await getTranslations('publicCreator')
  const { username } = await params
  const data = await getCreatorData(username)
  if (!data) notFound()

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-ink/10">
        <Link href="/" className="text-ink-mute text-sm hover:text-ink transition-colors">{t('home')}</Link>
        <Link href="/signin" className="px-4 py-2 text-sm border border-ink/10 rounded-lg text-ink-soft hover:border-ink/10 transition-[color,background-color,border-color,box-shadow,opacity,transform]">
          {t('signUpFree')}
        </Link>
      </nav>

      {/* Banner */}
      <div
        className="h-48 w-full relative"
        style={{
          background: data.banner_image_url
            ? `url(${data.banner_image_url}) center/cover`
            : 'rgb(var(--sand-deep))',
        }}
      >
        <div className="absolute inset-0 bg-ink/10" />
      </div>

      {/* Creator hero */}
      <div className="px-6 max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row items-start md:items-end gap-6 -mt-12 mb-10">
          <div className="relative">
            {data.avatar_url ? (
              <img
                src={data.avatar_url}
                alt={data.display_name || data.username}
                className="w-24 h-24 rounded-full border-4 border-ink object-cover"
              />
            ) : (
              <div className="w-24 h-24 rounded-full border-4 border-ink bg-white flex items-center justify-center text-3xl font-black">
                {(data.display_name || data.username || '?')[0].toUpperCase()}
              </div>
            )}
          </div>
          <div className="flex-1">
            <h1 className="text-4xl font-black tracking-tighter">
              {data.display_name || data.username}
            </h1>
            <div className="text-ink-mute text-sm font-mono">@{data.username}</div>
          </div>
        </div>

        {data.bio && (
          <p className="text-ink-soft text-lg max-w-2xl leading-relaxed mb-8">{data.bio}</p>
        )}

        {/* Stats bar */}
        <div className="flex items-center gap-6 mb-12 text-sm text-ink-mute font-mono">
          <span>{data.agents?.length || 0} agents</span>
          <span className="text-ink-mute">/</span>
          <span>{data.total_earnings_credits?.toLocaleString() || 0} credits earned</span>
        </div>

        {/* Social links */}
        <div className="flex gap-4 mb-12 flex-wrap">
          {data.website_url && (
            <a href={data.website_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-ink/10 rounded-lg text-sm text-ink-soft hover:text-ink hover:border-ink/10 transition-[color,background-color,border-color,box-shadow,opacity,transform]">
              {t('website')}
            </a>
          )}
          {data.twitter_url && (
            <a href={data.twitter_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-ink/10 rounded-lg text-sm text-ink-soft hover:text-ink hover:border-ink/10 transition-[color,background-color,border-color,box-shadow,opacity,transform]">
              {t('twitter')}
            </a>
          )}
          {data.github_url && (
            <a href={data.github_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-ink/10 rounded-lg text-sm text-ink-soft hover:text-ink hover:border-ink/10 transition-[color,background-color,border-color,box-shadow,opacity,transform]">
              {t('github')}
            </a>
          )}
          {data.linkedin_url && (
            <a href={data.linkedin_url} target="_blank" rel="noopener noreferrer"
              className="px-4 py-2 border border-ink/10 rounded-lg text-sm text-ink-soft hover:text-ink hover:border-ink/10 transition-[color,background-color,border-color,box-shadow,opacity,transform]">
              {t('linkedin')}
            </a>
          )}
        </div>

        {/* Published agents grid */}
        <div className="mb-16">
          <h2 className="text-2xl font-black tracking-tighter mb-6">{t('publishedAgents')}</h2>
          {data.agents && data.agents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.agents.map((agent: any) => (
                <Link
                  key={agent.slug}
                  href={`/a/${agent.slug}`}
                  className="group block rounded-2xl border border-ink/10 bg-white/[0.02] p-6 hover:border-ink/10 hover:bg-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                >
                  {agent.hero_image_url && (
                    <div className="aspect-video rounded-xl overflow-hidden mb-4 bg-white">
                      <img src={agent.hero_image_url} alt={agent.agent_name} className="w-full h-full object-cover group-hover:scale-105 transition-transform motion-reduce:transition-none duration-300" loading="lazy" />
                    </div>
                  )}
                  <div className="text-lg font-bold mb-1 group-hover:text-ink-soft">
                    {agent.agent_name}
                  </div>
                  {agent.tagline && (
                    <p className="text-ink-mute text-sm line-clamp-2 mb-3">{agent.tagline}</p>
                  )}
                  <div className="text-xs font-mono text-leaf">
                    {agent.cta_label || 'Try it free'} →
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-16 text-ink-mute">{t('noAgents')}</div>
          )}
        </div>
      </div>

      <footer className="border-t border-ink/10 py-8 px-6 text-center text-ink-mute text-sm">
        {t('poweredBy')}
      </footer>
    </div>
  )
}
