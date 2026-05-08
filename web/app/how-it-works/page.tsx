'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
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
  Settings,
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

gsap.registerPlugin(ScrollTrigger)

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

export default function HowItWorksPage() {
  const stepsRef = useRef<HTMLDivElement>(null)
  const featuresRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Animate steps on scroll
    if (stepsRef.current) {
      gsap.fromTo(
        stepsRef.current.querySelectorAll('.step-card'),
        { opacity: 0, x: -50 },
        {
          opacity: 1,
          x: 0,
          duration: 0.8,
          stagger: 0.2,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: stepsRef.current,
            start: 'top 70%'
          }
        }
      )
    }

    // Animate features
    if (featuresRef.current) {
      gsap.fromTo(
        featuresRef.current.querySelectorAll('.feature-card'),
        { opacity: 0, y: 30 },
        {
          opacity: 1,
          y: 0,
          duration: 0.6,
          stagger: 0.1,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: featuresRef.current,
            start: 'top 75%'
          }
        }
      )
    }

    return () => {
      ScrollTrigger.getAll().forEach(trigger => trigger.kill())
    }
  }, [])

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-lg border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 sm:gap-3">
              <div className="w-9 h-9 sm:w-10 sm:h-10 bg-red-500 rounded-xl flex items-center justify-center">
                <Zap className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
              </div>
              <span className="text-xl sm:text-2xl font-bold text-gray-900">Synkora</span>
            </Link>
            <div className="flex items-center gap-2 sm:gap-4">
              <Link href="/" className="hidden sm:block text-gray-600 hover:text-gray-900 font-medium">
                Home
              </Link>
              <Link href="/pricing" className="hidden sm:block text-gray-600 hover:text-gray-900 font-medium">
                Pricing
              </Link>
              <Link
                href="/signup"
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-medium rounded-lg transition-colors text-sm sm:text-base"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 sm:pt-32 pb-16 sm:pb-20 px-4 sm:px-6 bg-gradient-to-b from-red-50 to-white">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-full text-sm font-semibold mb-6">
            <Play className="w-4 h-4" />
            How It Works
          </div>
          <h1 className="text-3xl sm:text-5xl font-bold text-gray-900 mb-6">
            Build LLM Applications
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-rose-600"> in Minutes</span>
          </h1>
          <p className="text-base sm:text-xl text-gray-600 mb-8 sm:mb-10 max-w-2xl mx-auto">
            From agent definition to production deployment — with API access, RAG, tool integrations, and multi-channel delivery.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-6 sm:px-8 py-3 sm:py-4 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl transition-all shadow-lg shadow-red-500/30 w-full sm:w-auto justify-center"
            >
              Start Building
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/pricing"
              className="px-6 sm:px-8 py-3 sm:py-4 border-2 border-gray-200 hover:border-gray-300 text-gray-700 font-semibold rounded-xl transition-all w-full sm:w-auto text-center"
            >
              View Pricing
            </Link>
          </div>
        </div>
      </section>

      {/* Steps Section */}
      <section className="py-16 sm:py-24 px-4 sm:px-6" ref={stepsRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-2xl sm:text-4xl font-bold text-gray-900 mb-4">Four Simple Steps</h2>
            <p className="text-base sm:text-xl text-gray-600">From zero to deployed agent in record time</p>
          </div>

          <div className="space-y-6 sm:space-y-8">
            {steps.map((step, index) => {
              const IllustrationComponent = stepIllustrations[step.number]
              return (
                <div
                  key={step.number}
                  className={`step-card flex flex-col lg:flex-row items-stretch gap-5 sm:gap-8 ${
                    index % 2 === 1 ? 'lg:flex-row-reverse' : ''
                  }`}
                >
                  {/* Content */}
                  <div className="flex-1 bg-white rounded-2xl p-5 sm:p-8 border border-gray-100 shadow-lg hover:shadow-xl transition-shadow">
                    <div className="flex items-start gap-4 sm:gap-6">
                      <div
                        className={`w-12 h-12 sm:w-16 sm:h-16 rounded-2xl flex items-center justify-center flex-shrink-0 ${
                          step.color === 'red' ? 'bg-red-100' :
                          step.color === 'orange' ? 'bg-orange-100' :
                          step.color === 'blue' ? 'bg-blue-100' : 'bg-green-100'
                        }`}
                      >
                        <step.icon
                          className={`w-6 h-6 sm:w-8 sm:h-8 ${
                            step.color === 'red' ? 'text-red-600' :
                            step.color === 'orange' ? 'text-orange-600' :
                            step.color === 'blue' ? 'text-blue-600' : 'text-green-600'
                          }`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 sm:gap-3 mb-3">
                          <span className="text-3xl sm:text-5xl font-bold text-gray-200">{step.number}</span>
                          <h3 className="text-lg sm:text-2xl font-bold text-gray-900">{step.title}</h3>
                        </div>
                        <p className="text-gray-600 mb-4 sm:mb-6 text-sm sm:text-lg">{step.description}</p>
                        <ul className="space-y-2">
                          {step.features.map((feature, idx) => (
                            <li key={idx} className="flex items-center gap-2 text-gray-700 text-sm sm:text-base">
                              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                step.color === 'red' ? 'bg-red-500' :
                                step.color === 'orange' ? 'bg-orange-500' :
                                step.color === 'blue' ? 'bg-blue-500' : 'bg-green-500'
                              }`} />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Illustration */}
                  <div className={`flex-1 rounded-2xl min-h-[280px] sm:min-h-[350px] relative overflow-hidden ${
                    step.color === 'red' ? 'bg-gradient-to-br from-red-50 via-pink-50 to-rose-50' :
                    step.color === 'orange' ? 'bg-gradient-to-br from-orange-50 via-amber-50 to-yellow-50' :
                    step.color === 'blue' ? 'bg-gradient-to-br from-blue-50 via-indigo-50 to-violet-50' :
                    'bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50'
                  }`}>
                    {IllustrationComponent && <IllustrationComponent />}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 sm:py-24 px-4 sm:px-6 bg-gray-50" ref={featuresRef}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-2xl sm:text-4xl font-bold text-gray-900 mb-4">Powerful Features</h2>
            <p className="text-base sm:text-xl text-gray-600">Everything you need to build production-ready AI agents</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {features.map((feature, idx) => (
              <div
                key={idx}
                className="feature-card bg-white rounded-xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center mb-4">
                  <feature.icon className="w-6 h-6 text-red-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-16 sm:py-24 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 sm:mb-16">
            <h2 className="text-2xl sm:text-4xl font-bold text-gray-900 mb-4">Built for Every Use Case</h2>
            <p className="text-base sm:text-xl text-gray-600">See what you can build with Synkora</p>
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
                className="text-center p-6 bg-gradient-to-br from-gray-50 to-white rounded-xl border border-gray-100"
              >
                <h3 className="font-semibold text-gray-900 mb-2">{useCase.title}</h3>
                <p className="text-gray-600 text-sm">{useCase.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 sm:py-24 px-4 sm:px-6 bg-gradient-to-br from-red-500 to-rose-600">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-2xl sm:text-4xl font-bold text-white mb-4 sm:mb-6">
            Ready to Build Your First Agent?
          </h2>
          <p className="text-base sm:text-xl text-white/90 mb-8 sm:mb-10">
            Join thousands of teams already using Synkora to automate their workflows.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-8 sm:px-10 py-4 sm:py-5 bg-white hover:bg-gray-50 text-red-600 text-base sm:text-lg font-semibold rounded-xl transition-all shadow-xl"
          >
            Get Started Free
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-red-500 rounded-lg flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-gray-600">© 2026 Synkora. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-gray-600 hover:text-gray-900 text-sm">
              Terms
            </Link>
            <Link href="/privacy" className="text-gray-600 hover:text-gray-900 text-sm">
              Privacy
            </Link>
            <Link href="/" className="text-gray-600 hover:text-gray-900 text-sm">
              Home
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
