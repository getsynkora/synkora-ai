import Link from 'next/link'
import { Check, X, Minus } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Synkora vs Flowise',
  description: 'Synkora vs Flowise: production multi-tenant platform vs local drag-and-drop flow builder. Compare features, deployment, and use cases.',
}

const features = [
  { name: 'Multi-tenant', synkora: 'yes', flowise: 'no' },
  { name: 'Production-grade deployment', synkora: 'yes', flowise: 'partial' },
  { name: 'Self-hostable', synkora: 'yes', flowise: 'yes' },
  { name: 'API-first', synkora: 'yes', flowise: 'partial' },
  { name: 'RAG / knowledge bases', synkora: 'yes', flowise: 'yes' },
  { name: 'Multi-channel (Slack, WhatsApp, Teams)', synkora: 'yes', flowise: 'no' },
  { name: 'MCP server support', synkora: 'yes', flowise: 'no' },
  { name: 'HITL approval gates', synkora: 'yes', flowise: 'no' },
  { name: 'Sub-agents', synkora: 'yes', flowise: 'partial' },
  { name: 'Built-in billing / credits', synkora: 'yes', flowise: 'no' },
  { name: 'Scheduled tasks', synkora: 'yes', flowise: 'no' },
  { name: 'Visual drag-and-drop builder', synkora: 'partial', flowise: 'yes' },
  { name: 'Local-first / desktop friendly', synkora: 'no', flowise: 'yes' },
]

function Cell({ value }: { value: 'yes' | 'no' | 'partial' }) {
  if (value === 'yes') return <Check className="w-5 h-5 text-green-500 mx-auto" />
  if (value === 'no') return <X className="w-5 h-5 text-red-400 mx-auto" />
  return <Minus className="w-5 h-5 text-yellow-400 mx-auto" />
}

const breadcrumbLd = {
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://synkora.ai' },
    { '@type': 'ListItem', position: 2, name: 'Alternatives', item: 'https://synkora.ai/alternatives' },
    { '@type': 'ListItem', position: 3, name: 'Synkora vs Flowise', item: 'https://synkora.ai/alternatives/flowise' },
  ],
}

export default function FlowiseComparisonPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="mb-6 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-700">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-gray-700">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>Flowise</span>
        </div>

        <h1 className="text-4xl font-bold text-gray-900 mb-4">Synkora vs Flowise</h1>
        <p className="text-xl text-gray-600 mb-12 max-w-3xl">
          Flowise is a drag-and-drop LLM flow builder, designed for local use and rapid prototyping. Synkora is a production multi-tenant platform. If you're prototyping solo, Flowise is excellent. If you're deploying for teams or customers, Synkora is built for that.
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-gray-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is Flowise?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              Flowise is an open-source drag-and-drop tool for building LLM flows. It runs locally and is excellent for quickly prototyping chains, RAG pipelines, and simple agents without writing code. It's single-user focused and best suited for development and experimentation.
            </p>
          </div>
          <div className="bg-red-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is Synkora?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              Synkora is a multitenant LLM platform built for production. It handles multi-tenant team access, API-first agent deployment, multi-channel delivery (Slack, WhatsApp, Teams, Telegram), RAG knowledge bases, billing, scheduled tasks, and observability — all in one self-hostable platform.
            </p>
          </div>
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-6">Feature Comparison</h2>
        <div className="border border-gray-200 rounded-xl overflow-hidden mb-16">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-5 py-3 font-semibold text-gray-700">Feature</th>
                <th className="text-center px-5 py-3 font-semibold text-red-600">Synkora</th>
                <th className="text-center px-5 py-3 font-semibold text-gray-700">Flowise</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="px-5 py-3 text-gray-700">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.flowise as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
            Partial = limited or requires additional setup
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-red-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-red-700 mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You're deploying agents for a team or customer-facing product</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need multi-tenant access control across workspaces</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need Slack, WhatsApp, Teams, or Telegram delivery</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need MCP, HITL, billing, or scheduled tasks</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need an API-first architecture for product integration</li>
            </ul>
          </div>
          <div className="border border-gray-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">When to choose Flowise</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want the fastest local prototyping experience</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />Your audience is non-technical and drag-and-drop is a priority</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You're building a personal project or internal demo</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You need a single-user local tool without server setup</li>
            </ul>
          </div>
        </div>

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
