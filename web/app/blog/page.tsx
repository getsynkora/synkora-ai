import Link from 'next/link'

import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getAllBlogPosts } from '@/lib/content'

export const metadata = {
  title: 'Blog – Synkora',
  description: 'Architecture deep dives, launch notes, and practical guides from the Synkora team.',
}

export default async function BlogPage({
  searchParams,
}: {
  searchParams: Promise<{ tag?: string }>
}) {
  const { tag: activeTag } = await searchParams
  const posts = await getAllBlogPosts()
  const [featuredPost, ...otherPosts] = posts
  const topicStats = getTopicStats(posts)

  // Tag filtered view
  if (activeTag) {
    const filtered = posts.filter((p) => p.tags.includes(activeTag))
    return (
      <PublicPageFrame mainClassName="pt-28 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <Link
            href="/blog"
            className="inline-flex items-center text-sm font-medium text-ink-soft transition-colors hover:text-ink"
          >
            ← All posts
          </Link>

          <div className="mt-6">
            <p className="text-[11px] font-semibold text-ink-mute">Topic</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-[-0.05em] text-ink sm:text-5xl">
              {activeTag}
            </h1>
            <p className="mt-2 text-[15px] text-ink-mute">
              {filtered.length} post{filtered.length === 1 ? '' : 's'}
            </p>
          </div>

          <div className="mt-10 space-y-0 overflow-hidden rounded-[2rem] border border-black/10 bg-paper shadow-soft">
            {filtered.length === 0 ? (
              <p className="px-8 py-10 text-[15px] text-ash">No posts found under this topic.</p>
            ) : (
              filtered.map((post, i) => (
                <Link
                  key={post.slug}
                  href={`/blog/${post.slug}`}
                  className="group flex items-start gap-5 px-8 py-7 transition-colors hover:bg-sand-deep"
                  style={{ borderTop: i === 0 ? 'none' : '1px solid #d8d2c8' }}
                >
                  <div className="mt-0.5 shrink-0 text-night transition-colors group-hover:text-leaf">
                    <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="10" y="10" width="12" height="12" rx="2" />
                      <path d="M16 4v6M16 22v6M4 16h6M22 16h6M7 7l4.2 4.2M20.8 20.8l4.2 4.2M25 7l-4.2 4.2M11.2 20.8 7 25" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    {post.publishedAt && (
                      <p className="text-[12px] text-ash">{formatDate(post.publishedAt)}</p>
                    )}
                    <p className="mt-1 line-clamp-2 text-[1.3rem] font-semibold leading-snug tracking-[-0.04em] text-ink transition-colors group-hover:text-leaf">
                      {post.title}
                    </p>
                    {post.excerpt && (
                      <p className="mt-1.5 line-clamp-2 text-[14px] leading-6 text-ink-soft">{post.excerpt}</p>
                    )}
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {post.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
                            tag === activeTag
                              ? 'border-leaf bg-leaf-wash text-leaf'
                              : 'border-paper-dim text-ink-mute'
                          }`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>

          {/* Other topics */}
          {topicStats.filter((t) => t.label !== activeTag).length > 0 && (
            <div className="mt-10">
              <p className="text-[11px] font-semibold text-ink-mute">Other topics</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {topicStats
                  .filter((t) => t.label !== activeTag)
                  .map((topic) => (
                    <Link
                      key={topic.label}
                      href={`/blog?tag=${encodeURIComponent(topic.label)}`}
                      className="rounded-full border border-paper-dim bg-white px-3.5 py-2 text-[12px] font-medium text-ink-soft shadow-soft transition-colors hover:border-leaf hover:text-leaf"
                    >
                      {topic.label}
                      <span className="ml-1.5 opacity-60">{topic.count}</span>
                    </Link>
                  ))}
              </div>
            </div>
          )}
        </div>
      </PublicPageFrame>
    )
  }

  return (
    <PublicPageFrame mainClassName="overflow-hidden pt-36 pb-20 px-4 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <section>

          <div>
            <div className="max-w-3xl">

              <h1 className="text-4xl font-semibold leading-[0.98] tracking-[-0.06em] text-ink sm:text-5xl lg:text-[3.85rem]">
                The operating notes behind building AI agents that actually ship.
              </h1>

              <p className="mt-5 max-w-2xl text-[17px] leading-8 text-ink-soft sm:text-[18px]">
                Launches, architecture decisions, implementation lessons, and practical guides from the team building
                Synkora. Less vague AI commentary. More product, systems, and execution.
              </p>

              {topicStats.length > 0 && (
                <div className="mt-6 flex flex-wrap gap-2.5">
                  {topicStats.map((topic) => (
                    <span
                      key={topic.label}
                      className="rounded-full border border-leaf-wash bg-white px-3.5 py-2 text-[12px] font-medium text-leaf shadow-soft"
                    >
                      {topic.label}
                      <span className="ml-2 text-ink-mute">{topic.count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

          </div>
        </section>

        {featuredPost ? (
          <section className="mt-10">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-[-0.05em] text-ink sm:text-3xl">
                  Start with the clearest thread
                </h2>
              </div>
            </div>

            <article className="group relative overflow-hidden rounded-[2.4rem] border border-black/10 bg-white p-7 shadow-soft sm:p-8 lg:p-10">

              <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-end">
                <div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-mute">
                    {featuredPost.publishedAt ? <span>{formatDate(featuredPost.publishedAt)}</span> : null}
                    {featuredPost.authors.length > 0 ? <span className="text-ink-soft">{featuredPost.authors.map((author) => author.name).join(', ')}</span> : null}
                  </div>

                  <h3 className="mt-4 text-[2rem] font-semibold leading-tight tracking-[-0.05em] text-ink sm:text-[2.5rem]">
                    <Link href={`/blog/${featuredPost.slug}`} className="transition-colors hover:text-leaf">
                      {featuredPost.title}
                    </Link>
                  </h3>

                  <p className="mt-4 max-w-3xl text-[16px] leading-8 text-ink-soft sm:text-[17px]">
                    {featuredPost.excerpt}
                  </p>

                  {featuredPost.tags.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {featuredPost.tags.map((tag) => (
                        <span
                          key={`${featuredPost.slug}-${tag}`}
                          className="rounded-full border border-leaf-wash bg-leaf-wash px-3 py-1 text-xs font-medium text-leaf"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-3">

                  <Link
                    href={`/blog/${featuredPost.slug}`}
                    className="inline-flex w-full items-center justify-center rounded-full bg-ink px-5 py-3 text-sm font-semibold text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
                  >
                    Read the featured article
                  </Link>
                </div>
              </div>
            </article>
          </section>
        ) : null}

        {otherPosts.length > 0 ? (
          <section className="mt-10">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-[-0.05em] text-ink sm:text-3xl">
                  More from the journal
                </h2>
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {otherPosts.map((post) => (
                <article
                  key={post.slug}
                  className="group relative overflow-hidden rounded-[2rem] border border-black/10 bg-white p-7 shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300 hover:-translate-y-1 hover:shadow-soft"
                >

                  <div className="flex flex-wrap items-center gap-2 text-xs text-ink-mute">
                    {post.publishedAt ? <span>{formatDate(post.publishedAt)}</span> : null}
                    {post.authors.length > 0 ? <span className="text-ink-soft">{post.authors.map((author) => author.name).join(', ')}</span> : null}
                  </div>

                  <h3 className="mt-4 text-[1.8rem] font-semibold tracking-[-0.05em] text-ink">
                    <Link href={`/blog/${post.slug}`} className="transition-colors hover:text-leaf">
                      {post.title}
                    </Link>
                  </h3>

                  <p className="mt-3 text-[15px] leading-7 text-ink-soft">{post.excerpt}</p>

                  {post.tags.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {post.tags.map((tag) => (
                        <span
                          key={`${post.slug}-${tag}`}
                          className="rounded-full border border-leaf-wash bg-leaf-wash px-3 py-1 text-xs font-medium text-leaf"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="mt-6">
                    <Link
                      href={`/blog/${post.slug}`}
                      className="inline-flex items-center text-sm font-medium text-ink underline decoration-black/15 underline-offset-4 transition-colors hover:text-leaf"
                    >
                      Read article
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {posts.length === 0 ? (
          <section className="mt-10 rounded-[2rem] border border-dashed border-black/15 bg-white/60 p-10 text-center">
            <h2 className="text-3xl font-semibold tracking-[-0.05em] text-ink">
              The journal is about to start filling up.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-[16px] leading-8 text-ink-soft">
              This page is wired to the main product site. As new posts land in `docs/blog`, they will automatically
              appear here.
            </p>
          </section>
        ) : null}
      </div>
    </PublicPageFrame>
  )
}

function getTopicStats(posts: Awaited<ReturnType<typeof getAllBlogPosts>>) {
  const counts = new Map<string, number>()

  for (const post of posts) {
    for (const tag of post.tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 6)
    .map(([label, count]) => ({ label, count }))
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}
