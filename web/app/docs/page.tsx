import Link from 'next/link'

import DocsSidebar from '@/components/content/DocsSidebar'
import PublicPageFrame from '@/components/public/PublicPageFrame'
import { getDocsHomeSections, getDocsNavigation } from '@/lib/content'

export const metadata = {
  title: 'Docs – Synkora',
  description: 'Documentation for setup, integrations, APIs, deployment, and architecture in the main Synkora web app.',
}

export default async function DocsPage() {
  const [sections, navigation] = await Promise.all([
    getDocsHomeSections(),
    getDocsNavigation(),
  ])

  return (
    <PublicPageFrame mainClassName="pt-28 pb-20 px-4 sm:px-6">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-28 lg:self-start">
          <DocsSidebar sections={navigation} currentHref="/docs" />
        </div>

        <div className="rounded-[2rem] border border-black/10 bg-white/72 p-8 shadow-soft sm:p-10">
          <p className="text-[11px] font-semibold text-ink-mute">
            Documentation
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-ink sm:text-5xl">
            Everything now lives in the main Synkora app
          </h1>
          <p className="mt-4 max-w-3xl text-lg leading-8 text-ink-soft">
            Setup guides, API reference, SDK docs, and architecture notes no longer need a separate Docusaurus surface.
          </p>

          <div className="mt-10 grid gap-5 md:grid-cols-2">
            {sections.map((section) => (
              <Link
                key={section.label}
                href={section.href}
                className="rounded-[1.6rem] border border-black/10 bg-cream p-6 transition-transform motion-reduce:transition-none duration-200 hover:-translate-y-0.5 hover:border-mint"
              >
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-ink">
                    {section.label}
                  </h2>
                  <span className="rounded-full bg-leaf-wash px-3 py-1 text-xs font-semibold text-leaf">
                    {section.count} {section.count === 1 ? 'page' : 'pages'}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-7 text-ink-soft">
                  {section.description || `Browse ${section.label.toLowerCase()} documentation.`}
                </p>
                <div className="mt-4 text-sm font-medium text-ink">
                  Open section
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </PublicPageFrame>
  )
}
