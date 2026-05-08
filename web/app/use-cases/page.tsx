import Link from 'next/link'
import { Zap, ArrowRight, Users, Code, BarChart3, HeadphonesIcon, PenTool, Database, Briefcase, Shield } from 'lucide-react'

export const metadata = {
  title: 'Use Cases – Synkora LLM Platform',
  description: 'See what you can build on Synkora — AI agents for product management, engineering, customer support, marketing, and more. API-first, multitenant, self-hostable.',
}

const useCases = [
  {
    id: 'product-manager',
    icon: Briefcase,
    title: 'AI Product Manager',
    subtitle: 'Keep projects on track 24/7',
    description: 'Automate the repetitive parts of product management while you focus on strategy and vision.',
    color: 'red',
    capabilities: [
      'Backlog prioritization based on business impact',
      'Sprint planning and capacity management',
      'Daily standup summaries and status reports',
      'Feature request analysis and categorization',
      'Stakeholder update generation',
      'Roadmap tracking and milestone alerts',
    ],
    integrations: ['Jira', 'Linear', 'Notion', 'Slack', 'GitHub'],
    example: 'Your AI PM reviews all new tickets overnight, prioritizes them based on your criteria, and has a sprint proposal ready by morning standup.',
  },
  {
    id: 'software-engineer',
    icon: Code,
    title: 'AI Software Engineer',
    subtitle: 'Never miss a PR again',
    description: 'An AI teammate that handles code review, documentation, and keeps your codebase healthy.',
    color: 'blue',
    capabilities: [
      'Automated code review with actionable feedback',
      'Bug triage and reproduction steps',
      'Documentation generation from code',
      'CI/CD monitoring and failure analysis',
      'Dependency update management',
      'Technical debt tracking',
    ],
    integrations: ['GitHub', 'GitLab', 'Sentry', 'Datadog', 'Slack'],
    example: 'Every PR gets reviewed within minutes with specific suggestions. Breaking CI builds trigger instant root cause analysis in Slack.',
  },
  {
    id: 'marketing-lead',
    icon: PenTool,
    title: 'AI Marketing Lead',
    subtitle: 'Scale content without scaling headcount',
    description: 'From content creation to campaign analysis, your AI marketing teammate works around the clock.',
    color: 'green',
    capabilities: [
      'Blog post and social media content generation',
      'SEO optimization and keyword research',
      'Campaign performance analysis',
      'Competitor monitoring and alerts',
      'Email campaign drafting',
      'Brand voice consistency checking',
    ],
    integrations: ['HubSpot', 'Mailchimp', 'Google Analytics', 'Semrush', 'Buffer'],
    example: 'Weekly content calendar populated automatically. Performance reports generated every Monday with actionable recommendations.',
  },
  {
    id: 'support-agent',
    icon: HeadphonesIcon,
    title: 'AI Support Agent',
    subtitle: 'Instant responses, happy customers',
    description: 'Handle customer inquiries 24/7 with intelligent escalation to human agents when needed.',
    color: 'purple',
    capabilities: [
      'Instant ticket response and resolution',
      'Knowledge base Q&A with source citations',
      'Smart escalation to human agents',
      'Sentiment analysis and priority detection',
      'Multi-language support',
      'Customer satisfaction tracking',
    ],
    integrations: ['Zendesk', 'Intercom', 'Freshdesk', 'Slack', 'Email'],
    example: 'Customer asks a question at 3 AM. AI agent resolves it in seconds using your knowledge base, with a 95% satisfaction rate.',
  },
  {
    id: 'data-analyst',
    icon: BarChart3,
    title: 'AI Data Analyst',
    subtitle: 'Insights on demand',
    description: 'Query your data in natural language and get instant analysis without writing SQL.',
    color: 'orange',
    capabilities: [
      'Natural language to SQL queries',
      'Automated report generation',
      'Anomaly detection and alerts',
      'Dashboard creation and updates',
      'Trend analysis and forecasting',
      'Cross-dataset correlation discovery',
    ],
    integrations: ['PostgreSQL', 'BigQuery', 'Snowflake', 'Metabase', 'Slack'],
    example: '"What were our top 10 customers by revenue last quarter?" - Get an instant answer with a visualization, no SQL required.',
  },
  {
    id: 'hr-coordinator',
    icon: Users,
    title: 'AI HR Coordinator',
    subtitle: 'Streamline people operations',
    description: 'From onboarding to policy questions, your AI HR assistant handles the routine so you can focus on culture.',
    color: 'pink',
    capabilities: [
      'New hire onboarding automation',
      'Policy and benefits Q&A',
      'PTO and leave request processing',
      'Interview scheduling coordination',
      'Employee feedback collection',
      'Compliance reminder management',
    ],
    integrations: ['BambooHR', 'Gusto', 'Slack', 'Google Calendar', 'Notion'],
    example: 'New employee joins? AI automatically schedules their first week, sends welcome docs, and answers their initial questions.',
  },
]

const colorClasses = {
  red: { bg: 'bg-red-100', text: 'text-red-600', border: 'border-red-200', gradient: 'from-red-500 to-rose-500' },
  blue: { bg: 'bg-blue-100', text: 'text-blue-600', border: 'border-blue-200', gradient: 'from-blue-500 to-indigo-500' },
  green: { bg: 'bg-green-100', text: 'text-green-600', border: 'border-green-200', gradient: 'from-green-500 to-emerald-500' },
  purple: { bg: 'bg-purple-100', text: 'text-purple-600', border: 'border-purple-200', gradient: 'from-purple-500 to-violet-500' },
  orange: { bg: 'bg-orange-100', text: 'text-orange-600', border: 'border-orange-200', gradient: 'from-orange-500 to-amber-500' },
  pink: { bg: 'bg-pink-100', text: 'text-pink-600', border: 'border-pink-200', gradient: 'from-pink-500 to-rose-500' },
}

export default function UseCasesPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-red-50">
      {/* Navigation */}
      <nav className="py-4 px-4 sm:px-6 border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-9 h-9 bg-red-500 rounded-lg flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Synkora</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-4">
            <Link href="/pricing" className="hidden sm:block text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Pricing
            </Link>
            <Link
              href="/signup"
              className="px-4 py-2 text-sm font-medium bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-12 sm:py-20 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-full text-sm font-semibold mb-6">
            <Users className="w-4 h-4" />
            Use Cases
          </div>
          <h1 className="text-3xl sm:text-5xl font-bold text-gray-900 mb-6">
            Build AI Agents for
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-red-600 to-rose-600">
              Every Role in Your Company
            </span>
          </h1>
          <p className="text-base sm:text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            From product management to engineering to customer support—deploy AI teammates that handle real work around the clock. Use your own LLM keys for full control and transparency.
          </p>
        </div>
      </section>

      {/* Use Cases Grid */}
      <section className="py-12 sm:py-16 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="space-y-24">
            {useCases.map((useCase, index) => {
              const colors = colorClasses[useCase.color as keyof typeof colorClasses]
              const isEven = index % 2 === 0

              return (
                <div key={useCase.id} id={useCase.id} className="scroll-mt-24">
                  <div className={`grid lg:grid-cols-2 gap-12 items-center ${!isEven ? 'lg:flex-row-reverse' : ''}`}>
                    {/* Content */}
                    <div className={!isEven ? 'lg:order-2' : ''}>
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 ${colors.bg} ${colors.text} rounded-full text-sm font-semibold mb-4`}>
                        <useCase.icon className="w-4 h-4" />
                        {useCase.subtitle}
                      </div>
                      <h2 className="text-3xl font-bold text-gray-900 mb-4">{useCase.title}</h2>
                      <p className="text-lg text-gray-600 mb-6">{useCase.description}</p>

                      {/* Capabilities */}
                      <div className="mb-6">
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Capabilities</h3>
                        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {useCase.capabilities.map((cap, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                              <svg className={`w-5 h-5 ${colors.text} flex-shrink-0 mt-0.5`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              {cap}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Integrations */}
                      <div className="mb-6">
                        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Integrations</h3>
                        <div className="flex flex-wrap gap-2">
                          {useCase.integrations.map((int, i) => (
                            <span key={i} className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full">
                              {int}
                            </span>
                          ))}
                        </div>
                      </div>

                      <Link
                        href="/signup"
                        className={`inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r ${colors.gradient} text-white font-semibold rounded-xl hover:opacity-90 transition-opacity`}
                      >
                        Build Your {useCase.title.replace('AI ', '')}
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>

                    {/* Example Card */}
                    <div className={!isEven ? 'lg:order-1' : ''}>
                      <div className={`bg-white rounded-2xl p-8 shadow-xl border ${colors.border}`}>
                        <div className={`w-16 h-16 ${colors.bg} rounded-2xl flex items-center justify-center mb-6`}>
                          <useCase.icon className={`w-8 h-8 ${colors.text}`} />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-3">Example in Action</h3>
                        <p className="text-gray-600 leading-relaxed">{useCase.example}</p>

                        <div className="mt-6 pt-6 border-t border-gray-100">
                          <div className="flex items-center gap-4">
                            <div className="flex -space-x-2">
                              {[...Array(3)].map((_, i) => (
                                <div key={i} className={`w-8 h-8 rounded-full ${colors.bg} border-2 border-white flex items-center justify-center`}>
                                  <span className={`text-xs font-semibold ${colors.text}`}>{['PM', 'ENG', 'MKT'][i]}</span>
                                </div>
                              ))}
                            </div>
                            <span className="text-sm text-gray-500">Teams using this agent</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Why Synkora Section */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Why Teams Choose Synkora</h2>
            <p className="text-lg text-gray-600">Built different from day one</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-red-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Shield className="w-7 h-7 text-red-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Your LLM Keys</h3>
              <p className="text-gray-600">Use your own API keys from OpenAI, Anthropic, or Google. No vendor lock-in, complete cost transparency.</p>
            </div>
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Code className="w-7 h-7 text-blue-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Open Source</h3>
              <p className="text-gray-600">Full source code access. Self-host on your infrastructure or use our cloud. You own your data.</p>
            </div>
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Database className="w-7 h-7 text-green-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Enterprise Ready</h3>
              <p className="text-gray-600">Multi-tenancy, RBAC, SSO, audit logs, and SOC 2 compliance. Ready for serious workloads.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-12 sm:py-16 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-br from-red-600 via-red-500 to-rose-600 rounded-3xl p-12 text-center shadow-xl">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to Build Your AI Team?</h2>
            <p className="text-lg text-white/90 mb-8 max-w-xl mx-auto">
              Start with a template or build from scratch. Deploy your first AI agent in minutes.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-8 py-4 bg-white hover:bg-gray-50 text-red-600 font-semibold rounded-xl transition-all shadow-lg"
              >
                <Zap className="w-5 h-5" />
                Get Started Free
              </Link>
              <Link
                href="/pricing"
                className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-all border border-white/20"
              >
                View Pricing
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-gray-200 bg-white">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-gray-500 text-sm">
            © {new Date().getFullYear()} Synkora. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-gray-500 hover:text-gray-700 text-sm">Terms</Link>
            <Link href="/privacy" className="text-gray-500 hover:text-gray-700 text-sm">Privacy</Link>
            <Link href="/security" className="text-gray-500 hover:text-gray-700 text-sm">Security</Link>
            <Link href="/contact" className="text-gray-500 hover:text-gray-700 text-sm">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
