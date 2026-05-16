'use client'

import Link from 'next/link'
import { useEffect, useRef } from 'react'
import {
  Zap,
  ArrowRight,
  Chrome,
  Smartphone,
  Code2,
  Terminal,
  Package,
  Puzzle,
  CheckCircle2,
  Star,
  Download,
  ExternalLink,
  Globe,
  Layers,
} from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

const CHROME_EXTENSION_URL = process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || 'https://chrome.google.com/webstore'
const FLUTTER_PUB_URL = process.env.NEXT_PUBLIC_FLUTTER_PUB_URL || 'https://pub.dev'

const widgetFeatures = [
  'One script tag — works on any website or web app',
  'Fully customizable: colors, position, welcome message',
  'Mobile-responsive bubble and chat window',
  'Supports file uploads, rich text, and streaming',
  'Conversation history persisted across sessions',
  'White-label: hide all Synkora branding if needed',
]

const chromeFeatures = [
  'Chat with any AI agent directly from your browser',
  'Select text on any page and ask your agent about it',
  'Save web content to your knowledge base in one click',
  'Access all your agents from the toolbar popup',
  'Works on any website — no page reload needed',
  'Secure: communicates with your own platform instance',
]

const flutterFeatures = [
  'Embed a full chat UI in any Flutter app in minutes',
  'Stream responses with real-time token rendering',
  'Customizable theme — match your brand exactly',
  'Supports iOS, Android, Web, and Desktop',
  'File upload, voice, and rich message types',
  'Built-in conversation history and session management',
]

const widgetSnippet = `<script>
  window.SynkoraConfig = {
    agentSlug: 'your-agent',
    primaryColor: '#ef4444',
    position: 'bottom-right',
  }
</script>
<script src="https://your-instance.com/widget.js"></script>`

const flutterSnippet = `dependencies:
  synkora_flutter: ^1.0.0`

const flutterUsageSnippet = `SynkoraChat(
  agentSlug: 'your-agent',
  apiUrl: 'https://your-instance.com',
  theme: SynkoraChatTheme(
    primaryColor: Color(0xFFEF4444),
  ),
)`

const oauthIntegrations = [
  { name: 'Google', category: 'Productivity', color: '#4285F4', initial: 'G' },
  { name: 'Gmail', category: 'Email', color: '#EA4335', initial: 'M' },
  { name: 'Google Drive', category: 'Storage', color: '#0F9D58', initial: 'D' },
  { name: 'Google Calendar', category: 'Scheduling', color: '#4285F4', initial: 'C' },
  { name: 'GitHub', category: 'Dev Tools', color: '#24292E', initial: 'GH' },
  { name: 'GitLab', category: 'Dev Tools', color: '#FC6D26', initial: 'GL' },
  { name: 'Slack', category: 'Communication', color: '#4A154B', initial: 'S' },
  { name: 'Microsoft', category: 'Productivity', color: '#00A4EF', initial: 'MS' },
  { name: 'Jira', category: 'Project Mgmt', color: '#0052CC', initial: 'J' },
  { name: 'Notion', category: 'Productivity', color: '#000000', initial: 'N' },
  { name: 'ClickUp', category: 'Project Mgmt', color: '#7B68EE', initial: 'CU' },
  { name: 'Zoom', category: 'Communication', color: '#2D8CFF', initial: 'Z' },
  { name: 'LinkedIn', category: 'Social', color: '#0A66C2', initial: 'Li' },
  { name: 'Twitter / X', category: 'Social', color: '#000000', initial: 'X' },
  { name: 'Telegram', category: 'Messaging', color: '#2AABEE', initial: 'T' },
  { name: 'Apple', category: 'Auth', color: '#000000', initial: '' },
]

const categoryColors: Record<string, string> = {
  'Productivity': 'border border-[#8bb1ff]/18 bg-[#8bb1ff]/10 text-[#a8c4ff]',
  'Email': 'border border-[#ff9d86]/18 bg-[#ff9d86]/10 text-[#ffb29e]',
  'Storage': 'border border-[#8dd6a1]/18 bg-[#8dd6a1]/10 text-[#a6e0b6]',
  'Scheduling': 'border border-[#9fa8ff]/18 bg-[#9fa8ff]/10 text-[#b7beff]',
  'Dev Tools': 'border border-white/10 bg-white/6 text-[#c8c1b6]',
  'Communication': 'border border-[#c78dff]/18 bg-[#c78dff]/10 text-[#d7afff]',
  'Project Mgmt': 'border border-[#ffbc7e]/18 bg-[#ffbc7e]/10 text-[#ffd0a3]',
  'Social': 'border border-[#7cc8ff]/18 bg-[#7cc8ff]/10 text-[#a3daff]',
  'Messaging': 'border border-[#7fdcff]/18 bg-[#7fdcff]/10 text-[#a4e7ff]',
  'Auth': 'border border-white/10 bg-white/6 text-[#c8c1b6]',
}

export default function IntegrationsPage() {
  const embedRef = useRef<HTMLDivElement>(null)
  const connectRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cards = document.querySelectorAll('.fade-in-card')
    cards.forEach((card, i) => {
      const el = card as HTMLElement
      el.style.opacity = '0'
      el.style.transform = 'translateY(24px)'
      setTimeout(() => {
        el.style.transition = 'opacity 0.55s ease, transform 0.55s ease'
        el.style.opacity = '1'
        el.style.transform = 'translateY(0)'
      }, 80 + i * 100)
    })
  }, [])

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-16 pt-28 sm:px-6 sm:pt-36">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[10%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[10%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
          <div className="absolute left-[18%] top-[42%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.14),transparent_72%)]" />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur mb-6">
            <Puzzle className="w-4 h-4" />
            Integrations
          </div>
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-[#171717] mb-6">
            Bring AI agents<br />
            <span className="editorial-highlight inline-block mt-2">everywhere you work</span>
          </h1>
          <p className="text-lg sm:text-xl text-[#5a544a] max-w-2xl mx-auto leading-8">
            Embed agents into any surface. Connect them to the tools your team already uses.
          </p>

          <div className="mt-8 flex items-center justify-center gap-3">
            <a href="#embed" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2.5 text-sm font-semibold text-[#3f3a33] shadow-[0_12px_28px_rgba(0,0,0,0.04)] transition-colors hover:bg-white">
              <Layers className="w-4 h-4" />
              Embed anywhere
            </a>
            <a href="#connect" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2.5 text-sm font-semibold text-[#3f3a33] shadow-[0_12px_28px_rgba(0,0,0,0.04)] transition-colors hover:bg-white">
              <Globe className="w-4 h-4" />
              Connect your stack
            </a>
          </div>
        </div>
      </section>

      <section id="embed" ref={embedRef} className="bg-[#f4eee1] px-4 pb-24 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Layers className="w-3.5 h-3.5" />
              Embed anywhere
            </div>
            <h2 className="mt-3 text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-[#171717]">
              Ship your agent on any surface
            </h2>
            <p className="mt-2 max-w-xl text-[#5d564c] leading-7">
              Three ready-to-use options — no backend work required.
            </p>
          </div>

          <div className="space-y-8">
            {/* Chat Widget */}
            <div className="fade-in-card overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-[0_24px_56px_rgba(0,0,0,0.06)] backdrop-blur transition-shadow hover:shadow-[0_28px_62px_rgba(0,0,0,0.08)]">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className="p-8 sm:p-12">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-[#ffe8de] rounded-[1rem] flex items-center justify-center">
                      <Globe className="w-6 h-6 text-[#cf673e]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-[#171717]">Chat Widget</h3>
                        <span className="px-2 py-0.5 bg-[#e4f2ef] text-[#2d8b69] text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-[#7a736a]">Drop-in chat bubble for any website</p>
                    </div>
                  </div>
                  <p className="text-[#5f594f] mb-8 leading-8">
                    Add your AI agent to any website with a single script tag. No framework required — works with React, Vue, plain HTML, Webflow, WordPress, and more.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {widgetFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-[#2d8b69] flex-shrink-0 mt-0.5" />
                        <span className="text-[#39352f] text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <Link href="/signup" className="inline-flex items-center gap-2 rounded-full bg-[#191919] px-6 py-3 text-sm font-semibold text-[#f7f2e7] transition-colors hover:bg-black">
                      Get your embed code
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                    <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-white">
                      <Code2 className="w-4 h-4" />
                      View Source
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className="bg-[linear-gradient(145deg,rgba(255,248,242,0.96),rgba(250,237,228,0.92))] p-8 sm:p-12 flex flex-col items-center justify-center">
                  <div className="bg-gray-900 rounded-2xl overflow-hidden shadow-2xl w-full max-w-xs font-mono text-xs">
                    <div className="bg-gray-800 px-4 py-2.5 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                      </div>
                      <span className="text-gray-400 text-xs ml-2">index.html</span>
                    </div>
                    <div className="p-4 leading-relaxed">
                      <pre className="text-green-400 whitespace-pre-wrap text-[10.5px] leading-relaxed">{widgetSnippet}</pre>
                    </div>
                  </div>
                  {/* Chat bubble preview */}
                  <div className="relative mt-6 w-full max-w-xs h-16">
                    <div className="absolute bottom-0 right-0 w-14 h-14 bg-[#191919] rounded-full shadow-xl flex items-center justify-center">
                      <Zap className="w-6 h-6 text-white" />
                    </div>
                    <div className="absolute bottom-16 right-16 bg-white border border-gray-200 rounded-2xl rounded-br-sm px-4 py-2.5 shadow-lg text-xs text-gray-700 whitespace-nowrap">
                      Hi! How can I help you today?
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Chrome Extension */}
            <div className="fade-in-card overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-[0_24px_56px_rgba(0,0,0,0.06)] backdrop-blur transition-shadow hover:shadow-[0_28px_62px_rgba(0,0,0,0.08)]">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className="p-8 sm:p-12">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-[#e4f2ef] rounded-[1rem] flex items-center justify-center">
                      <Chrome className="w-6 h-6 text-[#2d8b69]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-[#171717]">Chrome Extension</h3>
                        <span className="px-2 py-0.5 bg-[#e4f2ef] text-[#2d8b69] text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-[#7a736a]">Browser integration for Chromium-based browsers</p>
                    </div>
                  </div>
                  <p className="text-[#5f594f] mb-8 leading-8">
                    Access your AI agents from any tab. Select text, ask questions, save content to your knowledge base — all without leaving the page you're on.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {chromeFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-[#2d8b69] flex-shrink-0 mt-0.5" />
                        <span className="text-[#39352f] text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <a href={CHROME_EXTENSION_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full bg-[#191919] px-6 py-3 text-sm font-semibold text-[#f7f2e7] transition-colors hover:bg-black">
                      <Download className="w-4 h-4" />
                      Install Extension
                    </a>
                    <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-white">
                      <Code2 className="w-4 h-4" />
                      View Source
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className="bg-[linear-gradient(145deg,rgba(246,252,250,0.96),rgba(231,245,240,0.92))] p-8 sm:p-12 flex flex-col justify-center">
                  <div className="bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-100 max-w-xs mx-auto w-full">
                    <div className="bg-gray-100 px-3 py-2 flex items-center gap-2 border-b border-gray-200">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                      </div>
                      <div className="flex-1 bg-white rounded text-xs text-gray-400 px-2 py-0.5 text-center">your-site.com</div>
                        <div className="w-5 h-5 bg-[#191919] rounded flex items-center justify-center">
                          <Zap className="w-3 h-3 text-white" />
                        </div>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 bg-[#191919] rounded-lg flex items-center justify-center">
                          <Zap className="w-3 h-3 text-white" />
                        </div>
                        <span className="text-sm font-bold text-gray-900">Synkora</span>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3 mb-3 text-xs text-gray-500 italic">"Summarize the selected text..."</div>
                      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-gray-700 leading-relaxed">
                        Here's a concise summary: The article covers three main topics...
                      </div>
                      <div className="mt-3 flex gap-2">
                        <div className="flex-1 bg-gray-100 rounded-lg h-7 text-xs text-gray-400 flex items-center px-2">Ask follow-up...</div>
                        <div className="w-7 h-7 bg-[#191919] rounded-lg flex items-center justify-center">
                          <ArrowRight className="w-3 h-3 text-white" />
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-4 mt-6">
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <Star key={i} className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                      ))}
                    </div>
                    <span className="text-sm text-gray-500">Chrome Web Store</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Flutter Package */}
            <div className="fade-in-card overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-[0_24px_56px_rgba(0,0,0,0.06)] backdrop-blur transition-shadow hover:shadow-[0_28px_62px_rgba(0,0,0,0.08)]">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className="bg-[linear-gradient(145deg,rgba(255,251,242,0.96),rgba(248,239,220,0.92))] p-8 sm:p-12 flex flex-col justify-center order-2 lg:order-1">
                  <div className="bg-gray-900 rounded-2xl overflow-hidden shadow-2xl max-w-xs mx-auto w-full font-mono text-xs">
                    <div className="bg-gray-800 px-4 py-2.5 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                        <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                      </div>
                      <span className="text-gray-400 text-xs ml-2">pubspec.yaml</span>
                    </div>
                    <div className="p-4 leading-relaxed">
                      <div className="text-gray-500 mb-1"># Add to pubspec.yaml</div>
                      <pre className="text-green-400 whitespace-pre-wrap">{flutterSnippet}</pre>
                      <div className="mt-4 text-gray-500 mb-1"># Usage</div>
                      <pre className="text-cyan-300 whitespace-pre-wrap text-[10px] leading-relaxed">{flutterUsageSnippet}</pre>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-3 mt-6">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-full border border-gray-200 shadow-sm">
                      <Package className="w-3.5 h-3.5 text-cyan-600" />
                      <span className="text-xs font-semibold text-gray-700">pub.dev</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-full border border-gray-200 shadow-sm">
                      <Smartphone className="w-3.5 h-3.5 text-teal-600" />
                      <span className="text-xs font-semibold text-gray-700">iOS · Android · Web</span>
                    </div>
                  </div>
                </div>
                <div className="p-8 sm:p-12 order-1 lg:order-2">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-[#fff0d8] rounded-[1rem] flex items-center justify-center">
                      <Smartphone className="w-6 h-6 text-[#d58a27]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-[#171717]">Flutter Package</h3>
                        <span className="px-2 py-0.5 bg-[#e4f2ef] text-[#2d8b69] text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-[#7a736a]">Official Dart/Flutter SDK for Synkora</p>
                    </div>
                  </div>
                  <p className="text-[#5f594f] mb-8 leading-8">
                    Drop a fully-featured AI chat interface into any Flutter app. Stream responses, customize the theme, and manage conversation sessions — all with a few lines of code.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {flutterFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-[#2d8b69] flex-shrink-0 mt-0.5" />
                        <span className="text-[#39352f] text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <a href={FLUTTER_PUB_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full bg-[#191919] px-6 py-3 text-sm font-semibold text-[#f7f2e7] transition-colors hover:bg-black">
                      <Package className="w-4 h-4" />
                      View on pub.dev
                    </a>
                    <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-white">
                      <Terminal className="w-4 h-4" />
                      View Source
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="connect" ref={connectRef} className="border-t border-black/8 bg-[#171717] px-4 py-20 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-12">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#d7d0c5] shadow-sm">
              <Globe className="w-3.5 h-3.5" />
              Connect your stack
            </div>
            <h2 className="mt-3 text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-white">
              Your agents work where your team works
            </h2>
            <p className="mt-2 max-w-xl leading-7 text-[#c7beb2]">
              Connect your agents to 15+ services via OAuth. Let them read emails, create tickets, push code, post messages, and more — securely and with per-user authorization.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {oauthIntegrations.map((integration) => (
              <div
                key={integration.name}
                className="fade-in-card relative flex items-center gap-3 overflow-hidden rounded-[1.4rem] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.035))] p-4 shadow-[0_16px_34px_rgba(0,0,0,0.18)] transition-all group hover:-translate-y-0.5 hover:border-white/14 hover:bg-[linear-gradient(180deg,rgba(255,255,255,0.07),rgba(255,255,255,0.045))]"
              >
                <div className="absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/18 to-transparent" />
                <div
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white shadow-sm ring-1 ring-white/10"
                  style={{ backgroundColor: integration.color }}
                >
                  {integration.initial || (
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
                    </svg>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-white truncate">{integration.name}</div>
                  <div className={`mt-1 inline-block rounded-md px-1.5 py-0.5 text-xs font-medium ${categoryColors[integration.category] || 'border border-white/10 bg-white/6 text-[#c8c1b6]'}`}>
                    {integration.category}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <p className="text-sm text-[#978f84] mt-6 text-center">
            More coming soon · All connections use OAuth 2.0 · No passwords stored
          </p>
        </div>
      </section>

      <section className="bg-[#f7f2e7] px-4 py-20 sm:px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-8 shadow-[0_34px_90px_rgba(0,0,0,0.2)] sm:p-14">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
            <h2 className="text-2xl sm:text-3xl font-medium tracking-[-0.05em] text-white mb-4">
              Build your agent. Ship everywhere.
            </h2>
            <p className="text-white/85 mb-8 text-base sm:text-lg max-w-xl mx-auto leading-8">
              Create an agent in minutes, then reach your users on web, mobile, and beyond.
            </p>
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 text-base font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
            >
              Start building free
              <ArrowRight className="w-5 h-5" />
            </Link>
            </div>
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
