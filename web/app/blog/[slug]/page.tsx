import Link from 'next/link'
import { notFound } from 'next/navigation'

import MarkdownContent from '@/components/content/MarkdownContent'
import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getAllBlogPosts, getBlogPostBySlug } from '@/lib/content'

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

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const post = await getBlogPostBySlug(slug)

  if (!post) {
    notFound()
  }

  return (
    <PublicPageFrame mainClassName="pt-28 pb-20 px-4 sm:px-6">
      <article className="mx-auto max-w-3xl rounded-[2rem] border border-black/10 bg-white/72 p-8 shadow-[0_24px_60px_rgba(0,0,0,0.05)] backdrop-blur sm:p-12">
        <Link
          href="/blog"
          className="inline-flex items-center text-sm font-medium text-[#5b564e] transition-colors hover:text-[#171717]"
        >
          ← Back to blog
        </Link>

        <div className="mt-6">
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#7a736a]">
            {post.publishedAt ? <span>{formatDate(post.publishedAt)}</span> : null}
            {post.authors.length > 0 ? <span>• {post.authors.map((author) => author.name).join(', ')}</span> : null}
          </div>
          <h1 className="mt-4 text-4xl font-semibold tracking-[-0.05em] text-[#171717] sm:text-5xl">
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

        <div className="mt-10 border-t border-black/10 pt-10">
          <MarkdownContent content={post.content} />
        </div>
      </article>
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
