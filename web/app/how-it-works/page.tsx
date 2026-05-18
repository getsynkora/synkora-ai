'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
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
    description: 'Build and configure AI agents through an intuitive web interface — or go straight to the API.'
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
    <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 w-full max-w-sm">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-gradient-to-br from-red-100 to-pink-100 rounded-xl flex items-center justify-center">
          <Bot className="w-6 h-6 text-red-500" />
        </div>
        <div>
          <h4 className="font-semibold text-gray-900">New Agent</h4>
          <p className="text-xs text-gray-500">Configure your AI assistant</p>
        </div>
      </div>

      {/* Form Fields */}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-600 mb-1 block">Agent Name</label>
          <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-200">
            <span className="text-gray-800 text-sm">Support Assistant</span>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 mb-1 block">LLM Provider</label>
          <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 flex items-center justify-between">
            <span className="text-gray-800 text-sm">GPT-4o</span>
            <Sparkles className="w-4 h-4 text-purple-500" />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 mb-1 block">Personality</label>
          <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 h-16">
            <span className="text-gray-500 text-sm">Friendly, professional, helpful...</span>
          </div>
        </div>
      </div>

      {/* Create Button */}
      <button className="w-full mt-6 bg-gradient-to-r from-red-500 to-rose-500 text-white font-medium py-2.5 rounded-lg text-sm flex items-center justify-center gap-2">
        <Zap className="w-4 h-4" />
        Create Agent
      </button>
    </div>

    {/* Floating Badge */}
    <div className="absolute top-4 right-4 bg-green-100 text-green-700 text-xs font-medium px-3 py-1 rounded-full flex items-center gap-1">
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
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
            <Database className="w-5 h-5 text-orange-600" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900 text-sm">Knowledge Base</h4>
            <p className="text-xs text-gray-500">3 sources connected</p>
          </div>
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
        </div>
        <div className="flex gap-2">
          <div className="flex-1 bg-gray-50 rounded-lg p-2 flex items-center gap-2">
            <FileText className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-600">docs.pdf</span>
          </div>
          <div className="flex-1 bg-gray-50 rounded-lg p-2 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-600">website</span>
          </div>
        </div>
      </div>

      {/* Tools Card */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
            <Plug className="w-5 h-5 text-purple-600" />
          </div>
          <div className="flex-1">
            <h4 className="font-medium text-gray-900 text-sm">Connected Tools</h4>
            <p className="text-xs text-gray-500">5 integrations active</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {['Slack', 'Jira', 'Gmail', 'Calendar', 'CRM'].map((tool, idx) => (
            <span key={idx} className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-md font-medium">
              {tool}
            </span>
          ))}
        </div>
      </div>

      {/* Upload Card */}
      <div className="bg-gradient-to-br from-orange-50 to-amber-50 rounded-xl border-2 border-dashed border-orange-200 p-4 flex items-center justify-center gap-3">
        <Upload className="w-5 h-5 text-orange-500" />
        <span className="text-sm text-orange-700 font-medium">Drop files to upload</span>
      </div>
    </div>

    {/* Floating Badge */}
    <div className="absolute bottom-4 right-4 bg-purple-100 text-purple-700 text-xs font-medium px-3 py-1 rounded-full">
      50+ Integrations
    </div>
  </div>
)

// Step 3 Illustration - Test & Refine (Chat Interface)
const TestRefineIllustration = () => (
  <div className="relative w-full h-full flex items-center justify-center p-6">
    <div className="bg-white rounded-2xl shadow-xl border border-gray-100 w-full max-w-sm overflow-hidden">
      {/* Chat Header */}
      <div className="bg-gradient-to-r from-blue-500 to-indigo-500 px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
          <MessageSquare className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-white text-sm">Agent Playground</h4>
          <p className="text-xs text-white/70">Testing mode</p>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-green-400 rounded-full" />
          <span className="text-xs text-white/80">Live</span>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="p-4 space-y-3 bg-gray-50 min-h-[180px]">
        {/* User Message */}
        <div className="flex justify-end">
          <div className="bg-blue-500 text-white text-sm px-3 py-2 rounded-xl rounded-br-sm max-w-[80%]">
            How do I reset my password?
          </div>
        </div>

        {/* Bot Response */}
        <div className="flex justify-start">
          <div className="bg-white text-gray-800 text-sm px-3 py-2 rounded-xl rounded-bl-sm max-w-[80%] shadow-sm border border-gray-100">
            I can help you reset your password. Click on &quot;Forgot Password&quot; on the login page...
          </div>
        </div>

        {/* Typing Indicator */}
        <div className="flex justify-start">
          <div className="bg-white px-3 py-2 rounded-xl shadow-sm border border-gray-100 flex items-center gap-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-gray-100 flex items-center gap-2">
        <input
          type="text"
          placeholder="Type a message..."
          className="flex-1 bg-gray-50 rounded-lg px-3 py-2 text-sm border border-gray-200 outline-none"
          readOnly
        />
        <button className="w-9 h-9 bg-blue-500 rounded-lg flex items-center justify-center">
          <Send className="w-4 h-4 text-white" />
        </button>
      </div>
    </div>

    {/* Analytics Floating Card */}
    <div className="absolute -bottom-2 -right-2 bg-white rounded-xl shadow-lg p-3 border border-gray-100">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-green-600" />
        </div>
        <div>
          <div className="text-sm font-bold text-gray-900">98%</div>
          <div className="text-xs text-gray-500">Accuracy</div>
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
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-5 mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-green-100 to-emerald-100 rounded-xl flex items-center justify-center">
            <Rocket className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 text-sm">Deploy Agent</h4>
            <p className="text-xs text-gray-500">Choose your channels</p>
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
              className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all ${
                channel.active
                  ? 'bg-green-50 border-green-200'
                  : 'bg-gray-50 border-gray-100'
              }`}
            >
              <channel.icon className={`w-5 h-5 ${channel.active ? 'text-green-600' : 'text-gray-400'}`} />
              <span className={`text-xs font-medium ${channel.active ? 'text-green-700' : 'text-gray-500'}`}>
                {channel.label}
              </span>
              {channel.active && (
                <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Status Bar */}
      <div className="bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-white rounded-full animate-pulse" />
          <span className="text-white font-medium text-sm">Agent is Live!</span>
        </div>
        <div className="text-white/80 text-xs">4 channels active</div>
      </div>
    </div>

    {/* Floating Badge */}
    <div className="absolute top-4 left-4 bg-blue-100 text-blue-700 text-xs font-medium px-3 py-1 rounded-full">
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
    badge: 'bg-[#ffe8de] text-[#915137]',
    iconWrap: 'bg-[#ffe8de]',
    iconColor: 'text-[#cf673e]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.84),rgba(249,241,233,0.82))]',
    art: 'bg-[linear-gradient(145deg,rgba(255,248,242,0.98),rgba(250,237,228,0.94))]',
    bullet: 'bg-[#cf673e]',
  },
  orange: {
    badge: 'bg-[#fff0d8] text-[#8c5d1d]',
    iconWrap: 'bg-[#fff0d8]',
    iconColor: 'text-[#d58a27]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.84),rgba(250,243,228,0.82))]',
    art: 'bg-[linear-gradient(145deg,rgba(255,251,242,0.98),rgba(248,239,220,0.94))]',
    bullet: 'bg-[#d58a27]',
  },
  blue: {
    badge: 'bg-[#e4f2ef] text-[#2d6c63]',
    iconWrap: 'bg-[#e4f2ef]',
    iconColor: 'text-[#2d8b69]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.84),rgba(234,245,241,0.82))]',
    art: 'bg-[linear-gradient(145deg,rgba(246,252,250,0.98),rgba(231,245,240,0.94))]',
    bullet: 'bg-[#2d8b69]',
  },
  green: {
    badge: 'bg-[#eaf3de] text-[#567436]',
    iconWrap: 'bg-[#eaf3de]',
    iconColor: 'text-[#6f9251]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,255,255,0.84),rgba(238,245,230,0.82))]',
    art: 'bg-[linear-gradient(145deg,rgba(250,253,245,0.98),rgba(236,246,228,0.94))]',
    bullet: 'bg-[#6f9251]',
  },
} as const

const featureAccentClasses = [
  { wrap: 'bg-[#ffe8de]', icon: 'text-[#cf673e]' },
  { wrap: 'bg-[#e4f2ef]', icon: 'text-[#2d8b69]' },
  { wrap: 'bg-[#fff0d8]', icon: 'text-[#d58a27]' },
]

const useCaseAccentClasses = [
  'border-[#cf673e]/20 bg-[linear-gradient(180deg,rgba(46,31,25,0.96),rgba(24,20,18,0.92))] shadow-[0_20px_50px_rgba(0,0,0,0.22)]',
  'border-[#2d8b69]/20 bg-[linear-gradient(180deg,rgba(24,36,33,0.96),rgba(18,22,21,0.92))] shadow-[0_20px_50px_rgba(0,0,0,0.22)]',
  'border-[#d58a27]/20 bg-[linear-gradient(180deg,rgba(44,35,23,0.96),rgba(23,20,18,0.92))] shadow-[0_20px_50px_rgba(0,0,0,0.22)]',
  'border-[#6f9251]/20 bg-[linear-gradient(180deg,rgba(31,38,27,0.96),rgba(19,22,18,0.92))] shadow-[0_20px_50px_rgba(0,0,0,0.22)]',
]

export default function HowItWorksPage() {
  const stepsRef = useRef<HTMLDivElement>(null)
  const featuresRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const stepsEl = stepsRef.current
    const featuresEl = featuresRef.current
    let cancelled = false

    Promise.all([import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ default: gsap }, { ScrollTrigger }]) => {
        if (cancelled) return
        gsap.registerPlugin(ScrollTrigger)

        if (stepsEl) {
          gsap.fromTo(
            stepsEl.querySelectorAll('.step-card'),
            { opacity: 0, y: 40, scale: 0.97 },
            {
              opacity: 1,
              y: 0,
              scale: 1,
              duration: 0.8,
              stagger: 0.16,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: stepsEl,
                start: 'top 70%'
              }
            }
          )
        }

        if (featuresEl) {
          gsap.fromTo(
            featuresEl.querySelectorAll('.feature-card'),
            { opacity: 0, y: 30, scale: 0.96 },
            {
              opacity: 1,
              y: 0,
              scale: 1,
              duration: 0.6,
              stagger: 0.1,
              ease: 'power3.out',
              scrollTrigger: {
                trigger: featuresEl,
                start: 'top 75%'
              }
            }
          )
        }
      }
    )

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-16 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[8%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
          <div className="absolute left-[18%] top-[34%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.16),transparent_72%)]" />
          <div className="absolute right-[18%] bottom-[10%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.08),transparent_72%)]" />
        </div>

        <div className="relative mx-auto max-w-6xl">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur">
              <Play className="h-4 w-4" />
              How It Works
            </div>
            <h1 className="text-4xl font-medium tracking-[-0.06em] text-[#171717] sm:text-6xl">
              Build LLM Applications
              <span className="editorial-highlight ml-3 inline-block">in Minutes</span>
            </h1>
            <p className="mx-auto mt-6 max-w-3xl text-base leading-8 text-[#5a544a] sm:text-xl">
              From agent definition to production deployment - with API access, RAG, tool integrations, and multi-channel delivery.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
              <Link
                href="/signup"
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#191919] px-8 py-4 text-sm font-semibold uppercase tracking-[0.16em] text-[#f7f2e7] shadow-[0_18px_40px_rgba(23,23,23,0.18)] transition-transform hover:-translate-y-0.5 sm:w-auto"
              >
                Start Building
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex w-full items-center justify-center rounded-full border border-black/10 bg-white/68 px-8 py-4 text-sm font-semibold uppercase tracking-[0.16em] text-[#1a1a1a] shadow-[0_12px_28px_rgba(0,0,0,0.04)] transition-colors hover:bg-white sm:w-auto"
              >
                View Pricing
              </Link>
            </div>
          </div>

          <div className="mt-14 grid gap-4 sm:grid-cols-3">
            {[
              { label: 'Create, connect, deploy', value: '4-step flow' },
              { label: 'Tools, data, and channels', value: 'Production stack' },
              { label: 'UI-first with API control', value: 'Built for teams' },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[1.7rem] border border-black/8 bg-white/62 p-5 text-left shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur"
              >
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#7a736a]">
                  {item.label}
                </div>
                <div className="text-2xl font-semibold tracking-[-0.04em] text-[#171717]">
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#f4eee1] px-4 py-16 sm:px-6 sm:py-24" ref={stepsRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Sparkles className="h-4 w-4" />
              Workflow
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-[#171717] mb-4">
              Four Simple Steps
            </h2>
            <p className="text-base sm:text-xl text-[#5d564c]">From zero to deployed agent in record time</p>
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
                  <div className={`flex-1 rounded-[2rem] border border-black/8 p-5 shadow-[0_22px_52px_rgba(0,0,0,0.06)] backdrop-blur sm:p-8 ${theme.panel}`}>
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
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${theme.badge}`}>
                            Step {step.number}
                          </span>
                          <h3 className="text-lg sm:text-2xl font-semibold tracking-[-0.04em] text-[#171717]">{step.title}</h3>
                        </div>
                        <p className="mb-4 text-sm text-[#5f594f] sm:mb-6 sm:text-lg">{step.description}</p>
                        <ul className="space-y-2">
                          {step.features.map((feature, idx) => (
                            <li key={idx} className="flex items-center gap-2 text-sm text-[#39352f] sm:text-base">
                              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${theme.bullet}`} />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Illustration */}
                  <div className={`flex-1 rounded-[2rem] min-h-[280px] sm:min-h-[350px] relative overflow-hidden border border-black/8 shadow-[0_22px_52px_rgba(0,0,0,0.05)] ${theme.art}`}>
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.72),transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.18),rgba(255,255,255,0))]" />
                    {IllustrationComponent && <IllustrationComponent />}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="py-16 sm:py-24 px-4 sm:px-6 bg-[#f7f2e7]" ref={featuresRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Zap className="h-4 w-4" />
              Capabilities
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-[#171717] mb-4">Powerful Features</h2>
            <p className="text-base sm:text-xl text-[#5d564c]">Everything you need to build production-ready AI agents</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {features.map((feature, idx) => (
              <div
                key={idx}
                className="feature-card rounded-[1.8rem] border border-black/8 bg-white/72 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur transition-transform hover:-translate-y-1"
              >
                <div className={`w-12 h-12 rounded-[1rem] flex items-center justify-center mb-4 ${featureAccentClasses[idx % featureAccentClasses.length].wrap}`}>
                  <feature.icon className={`w-6 h-6 ${featureAccentClasses[idx % featureAccentClasses.length].icon}`} />
                </div>
                <h3 className="text-lg font-semibold tracking-[-0.03em] text-[#171717] mb-2">{feature.title}</h3>
                <p className="text-[#5f594f]">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-[#171717] px-4 py-16 sm:px-6 sm:py-24">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[10%] top-[10%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.08),transparent_72%)]" />
          <div className="absolute right-[12%] bottom-[14%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,143,178,0.08),transparent_72%)]" />
          <div className="absolute left-1/2 top-[22%] h-[420px] w-[420px] -translate-x-1/2 rounded-full border border-white/[0.04]" />
        </div>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#d1c7bb]">
              <MessageCircle className="h-4 w-4 text-[#7de5c1]" />
              Use Cases
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-white mb-4">Built for Every Use Case</h2>
            <p className="text-base sm:text-xl text-[#c6bfb3]">See what you can build with Synkora</p>
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
                className={`relative overflow-hidden rounded-[1.7rem] border p-6 text-center backdrop-blur transition-transform hover:-translate-y-1 ${useCaseAccentClasses[idx]}`}
              >
                <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/22 to-transparent" />
                <div className="mx-auto mb-4 h-2 w-14 rounded-full bg-white/18" />
                <h3 className="font-semibold text-white mb-2 tracking-[-0.03em]">{useCase.title}</h3>
                <p className="text-[#d0c7bb] text-sm leading-6">{useCase.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#f7f2e7] px-4 py-16 sm:px-6 sm:py-24">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-10 shadow-[0_34px_90px_rgba(0,0,0,0.2)] md:p-14">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#d7d0c5]">
                <Send className="h-4 w-4 text-[#7de5c1]" />
                Start shipping
              </div>
              <h2 className="text-2xl sm:text-4xl font-medium tracking-[-0.05em] text-white mb-4 sm:mb-6">
            Ready to Build Your First Agent?
              </h2>
              <p className="text-base sm:text-xl text-white/90 mb-8 sm:mb-10">
            Join thousands of teams already using Synkora to automate their workflows.
              </p>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 text-base font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
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
