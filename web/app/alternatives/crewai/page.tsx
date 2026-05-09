import Link from 'next/link'
import { Zap, Check, X, Minus } from 'lucide-react'

export const metadata = {
  title: 'Synkora vs CrewAI',
  description: 'Synkora vs CrewAI: platform vs Python framework. Synkora adds web UI, multi-tenancy, deployment channels, RAG, billing, and monitoring on top of agent orchestration.',
}

const features = [
  { name: 'Web UI', synkora: 'yes', crewai: 'no' },
  { name: 'Multi-tenant', synkora: 'yes', crewai: 'no' },
  { name: 'Self-hostable', synkora: 'yes', crewai: 'no' },
  { name: 'RAG / knowledge bases', synkora: 'yes', crewai: 'no' },
  { name: 'Multi-channel deployment (Slack, WhatsApp…)', synkora: 'yes', crewai: 'no' },
  { name: 'Built-in billing / credits', synkora: 'yes', crewai: 'no' },
  { name: 'Scheduled tasks', synkora: 'yes', crewai: 'no' },
  { name: 'Observability / tracing', synkora: 'yes', crewai: 'partial' },
  { name: 'Multi-agent orchestration', synkora: 'yes', crewai: 'yes' },
  { name: 'Role-based agent definitions', synkora: 'partial', crewai: 'yes' },
  { name: 'Full Python API flexibility', synkora: 'no', crewai: 'yes' },
  { name: 'Embeddable in any Python app', synkora: 'no', crewai: 'yes' },
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
    { '@type': 'ListItem', position: 3, name: 'Synkora vs CrewAI', item: 'https://synkora.ai/alternatives/crewai' },
  ],
}

export default function CrewAIComparisonPage() {
  return (
    <div className="min-h-screen bg-white">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <nav className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-9 h-9 bg-red-500 rounded-lg flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Synkora</span>
          </Link>
          <Link href="/signup" className="px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 transition-colors">
            Try Free
          </Link>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="mb-6 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-700">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-gray-700">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>CrewAI</span>
        </div>

        <h1 className="text-4xl font-bold text-gray-900 mb-4">Synkora vs CrewAI</h1>
        <p className="text-xl text-gray-600 mb-12 max-w-3xl">
          CrewAI is a Python framework for role-based multi-agent orchestration. Synkora is a full deployment platform. They solve different problems — the choice depends on whether you need infrastructure or code-level flexibility.
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-gray-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is CrewAI?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              CrewAI is an open-source Python framework for building role-based multi-agent systems. Agents are defined in code with explicit roles, goals, and tools. It has a large developer community and supports flexible Python-native agent definitions. There is no built-in web UI, deployment infrastructure, or multi-tenancy.
            </p>
          </div>
          <div className="bg-red-50 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">What is Synkora?</h2>
            <p className="text-gray-600 text-sm leading-relaxed">
              Synkora is a multitenant LLM application platform. It includes a web UI for agent creation, RAG knowledge bases, multi-channel deployment (Slack, WhatsApp, Teams, Telegram, web widget), built-in billing, scheduled tasks, and an observability layer — all accessible via API or UI without writing infrastructure code.
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
                <th className="text-center px-5 py-3 font-semibold text-gray-700">CrewAI</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                  <td className="px-5 py-3 text-gray-700">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.crewai as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
            Partial = limited or in-progress support
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-red-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-red-700 mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need a web UI and no-config deployment for your team</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need multi-tenant agent access across multiple workspaces</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need to deploy agents to Slack, WhatsApp, Teams, or a web widget</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You need RAG, billing, scheduled tasks, and monitoring out of the box</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />You want to manage agents via API without building the platform yourself</li>
            </ul>
          </div>
          <div className="border border-gray-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">When to choose CrewAI</h2>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want full Python flexibility and explicit code-level agent definitions</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You're embedding agents into an existing Python application</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />Role-based orchestration logic needs to live in version-controlled code</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />You want to leverage the broad CrewAI Python ecosystem</li>
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

      <footer className="border-t border-gray-100 py-8 px-6 mt-16">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500">© 2026 Synkora. MIT License.</span>
          <div className="flex gap-6">
            <Link href="/alternatives" className="text-sm text-gray-500 hover:text-gray-700">All Comparisons</Link>
            <Link href="/terms" className="text-sm text-gray-500 hover:text-gray-700">Terms</Link>
            <Link href="/privacy" className="text-sm text-gray-500 hover:text-gray-700">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
