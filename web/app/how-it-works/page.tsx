'use client'

import Link from 'next/link'
import { useRef } from 'react'
import PublicPageFrame from '@/components/public/PublicPageFrame'
import {
  Zap,
  Bot,
  Wrench,
  Rocket,
  MessageSquare,
  Database,
  Globe,
  ArrowRight,
  Play,
  Code2,
  Blocks,
  BarChart3,
  Upload,
  Link2,
  Sparkles,
  Send,
  CheckCircle2,
  FileText,
  Plug,
  Hash,
  MessageCircle,
  Chrome,
  Smartphone
} from 'lucide-react'

const steps = [
  {
    number: '01',
    title: 'Create Your Agent',
    description: 'Start by creating an AI agent with our intuitive interface. Define its personality, capabilities, and behavior with simple configurations.',
    icon: Bot,
    color: 'red',
    features: ['Choose from multiple LLM providers', 'Customize agent personality', 'Set response guidelines']
  },
  {
    number: '02',
    title: 'Add Knowledge & Tools',
    description: 'Enhance your agent with custom knowledge bases and powerful integrations. Connect to your data sources and enable actions.',
    icon: Wrench,
    color: 'orange',
    features: ['Upload documents & URLs', 'Connect APIs & databases', 'Enable 50+ integrations']
  },
  {
    number: '03',
    title: 'Test & Refine',
    description: 'Use our built-in playground to test your agent. Iterate quickly with real-time feedback and conversation analytics.',
    icon: MessageSquare,
    color: 'blue',
    features: ['Interactive playground', 'Conversation history', 'Performance analytics']
  },
  {
    number: '04',
    title: 'Deploy Everywhere',
    description: 'Deploy your agent with one click. Embed on websites, connect to Slack, Discord, or access via API.',
    icon: Rocket,
    color: 'green',
    features: ['Web widget embed', 'Slack & Discord bots', 'REST API access']
  }
]

const features = [
  {
    icon: Code2,
    title: 'Visual Builder',
    description: 'Build and configure AI agents through an intuitive web interface, or go straight to the API.'
  },
  {
    icon: Blocks,
    title: 'Modular Architecture',
    description: 'Mix and match components to create exactly what you need. Tools, knowledge, and integrations work together seamlessly.'
  },
  {
    icon: Database,
    title: 'Knowledge Bases',
    description: 'Upload documents, websites, or connect databases. Your agent learns from your data instantly.'
  },
  {
    icon: Globe,
    title: 'Multi-Channel Deploy',
    description: 'One agent, everywhere. Deploy to web, mobile, Slack, Discord, Telegram, and more.'
  },
  {
    icon: BarChart3,
    title: 'Analytics & Insights',
    description: 'Track conversations, measure satisfaction, and optimize performance with detailed analytics.'
  },
  {
    icon: Zap,
    title: 'Lightning Fast',
    description: 'Optimized for speed with streaming responses and intelligent caching for instant interactions.'
  }
]

// Step 1 Illustration - Create Agent UI
const CreateAgentIllustration = () => (
  <div className="relative w-full h-full flex items-center justify-center p-6">
    {/* Main Card */}
    <div className="bg-white rounded-2xl shadow-xl border border-sand p-6 w-full max-w-sm">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-blush-wash rounded-xl flex items-center justify-center">
          <Bot className="w-6 h-6 text-leaf" />
        </div>
        <div>
          <h4 className="font-semibold text-ink">New Agent</h4>
          <p className="text-xs text-ink-mute">Configure your AI assistant</p>
        </div>
      </div>

      {/* Form Fields */}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-ink-soft mb-1 block">Agent Name</label>
          <div className="bg-cream rounded-lg px-3 py-2 border border-line">
            <span className="text-ink text-sm">Support Assistant</span>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-ink-soft mb-1 block">LLM Provider</label>
          <div className="bg-cream rounded-lg px-3 py-2 border border-line flex items-center justify-between">
            <span className="text-ink text-sm">GPT-4o</span>
            <Sparkles className="w-4 h-4 text-plum" />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-ink-soft mb-1 block">Personality</label>
          <div className="bg-cream rounded-lg px-3 py-2 border border-line h-16">
            <span className="text-ink-mute text-sm">Friendly, professional, helpful…</span>
          </div>
        </div>
      </div>

      {/* Create Button */}
      <button className="w-full mt-6 bg-ink text-white font-medium py-2.5 rounded-lg text-sm flex items-center justify-center gap-2">
        <Zap className="w-4 h-4" />
        Create Agent
      </button>
    </div>

    {/* Floating Badge */}
    <div className="absolute top-4 right-4 bg-leaf-wash text-forest text-xs font-medium px-3 py-1 rounded-full flex items-center gap-1">
      <CheckCircle2 className="w-3 h-3" />
      No Code
    </div>
  </div>
)

// Step 2 Illustration - Knowledge & Tools
const KnowledgeToolsIllustration = () => (
  <div className="relative w-full h-full flex items-center justify-center p-6">
    <div className="space-y-4 w-full max-w-sm">
      {/* Knowledge Base Card */}
      <div className="bg-white rounded-xl shadow-lg border border-sand p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-sand-deep rounded-lg flex items-center justify-center">
            <Database className="w-5 h-5 text-warn" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-ink text-sm">Knowledge Base</h4>
            <p className="text-xs text-ink-mute">3 sources connected</p>
          </div>
          <div className="w-2 h-2 bg-mint rounded-full" />
        </div>
        <div className="flex gap-2">
          <div className="flex-1 bg-cream rounded-lg p-2 flex items-center gap-2">
            <FileText className="w-4 h-4 text-ash" />
            <span className="text-xs text-ink-soft">docs.pdf</span>
          </div>
          <div className="flex-1 bg-cream rounded-lg p-2 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-ash" />
            <span className="text-xs text-ink-soft">website</span>
          </div>
        </div>
      </div>

      {/* Tools Card */}
      <div className="bg-white rounded-xl shadow-lg border border-sand p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-sand-deep rounded-lg flex items-center justify-center">
            <Plug className="w-5 h-5 text-plum" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-ink text-sm">Connected Tools</h4>
            <p className="text-xs text-ink-mute">5 integrations active</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {['Slack', 'Jira', 'Gmail', 'Calendar', 'CRM'].map((tool, idx) => (
            <span key={idx} className="bg-sand text-ink-soft text-xs px-2 py-1 rounded-md font-medium">
              {tool}
            </span>
          ))}
        </div>
      </div>

      {/* Upload Card */}
      <div className="bg-sand-deep rounded-xl border-2 border-dashed border-honey p-4 flex items-center justify-center gap-3">
        <Upload className="w-5 h-5 text-warn" />
        <span className="text-sm text-gold font-medium">Drop files to upload</span>
      </div>
    </div>

    {/* Floating Badge */}
    <div className="absolute bottom-4 right-4 bg-sand-deep text-ink-soft text-xs font-medium px-3 py-1 rounded-full">
      50+ Integrations
    </div>
  </div>
)

// Step 3 Illustration - Test & Refine (Chat Interface)
const TestRefineIllustration = () => (
  <div className="relative w-full h-full flex items-center justify-center p-6">
    <div className="bg-white rounded-2xl shadow-xl border border-sand w-full max-w-sm overflow-hidden">
      {/* Chat Header */}
      <div className="bg-azure px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
          <MessageSquare className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-white text-sm">Agent Playground</h4>
          <p className="text-xs text-white/70">Testing mode</p>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-mint rounded-full" />
          <span className="text-xs text-white/80">Live</span>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="p-4 space-y-3 bg-cream min-h-[180px]">
        {/* User Message */}
        <div className="flex justify-end">
          <div className="bg-azure text-white text-sm px-3 py-2 rounded-xl rounded-br-sm max-w-[80%]">
            How do I reset my password?
          </div>
        </div>

        {/* Bot Response */}
        <div className="flex justify-start">
          <div className="bg-white text-ink text-sm px-3 py-2 rounded-xl rounded-bl-sm max-w-[80%] shadow-sm border border-sand">
            I can help you reset your password. Click on &quot;Forgot Password&quot; on the login page...
          </div>
        </div>

        {/* Typing Indicator */}
        <div className="flex justify-start">
          <div className="bg-white px-3 py-2 rounded-xl shadow-sm border border-sand flex items-center gap-1">
            <div className="w-2 h-2 bg-ash rounded-full motion-safe:animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-ash rounded-full motion-safe:animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-ash rounded-full motion-safe:animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-sand flex items-center gap-2">
        <input
          type="text"
          placeholder="Type a message…"
          className="flex-1 bg-cream rounded-lg px-3 py-2 text-sm border border-line outline-none"
          readOnly
        />
        <button className="w-9 h-9 bg-azure rounded-lg flex items-center justify-center">
          <Send className="w-4 h-4 text-white" />
        </button>
      </div>
    </div>

    {/* Analytics Floating Card */}
    <div className="absolute -bottom-2 -right-2 bg-white rounded-xl shadow-lg p-3 border border-sand">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 bg-leaf-wash rounded-lg flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-leaf" />
        </div>
        <div>
          <div className="text-sm font-bold text-ink">98%</div>
          <div className="text-xs text-ink-mute">Accuracy</div>
        </div>
      </div>
    </div>
  </div>
)

// Step 4 Illustration - Deploy Everywhere
const DeployIllustration = () => (
  <div className="relative w-full h-full flex items-center justify-center p-6">
    <div className="w-full max-w-sm">
      {/* Main Deploy Card */}
      <div className="bg-white rounded-2xl shadow-xl border border-sand p-5 mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-leaf-wash rounded-xl flex items-center justify-center">
            <Rocket className="w-5 h-5 text-leaf" />
          </div>
          <div>
            <h4 className="font-semibold text-ink text-sm">Deploy Agent</h4>
            <p className="text-xs text-ink-mute">Choose your channels</p>
          </div>
        </div>

        {/* Channel Grid */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: Chrome, label: 'Website', active: true },
            { icon: Hash, label: 'Slack', active: true },
            { icon: MessageCircle, label: 'Discord', active: false },
            { icon: Smartphone, label: 'Mobile', active: true },
            { icon: Code2, label: 'API', active: true },
            { icon: Globe, label: 'Embed', active: false },
          ].map((channel, idx) => (
            <div
              key={idx}
              className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                channel.active
                  ? 'bg-leaf-wash border-mint'
                  : 'bg-cream border-sand'
              }`}
            >
              <channel.icon className={`w-5 h-5 ${channel.active ? 'text-leaf' : 'text-ash'}`} />
              <span className={`text-xs font-medium ${channel.active ? 'text-forest' : 'text-ink-mute'}`}>
                {channel.label}
              </span>
              {channel.active && (
                <div className="w-1.5 h-1.5 bg-leaf rounded-full" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Status Bar */}
      <div className="bg-leaf rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-white rounded-full" />
          <span className="text-white font-medium text-sm">Agent is Live!</span>
        </div>
        <div className="text-white/80 text-xs">4 channels active</div>
      </div>
    </div>

    {/* Floating Badge */}
    <div className="absolute top-4 left-4 bg-sky-wash text-azure text-xs font-medium px-3 py-1 rounded-full">
      One-Click Deploy
    </div>
  </div>
)

// Map step numbers to illustrations
const stepIllustrations: { [key: string]: React.FC } = {
  '01': CreateAgentIllustration,
  '02': KnowledgeToolsIllustration,
  '03': TestRefineIllustration,
  '04': DeployIllustration,
}

const stepThemes = {
  red: {
    badge: 'bg-sand-deep text-bark',
    iconWrap: 'bg-sand-deep',
    iconColor: 'text-rust',
    panel: ' bg-white',
    art: ' bg-cream',
    bullet: 'bg-rust',
  },
  orange: {
    badge: 'bg-sand-deep text-gold',
    iconWrap: 'bg-sand-deep',
    iconColor: 'text-warn',
    panel: ' bg-white',
    art: ' bg-cream',
    bullet: 'bg-warn',
  },
  blue: {
    badge: 'bg-leaf-wash text-forest',
    iconWrap: 'bg-leaf-wash',
    iconColor: 'text-leaf',
    panel: ' bg-white',
    art: ' bg-white',
    bullet: 'bg-leaf',
  },
  green: {
    badge: 'bg-sand text-forest',
    iconWrap: 'bg-sand',
    iconColor: 'text-leaf',
    panel: ' bg-white',
    art: ' bg-cream',
    bullet: 'bg-leaf',
  },
} as const

const featureAccentClasses = [
  { wrap: 'bg-sand-deep', icon: 'text-rust' },
  { wrap: 'bg-leaf-wash', icon: 'text-leaf' },
  { wrap: 'bg-sand-deep', icon: 'text-warn' },
]

const useCaseAccentClasses = [
  'border-rust/20 bg-white shadow-soft',
  'border-leaf/20 bg-white shadow-soft',
  'border-warn/20 bg-white shadow-soft',
  'border-leaf/20 bg-white shadow-soft',
]

export default function HowItWorksPage() {
  const stepsRef = useRef<HTMLDivElement>(null)
  const featuresRef = useRef<HTMLDivElement>(null)

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-paper px-4 pb-16 pt-28 sm:px-6 sm:pb-20 sm:pt-32">

        <div className="relative mx-auto max-w-6xl">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-4xl font-medium tracking-[-0.06em] text-ink sm:text-6xl">
              Deploy Enterprise AI
              <span className="mt-3 block text-leaf sm:inline sm:ml-3">in Minutes</span>
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-base leading-8 text-ink-soft sm:text-xl">
              From agent definition to production deployment, with SSO, RBAC, audit logs, RAG, tool integrations, and multi-channel delivery all included.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
              <Link
                href="/signup"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-ink px-8 py-4 text-sm font-semibold text-paper shadow-soft transition-transform motion-reduce:transition-none hover:-translate-y-0.5 sm:w-auto"
              >
                Start Building
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex w-full items-center justify-center rounded-full border border-black/10 bg-white/68 px-8 py-4 text-sm font-semibold text-ink shadow-soft transition-colors hover:bg-white sm:w-auto"
              >
                View Pricing
              </Link>
            </div>
          </div>

          <div className="mt-14 grid gap-4 sm:grid-cols-3">
            {[
              { label: 'SAML / OIDC SSO + RBAC', value: 'Enterprise auth' },
              { label: 'Tools, data, and channels', value: 'Production stack' },
              { label: 'Audit logs + IP allowlist', value: 'Full control' },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[1.7rem] border border-black/8 bg-white/62 p-5 text-left shadow-soft"
              >
                <div className="mb-2 text-xs font-semibold text-ink-mute">
                  {item.label}
                </div>
                <div className="text-2xl font-semibold tracking-[-0.04em] text-ink">
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-sand px-4 py-16 sm:px-6 sm:py-24" ref={stepsRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-4">
              Four Simple Steps
            </h2>
            <p className="text-base sm:text-xl text-ink-soft">From zero to deployed agent in record time</p>
          </div>

          <div className="space-y-6 sm:space-y-8">
            {steps.map((step, index) => {
              const IllustrationComponent = stepIllustrations[step.number]
              const theme = stepThemes[step.color as keyof typeof stepThemes]
              return (
                <div
                  key={step.number}
                  className={`step-card flex flex-col lg:flex-row items-stretch gap-5 sm:gap-8 ${
                    index % 2 === 1 ? 'lg:flex-row-reverse' : ''
                  }`}
                >
                  {/* Content */}
                  <div className={`flex-1 rounded-[2rem] border border-black/8 p-5 shadow-soft sm:p-8 ${theme.panel}`}>
                    <div className="flex items-start gap-4 sm:gap-6">
                      <div
                        className={`w-12 h-12 sm:w-16 sm:h-16 rounded-[1.25rem] flex items-center justify-center flex-shrink-0 ${theme.iconWrap}`}
                      >
                        <step.icon
                          className={`w-6 h-6 sm:w-8 sm:h-8 ${theme.iconColor}`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="mb-3 flex flex-wrap items-center gap-2 sm:gap-3">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${theme.badge}`}>
                            Step {step.number}
                          </span>
                          <h3 className="text-lg sm:text-2xl font-semibold tracking-[-0.04em] text-ink">{step.title}</h3>
                        </div>
                        <p className="mb-4 text-sm text-ink-soft sm:mb-6 sm:text-lg">{step.description}</p>
                        <ul className="space-y-2">
                          {step.features.map((feature, idx) => (
                            <li key={idx} className="flex items-center gap-2 text-sm text-night sm:text-base">
                              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${theme.bullet}`} />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Illustration */}
                  <div className={`flex-1 rounded-[2rem] min-h-[280px] sm:min-h-[350px] relative overflow-hidden border border-black/8 shadow-soft ${theme.art}`}>
                    <div className="absolute inset-0" />
                    {IllustrationComponent && <IllustrationComponent />}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="py-16 sm:py-24 px-4 sm:px-6 bg-paper" ref={featuresRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-4">Powerful Features</h2>
            <p className="text-base sm:text-xl text-ink-soft">Everything you need to build production-ready AI agents</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {features.map((feature, idx) => (
              <div
                key={idx}
                className="feature-card rounded-[1.8rem] border border-black/8 bg-white/72 p-6 shadow-soft transition-transform motion-reduce:transition-none hover:-translate-y-1"
              >
                <div className={`w-12 h-12 rounded-[1rem] flex items-center justify-center mb-4 ${featureAccentClasses[idx % featureAccentClasses.length].wrap}`}>
                  <feature.icon className={`w-6 h-6 ${featureAccentClasses[idx % featureAccentClasses.length].icon}`} />
                </div>
                <h3 className="text-lg font-semibold tracking-[-0.03em] text-ink mb-2">{feature.title}</h3>
                <p className="text-ink-soft">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-sand px-4 py-16 sm:px-6 sm:py-24">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-1/2 top-[22%] h-[420px] w-[420px] -translate-x-1/2 rounded-full border border-white/[0.04]" />
        </div>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-4">Built for Every Use Case</h2>
            <p className="text-base sm:text-xl text-ink-soft">See what you can build with Synkora</p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            {[
              { title: 'Customer Support', desc: '24/7 intelligent support agents' },
              { title: 'Sales Assistant', desc: 'Qualify leads and book meetings' },
              { title: 'Internal Knowledge', desc: 'Company wiki that answers back' },
              { title: 'Product Onboarding', desc: 'Guide users through your app' }
            ].map((useCase, idx) => (
              <div
                key={idx}
                className={`relative overflow-hidden rounded-[1.7rem] border p-6 text-center transition-transform motion-reduce:transition-none hover:-translate-y-1 ${useCaseAccentClasses[idx]}`}
              >
                <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/22 to-transparent" />
                <div className="mx-auto mb-4 h-2 w-14 rounded-full bg-white" />
                <h3 className="font-semibold text-ink mb-2 tracking-[-0.03em]">{useCase.title}</h3>
                <p className="text-ink-soft text-sm leading-6">{useCase.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-paper px-4 py-16 sm:px-6 sm:py-24">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-ink p-10 shadow-soft md:p-14">
            <div className="absolute inset-0" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
              <h2 className="text-2xl sm:text-4xl font-medium tracking-[-0.05em] text-white mb-4 sm:mb-6">
                Ready to build enterprise AI?
              </h2>
              <p className="text-base sm:text-xl text-white/90 mb-8 sm:mb-10">
                Self-host with full enterprise security, or start on cloud. SAML SSO, RBAC, audit logs, and your own LLM keys, MIT licensed.
              </p>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-mint px-8 py-4 text-base font-semibold text-ink transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
              >
                Get Started Free
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
