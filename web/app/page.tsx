import AnimatedNav from '@/components/landing/AnimatedNav'
import AnimatedHero from '@/components/landing/AnimatedHero'
import AnimatedFeatures from '@/components/landing/AnimatedFeatures'
import LandingDemoSection from '@/components/landing/LandingDemoSection'
import AgentsSectionClient from '@/components/landing/AgentsSectionClient'
import PricingPreviewClient from '@/components/landing/PricingPreviewClient'
import CTASectionClient from '@/components/landing/CTASectionClient'
import CountdownPage from '@/components/CountdownPage'
import Link from 'next/link'
import { MessageSquare, ArrowRight, Play, Code2, Blocks, Rocket } from 'lucide-react'

const COMING_SOON = process.env.NEXT_PUBLIC_COMING_SOON === 'true'

import { formatStars } from '@/lib/utils/formatStars'

async function getGitHubStars(): Promise<number | null> {
  try {
    const res = await fetch('https://api.github.com/repos/getsynkora/synkora-ai', {
      next: { revalidate: 3600 },
      headers: { Accept: 'application/vnd.github+json' },
    })
    if (!res.ok) return null
    const data = await res.json()
    return data.stargazers_count ?? null
  } catch {
    return null
  }
}

export default async function LandingPage() {
  const stars = await getGitHubStars()

  if (COMING_SOON) {
    return <CountdownPage />
  }

  return (
    <div
      className="min-h-screen bg-[#f7f2e7] text-[#191919]"
      style={{ fontFamily: '"Avenir Next", "Helvetica Neue", "Segoe UI", sans-serif' }}
    >
      <AnimatedNav />
      <AnimatedHero />

      <section className="border-y border-black/10 bg-[#f4eee1] px-6 py-8">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col items-center justify-center gap-8 text-center sm:flex-row sm:gap-14">
            <div>
              <div className="text-2xl font-semibold tracking-[-0.04em] text-[#171717]">MIT</div>
              <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[#6d675f]">Open Source License</div>
            </div>
            <div className="hidden h-8 w-px bg-black/10 sm:block" />
            <div>
              <div className="text-2xl font-semibold tracking-[-0.04em] text-[#171717]">Self-host</div>
              <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[#6d675f]">in 5 minutes</div>
            </div>
            <div className="hidden h-8 w-px bg-black/10 sm:block" />
            <div>
              <div className="text-2xl font-semibold tracking-[-0.04em] text-[#171717]">6+</div>
              <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[#6d675f]">Deployment channels</div>
            </div>
            <div className="hidden h-8 w-px bg-black/10 sm:block" />
            <div>
              <div className="text-2xl font-semibold tracking-[-0.04em] text-[#171717]">BYOK</div>
              <div className="mt-1 text-xs uppercase tracking-[0.22em] text-[#6d675f]">Bring your own LLM keys</div>
            </div>
            <div className="hidden h-8 w-px bg-black/10 sm:block" />
            <a
              href="https://github.com/getsynkora/synkora-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-[#6d675f] transition-colors hover:text-black"
            >
              <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              {stars !== null && (
                <span className="text-base font-semibold tracking-[-0.02em] text-[#3d3933]">
                  {formatStars(stars)}
                </span>
              )}
            </a>
          </div>
        </div>
      </section>

      <LandingDemoSection />

      <AnimatedFeatures />

      <section className="bg-[#f4eee1] px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Play className="h-4 w-4" />
              How It Works
            </div>
            <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-[#171717]">
              From idea to deployed agent in minutes
            </h2>
            <p className="mx-auto max-w-2xl text-xl leading-relaxed text-[#565149]">
              No infrastructure to configure. No framework to learn. Just build.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[
              { num: '01', icon: Code2, title: 'Create', desc: 'Define your agent — personality, LLM provider, tools — via UI or API' },
              { num: '02', icon: Blocks, title: 'Connect', desc: 'Add knowledge bases, database connections, and 50+ integrations' },
              { num: '03', icon: MessageSquare, title: 'Test', desc: 'Use the built-in playground to iterate with real-time feedback' },
              { num: '04', icon: Rocket, title: 'Deploy', desc: 'Ship to Slack, WhatsApp, Teams, web widget, or REST API' },
            ].map((step, idx) => (
              <div
                key={idx}
                className="relative rounded-[2rem] border border-black/10 bg-white/60 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#79dfbc] text-[#11231d]">
                  <step.icon className="h-6 w-6" />
                </div>
                <span className="absolute right-4 top-4 text-4xl font-medium tracking-[-0.05em] text-black/10">{step.num}</span>
                <h3 className="mb-2 text-xl font-semibold tracking-[-0.03em] text-[#171717]">{step.title}</h3>
                <p className="text-sm leading-relaxed text-[#575149]">{step.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 text-center">
            <Link href="/how-it-works" className="inline-flex items-center gap-2 font-semibold text-[#1f1d19] hover:text-black">
              See the full walkthrough
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <section className="bg-[#171717] px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid items-center gap-12 md:grid-cols-2">
            <div>
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 font-mono text-sm text-[#7de5c1]">
                <span className="h-2 w-2 rounded-full bg-[#7de5c1]" />
                Self-hosted in minutes
              </div>
              <h2 className="mb-4 text-3xl font-medium tracking-[-0.04em] text-white">
                Your infrastructure. Your data. Your rules.
              </h2>
              <p className="mb-6 leading-relaxed text-[#cfc7bb]">
                Run Synkora on your own servers with Docker. No data leaves your environment. Use your own PostgreSQL, Redis, and S3-compatible storage. MIT licensed — no usage fees, no phone-home.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row">
                <a
                  href="/docs"
                  className="inline-flex items-center gap-2 rounded-full bg-[#f7f2e7] px-5 py-2.5 text-sm font-semibold text-[#181818] transition-colors hover:bg-white"
                >
                  Self-host docs
                  <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  href="https://github.com/getsynkora/synkora-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/5 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                >
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  View on GitHub
                </a>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-[#0f0f0f] p-6 font-mono text-sm">
              <div className="mb-4 flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <div className="h-3 w-3 rounded-full bg-[#febc2e]" />
                <div className="h-3 w-3 rounded-full bg-[#28c840]" />
                <span className="ml-2 text-xs text-[#7d766c]">terminal</span>
              </div>
              <div className="space-y-2 text-sm">
                <div><span className="text-[#7d766c]"># Clone the repo</span></div>
                <div><span className="text-[#7de5c1]">$</span> <span className="text-white">git clone https://github.com/getsynkora/synkora-ai</span></div>
                <div><span className="text-[#7de5c1]">$</span> <span className="text-white">cd synkora-ai</span></div>
                <div className="pt-1"><span className="text-[#7d766c]"># Copy env and start</span></div>
                <div><span className="text-[#7de5c1]">$</span> <span className="text-white">cp .env.example .env</span></div>
                <div><span className="text-[#7de5c1]">$</span> <span className="text-white">docker-compose up -d</span></div>
                <div className="pt-2 text-[#cfc7bb]">
                  <span className="text-[#7de5c1]">✓</span> Running at <span className="text-[#c4d8ff]">http://localhost:3005</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <AgentsSectionClient />

      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-5xl">
          <div className="mb-12 text-center">
            <h2 className="mb-3 text-3xl font-medium tracking-[-0.04em] text-[#171717]">Platform, not a framework</h2>
            <p className="mx-auto max-w-xl text-lg leading-relaxed text-[#575149]">
              Frameworks give you building blocks. Synkora gives you the whole platform — deployed, monitored, and ready to use.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                name: 'LangChain / CrewAI',
                color: 'border-black/10',
                tag: 'Framework',
                tagColor: 'bg-black/5 text-[#5f5a52]',
                points: ['Python code only', 'No web UI', 'No deployment infrastructure', 'No multi-tenancy', 'You build everything yourself'],
                cta: null,
              },
              {
                name: 'Synkora',
                color: 'border-[#79dfbc] ring-2 ring-[#79dfbc]',
                tag: 'Platform',
                tagColor: 'bg-[#79dfbc]/25 text-[#153129]',
                points: ['Web UI + REST API', 'Multi-tenant workspaces', 'Deploy to 6+ channels', 'RAG, billing, scheduling built in', 'Self-host or cloud'],
                cta: 'Get Started Free',
              },
              {
                name: 'Flowise',
                color: 'border-black/10',
                tag: 'Visual builder',
                tagColor: 'bg-black/5 text-[#5f5a52]',
                points: ['Drag-and-drop UI', 'Single-user, local-first', 'Good for prototyping', 'Not built for production teams', 'No multi-tenancy'],
                cta: null,
              },
            ].map((col, i) => (
              <div
                key={i}
                className={`rounded-[2rem] border bg-white/60 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur ${col.color} ${i === 1 ? 'shadow-[0_24px_60px_rgba(0,0,0,0.08)]' : ''}`}
              >
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-semibold tracking-[-0.03em] text-[#171717]">{col.name}</h3>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${col.tagColor}`}>{col.tag}</span>
                </div>
                <ul className="mb-5 space-y-2">
                  {col.points.map((p, j) => (
                    <li key={j} className="flex items-start gap-2 text-sm text-[#575149]">
                      <span className={`mt-0.5 shrink-0 text-base leading-none ${i === 1 ? 'text-[#2d8b69]' : 'text-black/25'}`}>{i === 1 ? '✓' : '–'}</span>
                      {p}
                    </li>
                  ))}
                </ul>
                {col.cta && (
                  <Link
                    href="https://app.synkora.ai/signup"
                    className="block w-full rounded-full bg-[#191919] px-4 py-2.5 text-center text-sm font-semibold uppercase tracking-[0.14em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
                  >
                    {col.cta}
                  </Link>
                )}
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <Link href="/alternatives" className="inline-flex items-center gap-2 text-sm font-semibold text-[#1f1d19] hover:text-black">
              See detailed comparisons
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <PricingPreviewClient />
      <CTASectionClient />
    </div>
  )
}
