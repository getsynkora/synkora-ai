import Link from 'next/link'
import { ArrowRight, Zap } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Synkora Alternatives & Comparisons – Enterprise AI Platform',
  description: 'How Synkora compares to Dify, CrewAI, LangChain, Flowise, and OpenClaw. Enterprise security, SAML SSO, RBAC, and multi-tenant deployment vs. frameworks and personal tools.',
}

const comparisons = [
  {
    slug: 'dify',
    name: 'Dify',
    type: 'Platform',
    summary: 'Open-source LLM app platform with a visual workflow DAG editor. Synkora has stronger API-first design and multi-channel deployment.',
  },
  {
    slug: 'crewai',
    name: 'CrewAI',
    type: 'Python Framework',
    summary: 'Code-first Python framework for multi-agent orchestration. No web UI, no built-in deployment or multi-tenancy.',
  },
  {
    slug: 'langchain',
    name: 'LangChain',
    type: 'Python Library',
    summary: 'Extensive library for building LLM applications in Python. Requires significant custom code for UI, deployment, and infrastructure.',
  },
  {
    slug: 'flowise',
    name: 'Flowise',
    type: 'Visual Builder',
    summary: 'Drag-and-drop LLM flow builder, local-first and single-user. Good for prototyping; Synkora is built for multi-tenant production.',
  },
  {
    slug: 'openclaw',
    name: 'OpenClaw',
    type: 'Personal Assistant',
    summary: 'Local-first personal AI assistant daemon for individuals. Different use case: OpenClaw is for personal productivity, Synkora is for teams building AI products.',
  },
]

export default function AlternativesIndexPage() {
  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[8%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[10%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
        </div>
        <div className="relative max-w-5xl mx-auto">
          <div className="mb-4 text-sm text-[#7a736a]">
            <Link href="/" className="hover:text-[#4b463e]">Home</Link>
            <span className="mx-2">/</span>
            <span>Alternatives</span>
          </div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur">
            <Zap className="w-4 h-4" />
            Comparisons
          </div>
          <h1 className="text-4xl font-medium tracking-[-0.05em] text-[#171717] mb-4 sm:text-5xl">Synkora vs the alternatives</h1>
          <p className="text-lg text-[#5a544a] mb-8 max-w-3xl leading-8">
            How Synkora fits in the AI landscape alongside frameworks, platforms, and personal tools. Enterprise security is the differentiator.
          </p>

          <div className="rounded-[1.8rem] border border-black/8 bg-white/62 p-6 mb-12 max-w-3xl shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur">
            <h2 className="font-semibold text-[#171717] mb-2">How Synkora fits in the ecosystem</h2>
            <p className="text-[#5f594f] text-sm leading-relaxed">
              Synkora is an <strong className="text-[#171717]">enterprise deployment platform</strong> — SAML/OIDC SSO, RBAC, audit logs, IP allowlist, and encryption key rotation are built in.
              It sits above frameworks like LangChain and CrewAI, and alongside self-hostable platforms like Dify but with production-grade security controls neither offers.
              If you need a full-stack, multi-tenant environment for building and operating AI agents with enterprise compliance, Synkora is built for that.
            </p>
            <p className="text-[#5f594f] text-sm leading-relaxed mt-3">
              <strong className="text-[#171717]">Platform</strong> — Synkora, Dify &nbsp;|&nbsp; <strong className="text-[#171717]">Framework</strong> — LangChain, CrewAI &nbsp;|&nbsp; <strong className="text-[#171717]">Visual builder</strong> — Flowise &nbsp;|&nbsp; <strong className="text-[#171717]">Personal assistant</strong> — OpenClaw
            </p>
          </div>
        </div>
      </section>

      <section className="bg-[#f4eee1] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-5xl mx-auto">
          <div className="grid gap-4">
            {comparisons.map((c) => (
              <Link
                key={c.slug}
                href={`/alternatives/${c.slug}`}
                className="group flex items-start gap-5 rounded-[1.6rem] border border-black/8 bg-white/72 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur transition-all hover:shadow-[0_22px_52px_rgba(0,0,0,0.08)] hover:-translate-y-0.5"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-lg font-semibold tracking-[-0.03em] text-[#171717]">Synkora vs {c.name}</h2>
                    <span className="rounded-full border border-black/10 bg-[#e4f2ef] px-2 py-0.5 text-xs font-semibold text-[#2d8b69]">{c.type}</span>
                  </div>
                  <p className="text-[#5f594f] text-sm leading-6">{c.summary}</p>
                </div>
                <ArrowRight className="w-5 h-5 text-[#7a736a] group-hover:text-[#2d8b69] flex-shrink-0 mt-1 transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
