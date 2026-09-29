import Link from 'next/link'
import { Zap, ArrowRight, Users, Code, BarChart3, HeadphonesIcon, PenTool, Database, Briefcase, Shield } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Use Cases – Synkora Enterprise AI Platform',
  description: 'Enterprise AI agents for every team — product, engineering, support, marketing, data, and HR. SAML SSO, RBAC, audit logs, and self-hosting included. API-first, multitenant.',
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
    <PublicPageFrame mainClassName="pt-28">

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[8%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[10%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
        </div>
        <div className="relative max-w-4xl mx-auto text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur">
            <Users className="w-4 h-4" />
            Use Cases
          </div>
          <h1 className="text-4xl font-medium tracking-[-0.06em] text-[#171717] sm:text-6xl">
            Enterprise AI agents
            <span className="mt-3 block text-[#2d8b69]">for every team</span>
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-base leading-8 text-[#5a544a] sm:text-xl">
            Deploy auditable AI agents across product, engineering, support, and ops — with SAML SSO, RBAC, and your own LLM keys. Built for teams that need production-grade control.
          </p>
        </div>
      </section>

      {/* Use Cases Grid */}
      <section className="bg-[#f4eee1] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="space-y-10">
            {useCases.map((useCase, index) => {
              const isEven = index % 2 === 0

              return (
                <div key={useCase.id} id={useCase.id} className="scroll-mt-24">
                  <div className={`grid lg:grid-cols-2 gap-8 items-stretch ${!isEven ? '' : ''}`}>
                    {/* Content */}
                    <div className={`rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur ${!isEven ? 'lg:order-2' : ''}`}>
                      <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-[#e4f2ef] px-3 py-1.5 text-sm font-semibold text-[#2d8b69] mb-4">
                        <useCase.icon className="w-4 h-4" />
                        {useCase.subtitle}
                      </div>
                      <h2 className="text-2xl font-semibold tracking-[-0.04em] text-[#171717] mb-3">{useCase.title}</h2>
                      <p className="text-[#5f594f] mb-6 leading-7">{useCase.description}</p>

                      {/* Capabilities */}
                      <div className="mb-6">
                        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7a736a] mb-3">Capabilities</h3>
                        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {useCase.capabilities.map((cap, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-[#39352f]">
                              <svg className="w-5 h-5 text-[#2d8b69] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              {cap}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Integrations */}
                      <div className="mb-6">
                        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[#7a736a] mb-3">Integrations</h3>
                        <div className="flex flex-wrap gap-2">
                          {useCase.integrations.map((int, i) => (
                            <span key={i} className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-sm text-[#4b463e]">
                              {int}
                            </span>
                          ))}
                        </div>
                      </div>

                      <Link
                        href="/signup"
                        className="inline-flex items-center gap-2 rounded-full bg-[#191919] px-6 py-3 text-sm font-semibold text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
                      >
                        Deploy this agent
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>

                    {/* Example Card */}
                    <div className={`rounded-[2rem] border border-black/8 bg-white/60 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur ${!isEven ? 'lg:order-1' : ''}`}>
                      <div className="flex h-14 w-14 items-center justify-center rounded-[1.1rem] bg-[#e4f2ef] mb-6">
                        <useCase.icon className="w-7 h-7 text-[#2d8b69]" />
                      </div>
                      <h3 className="text-base font-semibold uppercase tracking-[0.1em] text-[#4b463e] mb-3">Example in Action</h3>
                      <p className="text-[#5f594f] leading-7">{useCase.example}</p>

                      <div className="mt-6 pt-6 border-t border-black/8">
                        <div className="flex items-center gap-4">
                          <div className="flex -space-x-2">
                            {[...Array(3)].map((_, i) => (
                              <div key={i} className="w-8 h-8 rounded-full bg-[#e4f2ef] border-2 border-white flex items-center justify-center">
                                <span className="text-xs font-semibold text-[#2d8b69]">{['PM', 'ENG', 'MKT'][i]}</span>
                              </div>
                            ))}
                          </div>
                          <span className="text-sm text-[#7a736a]">Teams using this agent</span>
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
      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-medium tracking-[-0.05em] text-[#171717] sm:text-4xl mb-4">Why enterprises choose Synkora</h2>
            <p className="text-lg text-[#5d564c]">Production-grade controls, not an afterthought</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur text-center">
              <div className="w-14 h-14 bg-[#e4f2ef] rounded-[1.1rem] flex items-center justify-center mx-auto mb-4">
                <Shield className="w-7 h-7 text-[#2d8b69]" />
              </div>
              <h3 className="text-xl font-semibold tracking-[-0.03em] text-[#171717] mb-2">SAML / OIDC SSO</h3>
              <p className="text-[#5f594f] leading-7">Integrate with Okta, Azure AD, Google Workspace, and any SAML 2.0 or OIDC provider. JIT provisioning included.</p>
            </div>
            <div className="rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur text-center">
              <div className="w-14 h-14 bg-[#e4f2ef] rounded-[1.1rem] flex items-center justify-center mx-auto mb-4">
                <Code className="w-7 h-7 text-[#2d8b69]" />
              </div>
              <h3 className="text-xl font-semibold tracking-[-0.03em] text-[#171717] mb-2">Open Source · MIT</h3>
              <p className="text-[#5f594f] leading-7">Full source code. Self-host on your infrastructure for complete data ownership. No usage fees, no vendor lock-in.</p>
            </div>
            <div className="rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur text-center">
              <div className="w-14 h-14 bg-[#e4f2ef] rounded-[1.1rem] flex items-center justify-center mx-auto mb-4">
                <Database className="w-7 h-7 text-[#2d8b69]" />
              </div>
              <h3 className="text-xl font-semibold tracking-[-0.03em] text-[#171717] mb-2">RBAC + Audit Logs</h3>
              <p className="text-[#5f594f] leading-7">Granular role-based access control with SHA-256 chain-hashed audit trails. Export to CSV or JSON for your SIEM.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-[#f7f2e7] px-4 pb-14 sm:px-6 sm:pb-20">
        <div className="max-w-4xl mx-auto">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-10 text-center shadow-[0_34px_90px_rgba(0,0,0,0.2)] md:p-14">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-white mb-4">Ready to deploy enterprise AI?</h2>
              <p className="text-lg text-white/85 mb-8 max-w-xl mx-auto leading-8">
                Self-host free with full enterprise features, or start on cloud. SAML SSO, RBAC, audit logs — MIT licensed.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
                >
                  <Zap className="w-5 h-5" />
                  Get Started Free
                </Link>
                <a
                  href="mailto:enterprise@synkora.ai"
                  className="inline-flex items-center gap-2 rounded-full border border-white/16 bg-white/6 px-8 py-4 font-semibold text-white transition-colors hover:bg-white/10"
                >
                  Talk to Sales
                  <ArrowRight className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

    </PublicPageFrame>
  )
}
