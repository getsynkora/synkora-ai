import Link from 'next/link'
import { Check, X, Minus } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Synkora vs LangChain',
  description: 'Synkora vs LangChain: complete deployment platform vs Python library. No custom infrastructure code required with Synkora.',
}

const features = [
  { name: 'Web UI', synkora: 'yes', langchain: 'no' },
  { name: 'Multi-tenant', synkora: 'yes', langchain: 'no' },
  { name: 'Self-hostable platform', synkora: 'yes', langchain: 'no' },
  { name: 'RAG / knowledge bases', synkora: 'yes', langchain: 'yes' },
  { name: 'Multi-channel deployment', synkora: 'yes', langchain: 'no' },
  { name: 'Built-in billing / credits', synkora: 'yes', langchain: 'no' },
  { name: 'Observability / tracing', synkora: 'yes', langchain: 'partial' },
  { name: 'HITL approval gates', synkora: 'yes', langchain: 'no' },
  { name: 'Scheduled tasks', synkora: 'yes', langchain: 'no' },
  { name: 'Integration ecosystem', synkora: 'partial', langchain: 'yes' },
  { name: 'Python embeddable', synkora: 'no', langchain: 'yes' },
  { name: 'Maximum code flexibility', synkora: 'no', langchain: 'yes' },
]

function Cell({ value }: { value: 'yes' | 'no' | 'partial' }) {
  if (value === 'yes') return <Check className="w-5 h-5 text-leaf mx-auto" />
  if (value === 'no') return <X className="w-5 h-5 text-ink-mute mx-auto" />
  return <Minus className="w-5 h-5 text-ink-mute mx-auto" />
}

const breadcrumbLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://synkora.ai' },
    { '@type': 'ListItem', position: 2, name: 'Alternatives', item: 'https://synkora.ai/alternatives' },
    { '@type': 'ListItem', position: 3, name: 'Synkora vs LangChain', item: 'https://synkora.ai/alternatives/langchain' },
  ],
}

export default function LangChainComparisonPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="mb-6 text-sm text-ink-mute">
          <Link href="/" className="hover:text-ink-soft">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-ink-soft">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>LangChain</span>
        </div>

        <h1 className="text-4xl font-bold text-ink mb-4">Synkora vs LangChain</h1>
        <p className="text-xl text-ink-soft mb-12 max-w-3xl">
          LangChain is a Python library, a powerful set of building blocks. Synkora is a complete platform. LangChain gives you maximum flexibility; Synkora gives you everything assembled and deployable without writing infrastructure code.
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-cream rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is LangChain?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              LangChain is an open-source Python (and JavaScript) library for building LLM applications. It provides a large ecosystem of integrations, chains, and agent primitives. Building production applications requires significant custom code for UI, deployment, multi-tenancy, and infrastructure.
            </p>
          </div>
          <div className="bg-leaf-wash rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is Synkora?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              Synkora is a full deployment platform for LLM agents. It includes a web UI, multi-tenant workspaces, RAG, multi-channel delivery, billing, observability, and an API-first backend, ready to self-host or run on Synkora Cloud without writing infrastructure code.
            </p>
          </div>
        </div>

        <h2 className="text-2xl font-bold text-ink mb-6">Feature Comparison</h2>
        <div className="border border-line rounded-xl overflow-hidden mb-16">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-cream border-b border-line">
                <th className="text-left px-5 py-3 font-semibold text-ink-soft">Feature</th>
                <th className="text-center px-5 py-3 font-semibold text-leaf">Synkora</th>
                <th className="text-center px-5 py-3 font-semibold text-ink-soft">LangChain</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-cream/50'}>
                  <td className="px-5 py-3 text-ink-soft">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.langchain as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-cream border-t border-line text-xs text-ink-mute">
            Partial = limited or requires additional configuration
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-leaf/30 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-leaf mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You want a complete platform without building deployment infrastructure</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need multi-tenant agent management across teams</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need channels (Slack, WhatsApp, Teams) without custom integration code</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need billing, observability, and RAG ready to go</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />Non-technical team members need to manage or interact with agents</li>
            </ul>
          </div>
          <div className="border border-line rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink-soft mb-4">When to choose LangChain</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You need maximum flexibility and full control of every component</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You're embedding LLM logic into an existing Python application</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You need LangChain's massive integration ecosystem</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />Your team has the engineering capacity to build and maintain the full stack</li>
            </ul>
          </div>
        </div>

        <div className="bg-ink rounded-2xl p-8 text-center text-paper">
          <h2 className="text-2xl font-bold mb-2">Try Synkora free</h2>
          <p className="text-paper-dim mb-6">Self-host in minutes or use Synkora Cloud. MIT licensed.</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/signup" className="px-6 py-3 bg-mint text-ink font-semibold rounded-xl hover:bg-white transition-colors">
              Get Started Free
            </Link>
            <Link href="/how-it-works" className="px-6 py-3 text-paper font-semibold rounded-xl hover:bg-white/10 transition-colors border border-white/25">
              See How It Works
            </Link>
          </div>
        </div>
      </div>
    </PublicPageFrame>
  )
}
