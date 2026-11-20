import Link from 'next/link'
import { Check, X, Minus } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

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
    { '@type': 'ListItem', position: 3, name: 'Synkora vs CrewAI', item: 'https://synkora.ai/alternatives/crewai' },
  ],
}

export default function CrewAIComparisonPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="mb-6 text-sm text-ink-mute">
          <Link href="/" className="hover:text-ink-soft">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/alternatives" className="hover:text-ink-soft">Alternatives</Link>
          <span className="mx-2">/</span>
          <span>CrewAI</span>
        </div>

        <h1 className="text-4xl font-bold text-ink mb-4">Synkora vs CrewAI</h1>
        <p className="text-xl text-ink-soft mb-12 max-w-3xl">
          CrewAI is a Python framework for role-based multi-agent orchestration. Synkora is a full deployment platform. They solve different problems, the choice depends on whether you need infrastructure or code-level flexibility.
        </p>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="bg-cream rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is CrewAI?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              CrewAI is an open-source Python framework for building role-based multi-agent systems. Agents are defined in code with explicit roles, goals, and tools. It has a large developer community and supports flexible Python-native agent definitions. There is no built-in web UI, deployment infrastructure, or multi-tenancy.
            </p>
          </div>
          <div className="bg-leaf-wash rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink mb-3">What is Synkora?</h2>
            <p className="text-ink-soft text-sm leading-relaxed">
              Synkora is a multitenant LLM application platform. It includes a web UI for agent creation, RAG knowledge bases, multi-channel deployment (Slack, WhatsApp, Teams, Telegram, web widget), built-in billing, scheduled tasks, and an observability layer, all accessible via API or UI without writing infrastructure code.
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
                <th className="text-center px-5 py-3 font-semibold text-ink-soft">CrewAI</th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? 'bg-white' : 'bg-cream/50'}>
                  <td className="px-5 py-3 text-ink-soft">{row.name}</td>
                  <td className="px-5 py-3 text-center"><Cell value={row.synkora as 'yes' | 'no' | 'partial'} /></td>
                  <td className="px-5 py-3 text-center"><Cell value={row.crewai as 'yes' | 'no' | 'partial'} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 bg-cream border-t border-line text-xs text-ink-mute">
            Partial = limited or in-progress support
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div className="border border-leaf/30 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-leaf mb-4">When to choose Synkora</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need a web UI and no-config deployment for your team</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need multi-tenant agent access across multiple workspaces</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need to deploy agents to Slack, WhatsApp, Teams, or a web widget</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You need RAG, billing, scheduled tasks, and monitoring out of the box</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-leaf flex-shrink-0 mt-0.5" />You want to manage agents via API without building the platform yourself</li>
            </ul>
          </div>
          <div className="border border-line rounded-xl p-6">
            <h2 className="text-lg font-semibold text-ink-soft mb-4">When to choose CrewAI</h2>
            <ul className="space-y-2 text-sm text-ink-soft">
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You want full Python flexibility and explicit code-level agent definitions</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You're embedding agents into an existing Python application</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />Role-based orchestration logic needs to live in version-controlled code</li>
              <li className="flex gap-2"><Check className="w-4 h-4 text-steel flex-shrink-0 mt-0.5" />You want to leverage the broad CrewAI Python ecosystem</li>
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
