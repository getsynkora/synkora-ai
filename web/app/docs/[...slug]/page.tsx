import Link from 'next/link'
import { notFound } from 'next/navigation'

import DocsSidebar from '@/components/content/DocsSidebar'
import MarkdownContent from '@/components/content/MarkdownContent'
import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getAdjacentDocs, getAllDocs, getDocBySlug, getDocsNavigation } from '@/lib/content'

export async function generateStaticParams() {
  const docs = await getAllDocs()
  return docs
    .filter((doc) => doc.slugParts.length > 0)
    .map((doc) => ({ slug: doc.slugParts }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params
  const doc = await getDocBySlug(slug)

  if (!doc) {
    return {
      title: 'Docs – Synkora',
    }
  }

  return {
    title: `${doc.title} – Synkora Docs`,
    description: doc.description,
  }
}

export default async function DocDetailPage({
  params,
}: {
  params: Promise<{ slug: string[] }>
}) {
  const { slug } = await params
  const [doc, navigation, adjacent] = await Promise.all([
    getDocBySlug(slug),
    getDocsNavigation(),
    getAdjacentDocs(slug),
  ])

  if (!doc) {
    notFound()
  }

  return (
    <PublicPageFrame mainClassName="pt-28 pb-20 px-4 sm:px-6">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <DocsSidebar sections={navigation} currentHref={doc.href} />
        </div>

        <article className="rounded-[2rem] border border-black/10 bg-white/72 p-8 shadow-soft sm:p-10">
          <div className="border-b border-black/10 pb-8">
            <Link
              href="/docs"
              className="inline-flex items-center text-sm font-medium text-ink-soft transition-colors hover:text-ink"
            >
              ← Back to docs
            </Link>
            <p className="mt-5 text-[11px] font-semibold text-ink-mute">
              {doc.section.replace(/-/g, ' ')}
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-ink sm:text-5xl">
              {doc.title}
            </h1>
            {doc.description ? (
              <p className="mt-4 max-w-3xl text-lg leading-8 text-ink-soft">{doc.description}</p>
            ) : null}
          </div>

          <div className="mt-10">
            <MarkdownContent content={doc.content} />
          </div>

          <div className="mt-12 grid gap-4 border-t border-black/10 pt-8 sm:grid-cols-2">
            {adjacent.previous ? (
              <Link
                href={adjacent.previous.href}
                className="rounded-[1.4rem] border border-black/10 bg-cream p-5 transition-colors hover:border-mint"
              >
                <p className="text-xs text-ink-mute">Previous</p>
                <p className="mt-2 text-base font-semibold text-ink">{adjacent.previous.title}</p>
              </Link>
            ) : <div />}

            {adjacent.next ? (
              <Link
                href={adjacent.next.href}
                className="rounded-[1.4rem] border border-black/10 bg-cream p-5 text-left transition-colors hover:border-mint"
              >
                <p className="text-xs text-ink-mute">Next</p>
                <p className="mt-2 text-base font-semibold text-ink">{adjacent.next.title}</p>
              </Link>
            ) : null}
          </div>
        </article>
      </div>
    </PublicPageFrame>
  )
}
