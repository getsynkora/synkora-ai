import Link from 'next/link'
import {
  ArrowRight,
  BookOpen,
  Compass,
  Home,
  Layers3,
  SearchSlash,
  Sparkles,
} from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Page Not Found – Synkora',
  description: 'The page you are looking for does not exist.',
}

const quickLinks = [
  {
    href: '/how-it-works',
    label: 'How It Works',
    description: 'See how the platform is structured from build to deployment.',
    icon: Compass,
    accent: 'bg-sand-deep text-rust',
  },
  {
    href: '/pricing',
    label: 'Pricing',
    description: 'Review plans, limits, and what you can run on the platform.',
    icon: Layers3,
    accent: 'bg-leaf-wash text-leaf',
  },
  {
    href: '/docs',
    label: 'Docs',
    description: 'Jump into setup, APIs, and self-hosting documentation.',
    icon: BookOpen,
    accent: 'bg-sand-deep text-warn',
  },
]

export default function NotFound() {
  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-paper px-4 pb-16 pt-28 sm:px-6 sm:pb-24 sm:pt-32">

        <div className="relative mx-auto max-w-6xl">
          <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
            <div className="rounded-[2.4rem] border border-black/10 bg-white/68 p-7 shadow-soft md:p-10">
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/72 px-4 py-2 text-xs font-semibold text-ink-soft">
                <SearchSlash className="h-4 w-4 text-leaf" />
                404 Error
              </div>

              <div className="mt-6 text-[5rem] font-semibold leading-none tracking-[-0.08em] text-ink/10 sm:text-[7rem]">
                404
              </div>

              <h1 className="mt-3 max-w-3xl text-4xl font-medium tracking-[-0.06em] text-ink sm:text-6xl">
                This page is
                <span className="mt-3 inline-block text-leaf">not here</span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-ink-soft sm:text-xl">
                The link may be outdated, the route may have changed, or the page may no longer exist. Use one of the paths below to get back into the platform.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-6 py-3.5 text-sm font-semibold text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
                >
                  <Home className="h-4 w-4" />
                  Back to Home
                </Link>
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-black/10 bg-white/72 px-6 py-3.5 text-sm font-semibold text-ink transition-colors hover:bg-white"
                >
                  Start Building
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>

            <div className="relative overflow-hidden rounded-[2.4rem] border border-black/10 bg-ink p-7 text-white shadow-soft md:p-9">
              <div className="absolute inset-0" />
              <div className="absolute inset-[10px] rounded-[2rem] border border-white/10" />

              <div className="relative">

                <h2 className="mt-6 text-3xl font-medium tracking-[-0.05em] text-white">
                  Popular next steps
                </h2>
                <p className="mt-4 text-base leading-7 text-paper-dim">
                  If you were trying to learn the platform or continue setup, these are the pages most people need next.
                </p>

                <div className="mt-8 space-y-4">
                  {quickLinks.map((item) => {
                    const Icon = item.icon

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="group flex items-start gap-4 rounded-[1.5rem] border border-white/10 bg-white/[0.05] p-4 transition-colors hover:bg-white/[0.08]"
                      >
                        <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-[1rem] ${item.accent}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-base font-semibold text-white">
                            {item.label}
                            <ArrowRight className="h-4 w-4 text-white/50 transition-transform motion-reduce:transition-none group-hover:translate-x-0.5" />
                          </div>
                          <p className="mt-1 text-sm leading-6 text-paper-dim">{item.description}</p>
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
