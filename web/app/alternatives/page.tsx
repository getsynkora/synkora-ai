import Link from 'next/link'
import { ArrowRight, Zap } from 'lucide-react'

export const metadata = {
  title: 'Synkora Alternatives & Comparisons',
  description: 'How Synkora compares to Dify, CrewAI, LangChain, Flowise, and OpenClaw. Honest, factual comparisons covering platform features, architecture, and target use cases.',
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
    <div className="min-h-screen bg-white">
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
        <div className="mb-4 text-sm text-gray-500">
          <Link href="/" className="hover:text-gray-700">Home</Link>
          <span className="mx-2">/</span>
          <span>Alternatives</span>
        </div>

        <h1 className="text-4xl font-bold text-gray-900 mb-4">Synkora Alternatives & Comparisons</h1>
        <p className="text-xl text-gray-600 mb-4 max-w-3xl">
          How Synkora fits in the AI landscape alongside frameworks, platforms, and personal tools.
        </p>

        <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 mb-12 max-w-3xl">
          <h2 className="font-semibold text-gray-900 mb-2">How Synkora fits in the ecosystem</h2>
          <p className="text-gray-700 text-sm leading-relaxed">
            Synkora is a <strong>multitenant deployment platform</strong> — it sits above frameworks like LangChain and CrewAI,
            and alongside self-hostable platforms like Dify. If you need a full-stack environment for building, deploying,
            and managing AI agents across teams and channels (Slack, WhatsApp, Teams, web widget, API), Synkora is built for that.
            If you need maximum Python flexibility or a simple personal assistant, a framework or personal tool may serve you better.
          </p>
          <p className="text-gray-700 text-sm leading-relaxed mt-3">
            <strong>Platform</strong> — Synkora, Dify &nbsp;|&nbsp; <strong>Framework</strong> — LangChain, CrewAI &nbsp;|&nbsp; <strong>Visual builder</strong> — Flowise &nbsp;|&nbsp; <strong>Personal assistant</strong> — OpenClaw
          </p>
        </div>

        <div className="grid gap-4">
          {comparisons.map((c) => (
            <Link
              key={c.slug}
              href={`/alternatives/${c.slug}`}
              className="group flex items-start gap-5 p-6 border border-gray-200 rounded-xl hover:border-red-300 hover:shadow-md transition-all"
            >
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-lg font-semibold text-gray-900">Synkora vs {c.name}</h2>
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{c.type}</span>
                </div>
                <p className="text-gray-600 text-sm">{c.summary}</p>
              </div>
              <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-red-500 flex-shrink-0 mt-1 transition-colors" />
            </Link>
          ))}
        </div>
      </div>

      <footer className="border-t border-gray-100 py-8 px-6 mt-16">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500">© 2026 Synkora. MIT License.</span>
          <div className="flex gap-6">
            <Link href="/terms" className="text-sm text-gray-500 hover:text-gray-700">Terms</Link>
            <Link href="/privacy" className="text-sm text-gray-500 hover:text-gray-700">Privacy</Link>
            <Link href="/contact" className="text-sm text-gray-500 hover:text-gray-700">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
