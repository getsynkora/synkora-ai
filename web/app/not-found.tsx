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
    accent: 'bg-[#ffe8de] text-[#cf673e]',
  },
  {
    href: '/pricing',
    label: 'Pricing',
    description: 'Review plans, limits, and what you can run on the platform.',
    icon: Layers3,
    accent: 'bg-[#e4f2ef] text-[#2d8b69]',
  },
  {
    href: '/docs',
    label: 'Docs',
    description: 'Jump into setup, APIs, and self-hosting documentation.',
    icon: BookOpen,
    accent: 'bg-[#fff0d8] text-[#d58a27]',
  },
]

export default function NotFound() {
  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-16 pt-28 sm:px-6 sm:pb-24 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[6%] top-[10%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.96),transparent_72%)]" />
          <div className="absolute right-[8%] top-[12%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.95),transparent_72%)]" />
          <div className="absolute left-[16%] top-[48%] h-48 w-48 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.16),transparent_72%)]" />
          <div className="absolute bottom-[10%] right-[16%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(255,214,170,0.18),transparent_72%)]" />
        </div>

        <div className="relative mx-auto max-w-6xl">
          <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
            <div className="rounded-[2.4rem] border border-black/10 bg-white/68 p-7 shadow-[0_24px_60px_rgba(0,0,0,0.06)] backdrop-blur md:p-10">
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/72 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[#4e473f]">
                <SearchSlash className="h-4 w-4 text-[#2d8b69]" />
                404 Error
              </div>

              <div className="mt-6 text-[5rem] font-semibold leading-none tracking-[-0.08em] text-[#171717]/10 sm:text-[7rem]">
                404
              </div>

              <h1 className="mt-3 max-w-3xl text-4xl font-medium tracking-[-0.06em] text-[#171717] sm:text-6xl">
                This page is
                <span className="editorial-highlight mt-3 inline-block">not here</span>
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-[#5b554c] sm:text-xl">
                The link may be outdated, the route may have changed, or the page may no longer exist. Use one of the paths below to get back into the platform.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-[#171717] px-6 py-3.5 text-sm font-semibold text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
                >
                  <Home className="h-4 w-4" />
                  Back to Home
                </Link>
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-black/10 bg-white/72 px-6 py-3.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-white"
                >
                  Start Building
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>

            <div className="relative overflow-hidden rounded-[2.4rem] border border-black/10 bg-[#171717] p-7 text-white shadow-[0_32px_90px_rgba(0,0,0,0.18)] md:p-9">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_26%),radial-gradient(circle_at_84%_18%,rgba(125,229,193,0.18),transparent_24%),radial-gradient(circle_at_20%_82%,rgba(255,214,170,0.14),transparent_22%)]" />
              <div className="absolute inset-[10px] rounded-[2rem] border border-white/10" />

              <div className="relative">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/6 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[#d7d0c5]">
                  <Sparkles className="h-4 w-4 text-[#7de5c1]" />
                  Suggested Routes
                </div>

                <h2 className="mt-6 text-3xl font-medium tracking-[-0.05em] text-white">
                  Popular next steps
                </h2>
                <p className="mt-4 text-base leading-7 text-[#cfc7bb]">
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
                            <ArrowRight className="h-4 w-4 text-white/50 transition-transform group-hover:translate-x-0.5" />
                          </div>
                          <p className="mt-1 text-sm leading-6 text-[#c7c0b5]">{item.description}</p>
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
