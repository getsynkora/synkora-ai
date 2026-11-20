import Link from 'next/link'
import { Check, X, Minus } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Synkora vs OpenClaw',
  description: 'Synkora vs OpenClaw: team AI platform vs personal AI assistant. Different tools for fundamentally different use cases.',
}

const features = [
  { name: 'Multi-tenant / team access', synkora: 'yes', openclaw: 'no' },
  { name: 'API-first for product integration', synkora: 'yes', openclaw: 'no' },
  { name: 'RAG / knowledge bases', synkora: 'yes', openclaw: 'no' },
  { name: 'Multi-channel deployment (web widget, API)', synkora: 'yes', openclaw: 'no' },
  { name: 'Built-in billing / credits', synkora: 'yes', openclaw: 'no' },
  { name: 'Scheduled autonomous tasks', synkora: 'yes', openclaw: 'no' },
  { name: 'HITL approval gates', synkora: 'yes', openclaw: 'no' },
  { name: 'Local model support', synkora: 'partial', openclaw: 'yes' },
  { name: 'Voice interface', synkora: 'no', openclaw: 'yes' },
  { name: 'iMessage / Signal integration', synkora: 'no', openclaw: 'yes' },
  { name: 'Browser control', synkora: 'no', openclaw: 'yes' },
  { name: 'Shell execution (local)', synkora: 'no', openclaw: 'yes' },
  { name: 'Single-user personal assistant', synkora: 'no', openclaw: 'yes' },
  { name: 'Mac / Windows / Linux daemon', synkora: 'no', openclaw: 'yes' },
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
    { '@type': 'ListItem', position: 3, name: 'Synkora vs OpenClaw', item: 'https://synkora.ai/alternatives/openclaw' },
  ],
}

export default function OpenClawComparisonPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="mb-6 text-sm text-ink-mute">
          <Link href="/" className="hover:text-ink-soft">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-ink-soft">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>OpenClaw</span>
        </div>

        <h1 className="text-4xl font-bold text-ink mb-4">Synkora vs OpenClaw</h1>
        <p className="text-xl text-ink-soft mb-8 max-w-3xl">
          Synkora and OpenClaw are not direct competitors, they solve fundamentally different problems. OpenClaw is a local-first personal AI assistant for individuals. Synkora is a platform for teams building and deploying AI products.
        </p>

        <div className="bg-sand-deep border border-honey rounded-xl p-5 mb-12 max-w-3xl">
          <p className="text-gold text-sm">
            <strong>Honest framing:</strong> If you&apos;re looking for a personal AI assistant that runs on your Mac, handles your iMessages, and controls your browser, OpenClaw is the right tool. If you&apos;re building AI agents for a team, a product, or customers, Synkora is the right tool. These pages exist for search discoverability, not because we think one product is better than the other in every context.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-cream rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is OpenClaw?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              OpenClaw is a local-first personal AI assistant daemon for Mac, Windows, and Linux. It&apos;s single-user by design, supports local models, voice, browser control, shell execution, and integrates with personal messaging (WhatsApp, Telegram, Discord, iMessage, Signal). Built for individual productivity with privacy as a core principle.
            </p>
          </div>
          <div className="bg-leaf-wash rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is Synkora?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              Synkora is a multitenant platform for teams and companies building AI products. It includes team management, API-first agent deployment, RAG knowledge bases, multi-channel delivery (Slack, WhatsApp, Teams, web widget), billing, scheduled tasks, and observability, designed for production workloads and product companies.
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
                <th className="text-center px-5 py-3 font-semibold text-ink-soft">OpenClaw</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-cream/50'}>
                  <td className="px-5 py-3 text-ink-soft">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.openclaw as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-cream border-t border-line text-xs text-ink-mute">
            Partial = limited support
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-leaf/30 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-leaf mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You&apos;re a team or company building an AI-powered product</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need multi-tenant agent management across workspaces</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need to deploy agents to end-users via API, web widget, or messaging bots</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need RAG over company data with team access controls</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need billing, observability, and production-grade infrastructure</li>
            </ul>
          </div>
          <div className="border border-line rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink-soft mb-4">When to choose OpenClaw</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You want a personal AI assistant that runs locally on your machine</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You need iMessage, Signal, or personal messaging integrations</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You need voice interaction and browser control</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />Privacy and local processing are your top priority</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You&apos;re an individual, not managing agents for a team</li>
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
