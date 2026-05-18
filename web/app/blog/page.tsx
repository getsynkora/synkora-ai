import Link from 'next/link'

import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getAllBlogPosts } from '@/lib/content'

export const metadata = {
  title: 'Blog – Synkora',
  description: 'Architecture deep dives, launch notes, and practical guides from the Synkora team.',
}

export default async function BlogPage() {
  const posts = await getAllBlogPosts()
  const [featuredPost, ...otherPosts] = posts
  const topicStats = getTopicStats(posts)
  const allAuthors = new Set(posts.flatMap((post) => post.authors.map((author) => author.name)))
  const latestDate = featuredPost?.publishedAt ? formatDate(featuredPost.publishedAt) : null

  return (
    <PublicPageFrame mainClassName="overflow-hidden pt-28 pb-20 px-4 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <section className="relative overflow-hidden rounded-[2.5rem] border border-black/10 bg-[#f6f1e7] px-6 py-8 shadow-[0_30px_80px_rgba(0,0,0,0.07)] sm:px-8 sm:py-10 lg:px-10">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-6 h-48 w-48 rounded-full bg-[#79dfbc]/20 blur-3xl" />
            <div className="absolute right-[-4rem] top-[-2rem] h-56 w-56 rounded-full bg-[#ffd7a8]/30 blur-3xl" />
            <div className="absolute bottom-[-3rem] right-24 h-40 w-40 rounded-full bg-[#ffb7c9]/20 blur-3xl" />
          </div>

          <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_360px] lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#6f675d]">
                <span className="h-2 w-2 rounded-full bg-[#2d8b69]" />
                Synkora Blog
              </div>

              <h1 className="mt-5 text-4xl font-semibold leading-[0.98] tracking-[-0.06em] text-[#171717] sm:text-5xl lg:text-[3.85rem]">
                The operating notes behind building AI agents that actually ship.
              </h1>

              <p className="mt-5 max-w-2xl text-[17px] leading-8 text-[#5b564e] sm:text-[18px]">
                Launches, architecture decisions, implementation lessons, and practical guides from the team building
                Synkora. Less vague AI commentary. More product, systems, and execution.
              </p>

              {topicStats.length > 0 && (
                <div className="mt-6 flex flex-wrap gap-2.5">
                  {topicStats.map((topic) => (
                    <span
                      key={topic.label}
                      className="rounded-full border border-[#d7eadf] bg-white/80 px-3.5 py-2 text-[12px] font-medium text-[#2d8b69] shadow-[0_8px_20px_rgba(0,0,0,0.04)]"
                    >
                      {topic.label}
                      <span className="ml-2 text-[#7a736a]">{topic.count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-[2rem] border border-black/10 bg-[#171717] p-5 text-[#f7f2e7] shadow-[0_20px_45px_rgba(0,0,0,0.18)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#d2c7b8]">
                Editorial Snapshot
              </p>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <div className="rounded-[1.3rem] border border-white/10 bg-white/5 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-[#c9bfae]">Articles</p>
                  <p className="mt-2 text-3xl font-semibold tracking-[-0.05em]">{posts.length}</p>
                </div>

                <div className="rounded-[1.3rem] border border-white/10 bg-white/5 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-[#c9bfae]">Topics</p>
                  <p className="mt-2 text-3xl font-semibold tracking-[-0.05em]">{topicStats.length}</p>
                </div>
              </div>

              <div className="mt-3 rounded-[1.3rem] border border-white/10 bg-white/5 p-4">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[#c9bfae]">Latest Signal</p>
                <p className="mt-2 text-sm leading-6 text-[#f7f2e7]">
                  {latestDate ? `Most recent publication: ${latestDate}.` : 'New writing will appear here as it ships.'}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#c9bfae]">
                  {allAuthors.size > 0 ? `${allAuthors.size} contributing voice${allAuthors.size > 1 ? 's' : ''}.` : 'Written by the Synkora team.'}
                </p>
              </div>
            </div>
          </div>
        </section>

        {featuredPost ? (
          <section className="mt-10">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7a736a]">
                  Featured Story
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.05em] text-[#171717] sm:text-3xl">
                  Start with the clearest thread
                </h2>
              </div>
            </div>

            <article className="group relative overflow-hidden rounded-[2.4rem] border border-black/10 bg-[#151412] p-7 text-[#f7f2e7] shadow-[0_28px_80px_rgba(0,0,0,0.16)] sm:p-8 lg:p-10">
              <div className="pointer-events-none absolute inset-0">
                <div className="absolute left-[-4rem] top-[-3rem] h-56 w-56 rounded-full bg-[#79dfbc]/16 blur-3xl transition-transform duration-500 group-hover:scale-110" />
                <div className="absolute bottom-[-5rem] right-[-2rem] h-64 w-64 rounded-full bg-[#ffb7c9]/12 blur-3xl transition-transform duration-500 group-hover:scale-110" />
              </div>

              <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-end">
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[#d2c7b8]">
                    {featuredPost.publishedAt ? <span>{formatDate(featuredPost.publishedAt)}</span> : null}
                    {featuredPost.authors.length > 0 ? <span>• {featuredPost.authors.map((author) => author.name).join(', ')}</span> : null}
                  </div>

                  <h3 className="mt-4 text-[2rem] font-semibold leading-tight tracking-[-0.05em] text-white sm:text-[2.5rem]">
                    <Link href={`/blog/${featuredPost.slug}`} className="transition-colors hover:text-[#79dfbc]">
                      {featuredPost.title}
                    </Link>
                  </h3>

                  <p className="mt-4 max-w-3xl text-[16px] leading-8 text-[#d8d0c4] sm:text-[17px]">
                    {featuredPost.excerpt}
                  </p>

                  {featuredPost.tags.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {featuredPost.tags.map((tag) => (
                        <span
                          key={`${featuredPost.slug}-${tag}`}
                          className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-medium text-[#79dfbc]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="rounded-[1.4rem] border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[#c9bfae]">Why it matters</p>
                    <p className="mt-2 text-sm leading-6 text-[#f7f2e7]">
                      Product decisions, architecture tradeoffs, and delivery notes in one thread.
                    </p>
                  </div>

                  <Link
                    href={`/blog/${featuredPost.slug}`}
                    className="inline-flex w-full items-center justify-center rounded-full bg-[#79dfbc] px-5 py-3 text-sm font-semibold text-[#171717] transition-transform hover:-translate-y-0.5"
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
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7a736a]">
                  Recent Writing
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.05em] text-[#171717] sm:text-3xl">
                  More from the journal
                </h2>
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {otherPosts.map((post) => (
                <article
                  key={post.slug}
                  className="group relative overflow-hidden rounded-[2rem] border border-black/10 bg-white/75 p-7 shadow-[0_24px_60px_rgba(0,0,0,0.05)] backdrop-blur transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_30px_80px_rgba(0,0,0,0.09)]"
                >
                  <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#79dfbc] via-[#ffd7a8] to-[#ffb7c9] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

                  <div className="flex flex-wrap items-center gap-2 text-xs text-[#7a736a]">
                    {post.publishedAt ? <span>{formatDate(post.publishedAt)}</span> : null}
                    {post.authors.length > 0 ? <span>• {post.authors.map((author) => author.name).join(', ')}</span> : null}
                  </div>

                  <h3 className="mt-4 text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717]">
                    <Link href={`/blog/${post.slug}`} className="transition-colors hover:text-[#2d8b69]">
                      {post.title}
                    </Link>
                  </h3>

                  <p className="mt-3 text-[15px] leading-7 text-[#5b564e]">{post.excerpt}</p>

                  {post.tags.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                      {post.tags.map((tag) => (
                        <span
                          key={`${post.slug}-${tag}`}
                          className="rounded-full border border-[#d7eadf] bg-[#edf8f3] px-3 py-1 text-xs font-medium text-[#2d8b69]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="mt-6">
                    <Link
                      href={`/blog/${post.slug}`}
                      className="inline-flex items-center text-sm font-medium text-[#171717] underline decoration-black/15 underline-offset-4 transition-colors hover:text-[#2d8b69]"
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
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7a736a]">
              Blog
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-[#171717]">
              The journal is about to start filling up.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-[16px] leading-8 text-[#5b564e]">
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
