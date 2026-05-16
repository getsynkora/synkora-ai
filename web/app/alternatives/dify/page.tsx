import Link from 'next/link'
import { Check, X, Minus } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Synkora vs Dify',
  description: 'Synkora vs Dify: a detailed comparison of two open-source LLM application platforms. API-first design, multi-channel deployment, MCP, HITL, and more.',
}

const features = [
  { name: 'Open source', synkora: 'yes', dify: 'yes' },
  { name: 'Self-hostable', synkora: 'yes', dify: 'yes' },
  { name: 'Multi-tenant', synkora: 'yes', dify: 'yes' },
  { name: 'RAG / knowledge bases', synkora: 'yes', dify: 'yes' },
  { name: 'Multi-provider LLM routing', synkora: 'yes', dify: 'yes' },
  { name: 'Visual workflow DAG editor', synkora: 'partial', dify: 'yes' },
  { name: 'SSE / WebSocket streaming', synkora: 'yes', dify: 'partial' },
  { name: 'Slack / WhatsApp / Teams / Telegram', synkora: 'yes', dify: 'no' },
  { name: 'MCP server support', synkora: 'yes', dify: 'no' },
  { name: 'HITL approval gates', synkora: 'yes', dify: 'no' },
  { name: 'Sub-agents', synkora: 'yes', dify: 'partial' },
  { name: 'Agent API keys', synkora: 'yes', dify: 'no' },
  { name: 'Scheduled tasks', synkora: 'yes', dify: 'no' },
  { name: 'Built-in billing / credits', synkora: 'yes', dify: 'partial' },
]

function Cell({ value }: { value: 'yes' | 'no' | 'partial' }) {
  if (value === 'yes') return <Check className="w-5 h-5 text-green-500 mx-auto" />
  if (value === 'no') return <X className="w-5 h-5 text-red-400 mx-auto" />
  return <Minus className="w-5 h-5 text-yellow-400 mx-auto" aria-label="Partial" />
}

const breadcrumbLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://synkora.ai' },
    { '@type': 'ListItem', position: 2, name: 'Alternatives', item: 'https://synkora.ai/alternatives' },
    { '@type': 'ListItem', position: 3, name: 'Synkora vs Dify', item: 'https://synkora.ai/alternatives/dify' },
  ],
}

export default function DifyComparisonPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <div className="max-w-5xl mx-auto px-6 py-16">
        {/* Breadcrumb */}
        <div className="mb-6 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-700">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-gray-700">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>Dify</span>
        </div>

        {/* Hero */}
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Synkora vs Dify</h1>
        <p className="text-xl text-gray-600 mb-12 max-w-3xl">
          Both are open-source, self-hostable LLM application platforms with RAG and multi-tenancy. Synkora focuses on API-first design, multi-channel deployment, and production infrastructure features. Dify has a more mature visual workflow DAG editor and a larger community.
        </p>

        {/* What is Dify */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-gray-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is Dify?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              Dify is an open-source LLM application development platform. It supports RAG pipelines, visual workflow editing, multi-tenant workspaces, and a broad range of LLM providers. Dify has a large community and a polished no-code workflow experience.
            </p>
          </div>
          <div className="bg-red-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is Synkora?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              Synkora is an API-first, multitenant LLM application platform for building and deploying AI agents across multiple channels. It prioritizes production infrastructure: SSE/WebSocket streaming, multi-channel bots (Slack, WhatsApp, Teams, Telegram), MCP server support, HITL approval gates, and per-agent billing.
            </p>
          </div>
        </div>

        {/* Comparison table */}
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Feature Comparison</h2>
        <div className="border border-gray-200 rounded-xl overflow-hidden mb-16">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-5 py-3 font-semibold text-gray-700">Feature</th>
                <th className="text-center px-5 py-3 font-semibold text-red-600">Synkora</th>
                <th className="text-center px-5 py-3 font-semibold text-gray-700">Dify</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="px-5 py-3 text-gray-700">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.dify as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
            Partial = limited or experimental support
          </div>
        </div>

        {/* When to choose */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-red-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-red-700 mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need multi-channel deployment (Slack, WhatsApp, Teams, Telegram)</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need MCP server integrations</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need HITL approval gates for sensitive operations</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need SSE streaming and WebSocket APIs as first-class features</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need per-agent API keys and billing</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need scheduled autonomous tasks</li>
            </ul>
          </div>
          <div className="border border-gray-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">When to choose Dify</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want a mature, polished no-code visual workflow editor</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want a large community with extensive third-party resources</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />Your use case is primarily LLM prompt pipelines or DAG workflows</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want a more established hosted cloud option</li>
            </ul>
          </div>
        </div>

        {/* CTA */}
        <div className="bg-gradient-to-r from-red-500 to-rose-600 rounded-2xl p-8 text-center text-white">
          <h2 className="text-2xl font-bold mb-2">Try Synkora free</h2>
          <p className="text-white/90 mb-6">Self-host in minutes or use Synkora Cloud. MIT licensed.</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/signup" className="px-6 py-3 bg-white text-red-600 font-semibold rounded-xl hover:bg-gray-50 transition-colors">
              Get Started Free
            </Link>
            <Link href="/how-it-works" className="px-6 py-3 bg-white/20 text-white font-semibold rounded-xl hover:bg-white/30 transition-colors border border-white/30">
              See How It Works
            </Link>
          </div>
        </div>
      </div>
    </PublicPageFrame>
  )
}
