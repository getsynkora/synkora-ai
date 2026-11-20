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
      <section className="relative overflow-hidden bg-paper px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="relative max-w-5xl mx-auto">
          <div className="mb-4 text-sm text-ink-mute">
            <Link href="/" className="hover:text-ink-soft">Home</Link>
            <span className="mx-2">/</span>
            <span>Alternatives</span>
          </div>
          <h1 className="text-4xl font-medium tracking-[-0.05em] text-ink mb-4 sm:text-5xl">Synkora vs the alternatives</h1>
          <p className="text-lg text-ink-soft mb-8 max-w-3xl leading-8">
            How Synkora fits in the AI landscape alongside frameworks, platforms, and personal tools. Enterprise security is the differentiator.
          </p>

          <div className="rounded-[1.8rem] border border-black/8 bg-white/62 p-6 mb-12 max-w-3xl shadow-soft">
            <h2 className="font-semibold text-ink mb-2">How Synkora fits in the ecosystem</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              Synkora is an <strong className="text-ink">enterprise deployment platform</strong>, SAML/OIDC SSO, RBAC, audit logs, IP allowlist, and encryption key rotation are built in.
              It sits above frameworks like LangChain and CrewAI, and alongside self-hostable platforms like Dify but with production-grade security controls neither offers.
              If you need a full-stack, multi-tenant environment for building and operating AI agents with enterprise compliance, Synkora is built for that.
            </p>
            <p className="text-ink-soft text-sm leading-relaxed mt-3">
              <strong className="text-ink">Platform</strong>, Synkora, Dify &nbsp;|&nbsp; <strong className="text-ink">Framework</strong>, LangChain, CrewAI &nbsp;|&nbsp; <strong className="text-ink">Visual builder</strong>, Flowise &nbsp;|&nbsp; <strong className="text-ink">Personal assistant</strong>, OpenClaw
            </p>
          </div>
        </div>
      </section>

      <section className="bg-sand px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-5xl mx-auto">
          <div className="grid gap-4">
            {comparisons.map((c) => (
              <Link
                key={c.slug}
                href={`/alternatives/${c.slug}`}
                className="group flex items-start gap-5 rounded-[1.6rem] border border-black/8 bg-white/72 p-6 shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:shadow-soft hover:-translate-y-0.5"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-lg font-semibold tracking-[-0.03em] text-ink">Synkora vs {c.name}</h2>
                    <span className="rounded-full border border-black/10 bg-leaf-wash px-2 py-0.5 text-xs font-semibold text-leaf">{c.type}</span>
                  </div>
                  <p className="text-ink-soft text-sm leading-6">{c.summary}</p>
                </div>
                <ArrowRight className="w-5 h-5 text-ink-mute group-hover:text-leaf flex-shrink-0 mt-1 transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
