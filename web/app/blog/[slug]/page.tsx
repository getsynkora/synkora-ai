import { Lora } from 'next/font/google'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { BlogArticleFade } from '@/components/blog/BlogArticleWrapper'
import BlogArtisticEffects from '@/components/blog/BlogArtisticEffects'
import ReadingProgress from '@/components/blog/ReadingProgress'
import MarkdownContent from '@/components/content/MarkdownContent'
import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getAllBlogPosts, getBlogPostBySlug } from '@/lib/content'

const lora = Lora({
  subsets: ['latin'],
  variable: '--font-lora',
  display: 'swap',
  weight: ['400', '600', '700'],
  style: ['normal', 'italic'],
})

export async function generateStaticParams() {
  const posts = await getAllBlogPosts()
  return posts.map((post) => ({ slug: post.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const post = await getBlogPostBySlug(slug)

  if (!post) {
    return {
      title: 'Blog – Synkora',
    }
  }

  return {
    title: `${post.title} – Synkora`,
    description: post.excerpt,
  }
}

// Assign a simple line-art SVG icon per post based on its primary tag or slug
function PostIcon({ tags, slug }: { tags: string[]; slug: string }) {
  const key = tags[0] ?? slug

  if (key.includes('observ') || key.includes('lens') || slug.includes('lens')) {
    return (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="16" cy="16" r="6" />
        <circle cx="16" cy="16" r="2.5" fill="currentColor" stroke="none" />
        <path d="M2 16c3-6 8-10 14-10s11 4 14 10c-3 6-8 10-14 10S5 22 2 16z" />
      </svg>
    )
  }
  if (key.includes('arch') || key.includes('mesh') || key.includes('multi') || slug.includes('mesh')) {
    return (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="16" cy="16" r="13" />
        <path d="M3 16h26M16 3a20 20 0 0 1 0 26M16 3a20 20 0 0 0 0 26M6 8a24 24 0 0 1 20 0M6 24a24 24 0 0 0 20 0" />
      </svg>
    )
  }
  if (key.includes('scale') || key.includes('worker') || key.includes('bot') || slug.includes('bot')) {
    return (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="16" cy="16" r="4" />
        <path d="M16 2v4M16 26v4M2 16h4M26 16h4M5.4 5.4l2.8 2.8M23.8 23.8l2.8 2.8M5.4 26.6l2.8-2.8M23.8 8.2l2.8-2.8" />
      </svg>
    )
  }
  if (key.includes('context') || key.includes('compact') || key.includes('memory') || slug.includes('context')) {
    return (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="4" y="4" width="24" height="24" rx="3" />
        <path d="M4 12h24M12 12v16M8 8h2M14 8h2M20 8h2" />
      </svg>
    )
  }
  if (key.includes('knowledge') || key.includes('integr') || slug.includes('knowledge')) {
    return (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M6 4h14l6 6v18H6zM20 4v6h6M10 14h12M10 19h12M10 24h8" />
      </svg>
    )
  }
  // default: circuit / agent
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="10" y="10" width="12" height="12" rx="2" />
      <path d="M16 4v6M16 22v6M4 16h6M22 16h6M7 7l4.2 4.2M20.8 20.8l4.2 4.2M25 7l-4.2 4.2M11.2 20.8 7 25" />
    </svg>
  )
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const [post, allPosts] = await Promise.all([getBlogPostBySlug(slug), getAllBlogPosts()])

  if (!post) {
    notFound()
  }

  const otherPosts = allPosts.filter((p) => p.slug !== slug)

  // Collect all unique tags from other posts, sorted by frequency
  const tagCounts = new Map<string, number>()
  for (const p of otherPosts) {
    for (const t of p.tags) {
      tagCounts.set(t, (tagCounts.get(t) ?? 0) + 1)
    }
  }
  const allTags = Array.from(tagCounts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([t]) => t)

  return (
    <PublicPageFrame mainClassName="pt-28 pb-20 px-4 sm:px-6">
      <ReadingProgress />
      <BlogArtisticEffects />

      <div className={`${lora.variable} relative z-10 mx-auto max-w-6xl`}>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
          {/* Main article */}
          <BlogArticleFade>
            <article
              data-blog-article
              className="relative overflow-hidden rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-[0_32px_80px_rgba(0,0,0,0.07)] backdrop-blur sm:p-14"
            >
              {/* Ambient blobs */}
              <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
                <div className="blog-blob-a absolute -left-20 -top-16 h-64 w-64 rounded-full bg-[#79dfbc]/14 blur-3xl" />
                <div className="blog-blob-b absolute -bottom-20 -right-16 h-72 w-72 rounded-full bg-[#ffd7a8]/18 blur-3xl" />
                <div className="blog-blob-a absolute right-1/3 top-1/2 h-48 w-48 rounded-full bg-[#ffb7c9]/10 blur-3xl" style={{ animationDelay: '8s' }} />
                {/* Rotating arc decorations */}
                <div className="blog-arc blog-arc-outer absolute -right-28 -top-28" />
                <div className="blog-arc blog-arc-inner absolute -bottom-16 -left-16" />
              </div>

              <div className="relative">
                <Link
                  href="/blog"
                  className="inline-flex items-center text-sm font-medium text-[#5b564e] transition-colors hover:text-[#171717]"
                >
                  ← Back to blog
                </Link>

                <div className="mt-7">
                  <div className="flex flex-wrap items-center gap-2 text-sm text-[#7a736a]">
                    {post.publishedAt ? <span>{formatDate(post.publishedAt)}</span> : null}
                    {post.authors.length > 0 ? <span>· {post.authors.map((author) => author.name).join(', ')}</span> : null}
                  </div>
                  <h1 className="mt-4 font-[family-name:var(--font-lora)] text-4xl font-bold leading-tight tracking-[-0.04em] text-[#171717] sm:text-5xl">
                    {post.title}
                  </h1>
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
                </div>

                <div className="mt-12 border-t border-black/8 pt-12">
                  <MarkdownContent content={post.content} />
                </div>
              </div>
            </article>
          </BlogArticleFade>

          {/* Sidebar */}
          {otherPosts.length > 0 && (
            <BlogArticleFade delay={0.18}>
            <aside className="lg:sticky lg:top-8">
              <div className="overflow-hidden rounded-[2rem] border border-black/10 bg-[#f6f1e7] shadow-[0_24px_60px_rgba(0,0,0,0.06)]">

                {/* Tag filter widget */}
                {allTags.length > 0 && (
                  <div className="border-b border-[#d8d2c8] px-7 pt-7 pb-5">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7a736a]">
                      Browse by topic
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {/* "All" pill */}
                      <Link
                        href="/blog"
                        className="rounded-full border border-[#c8c2b8] px-3 py-1.5 text-[12px] font-medium text-[#5b564e] transition-colors hover:border-[#1a1714] hover:text-[#1a1714]"
                      >
                        All
                        <span className="ml-1.5 opacity-60">{otherPosts.length}</span>
                      </Link>
                      {allTags.map((tag) => (
                        <Link
                          key={tag}
                          href={`/blog?tag=${encodeURIComponent(tag)}`}
                          className="rounded-full border border-[#c8c2b8] px-3 py-1.5 text-[12px] font-medium text-[#5b564e] transition-colors hover:border-[#2d8b69] hover:text-[#2d8b69]"
                        >
                          {tag}
                          <span className="ml-1.5 opacity-60">{tagCounts.get(tag)}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

                {/* Post list */}
                <div className="px-7 pt-5 pb-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7a736a]">
                    More from the blog
                  </p>
                </div>

                <div>
                  {otherPosts.map((p, i) => (
                      <Link
                        key={p.slug}
                        href={`/blog/${p.slug}`}
                        className="group block px-7 py-6 transition-colors hover:bg-[#ede8db]"
                        style={{ borderTop: i === 0 ? 'none' : '1px solid #d8d2c8' }}
                      >
                        <div className="flex items-start gap-4">
                          <span className="mt-0.5 shrink-0 text-[#3a3530] transition-colors group-hover:text-[#2d8b69]">
                            <PostIcon tags={p.tags} slug={p.slug} />
                          </span>
                          <div className="min-w-0">
                            <p className="line-clamp-2 text-[1.3rem] font-semibold leading-snug tracking-[-0.04em] text-[#1a1714] transition-colors group-hover:text-[#2d8b69]">
                              {p.title}
                            </p>
                            {p.tags.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {p.tags.slice(0, 3).map((tag) => (
                                  <span
                                    key={tag}
                                    className="rounded-full border border-[#c8c2b8] px-2 py-0.5 text-[10px] font-medium text-[#7a736a]"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </Link>
                  ))}
                </div>
              </div>
            </aside>
            </BlogArticleFade>
          )}
        </div>
      </div>
    </PublicPageFrame>
  )
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}
