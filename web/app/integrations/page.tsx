'use client'

import Link from 'next/link'
import { useRef } from 'react'
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

const GITHUB_REPO_URL = 'https://github.com/getsynkora/synkora-ai'
const CHROME_EXTENSION_URL = process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || `${GITHUB_REPO_URL}/tree/master/extension`
const FLUTTER_PUB_URL = process.env.NEXT_PUBLIC_FLUTTER_PUB_URL || 'https://pub.dev/packages/synkora_chat'

const widgetFeatures = [
  'One script tag, works on any website or web app',
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
  'Works on any website, no page reload needed',
  'Secure: communicates with your own platform instance',
]

const flutterFeatures = [
  'Embed a full chat UI in any Flutter app in minutes',
  'Stream responses with real-time token rendering',
  'Customizable theme, match your brand exactly',
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
  { name: 'Google', category: 'Productivity', color: 'rgb(var(--azure))', initial: 'G' },
  { name: 'Gmail', category: 'Email', color: 'rgb(var(--brand))', initial: 'M' },
  { name: 'Google Drive', category: 'Storage', color: 'rgb(var(--leaf))', initial: 'D' },
  { name: 'Google Calendar', category: 'Scheduling', color: 'rgb(var(--azure))', initial: 'C' },
  { name: 'GitHub', category: 'Dev Tools', color: 'rgb(var(--night))', initial: 'GH' },
  { name: 'GitLab', category: 'Dev Tools', color: 'rgb(var(--rust))', initial: 'GL' },
  { name: 'Slack', category: 'Communication', color: 'rgb(var(--wine))', initial: 'S' },
  { name: 'Microsoft', category: 'Productivity', color: 'rgb(var(--azure))', initial: 'MS' },
  { name: 'Jira', category: 'Project Mgmt', color: 'rgb(var(--azure))', initial: 'J' },
  { name: 'Notion', category: 'Productivity', color: 'rgb(var(--ink))', initial: 'N' },
  { name: 'ClickUp', category: 'Project Mgmt', color: 'rgb(var(--azure))', initial: 'CU' },
  { name: 'Zoom', category: 'Communication', color: 'rgb(var(--azure))', initial: 'Z' },
  { name: 'LinkedIn', category: 'Social', color: 'rgb(var(--azure))', initial: 'Li' },
  { name: 'Twitter / X', category: 'Social', color: 'rgb(var(--ink))', initial: 'X' },
  { name: 'Telegram', category: 'Messaging', color: 'rgb(var(--azure))', initial: 'T' },
  { name: 'Apple', category: 'Auth', color: 'rgb(var(--ink))', initial: '' },
]

const categoryColors: Record<string, string> = {
  'Productivity': 'border border-azure/20 bg-azure/10 text-azure',
  'Email': 'border border-rust/20 bg-rust/10 text-rust',
  'Storage': 'border border-leaf/20 bg-leaf/10 text-leaf',
  'Scheduling': 'border border-steel/20 bg-steel/10 text-steel',
  'Dev Tools': 'border border-ink/10 bg-ink/5 text-ink-soft',
  'Communication': 'border border-wine/20 bg-wine/10 text-wine',
  'Project Mgmt': 'border border-gold/20 bg-gold/10 text-gold',
  'Social': 'border border-azure/20 bg-azure/10 text-azure',
  'Messaging': 'border border-azure/20 bg-azure/10 text-azure',
  'Auth': 'border border-ink/10 bg-ink/5 text-ink-soft',
}

export default function IntegrationsPage() {
  const embedRef = useRef<HTMLDivElement>(null)
  const connectRef = useRef<HTMLDivElement>(null)

  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-paper px-4 pb-16 pt-28 sm:px-6 sm:pt-36">
                <div className="relative max-w-4xl mx-auto text-center">
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-ink mb-6">
            Deploy enterprise agents<br />
            <span className="mt-2 inline-block text-leaf">everywhere you work</span>
          </h1>
          <p className="text-lg sm:text-xl text-ink-soft max-w-2xl mx-auto leading-8">
            Embed agents into any surface. Connect them to the tools your team already uses.
          </p>

          <div className="mt-8 flex items-center justify-center gap-3">
            <a href="#embed" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2.5 text-sm font-semibold text-night shadow-soft transition-colors hover:bg-white">
              <Layers className="w-4 h-4" />
              Embed anywhere
            </a>
            <a href="#connect" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2.5 text-sm font-semibold text-night shadow-soft transition-colors hover:bg-white">
              <Globe className="w-4 h-4" />
              Connect your stack
            </a>
          </div>
        </div>
      </section>

      <section id="embed" ref={embedRef} className="bg-sand px-4 pb-24 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-10">
            <h2 className="mt-3 text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink">
              Ship your agent on any surface
            </h2>
            <p className="mt-2 max-w-xl text-ink-soft leading-7">
              Three ready-to-use options, no backend work required.
            </p>
          </div>

          <div className="space-y-8">
            {/* Chat Widget */}
            <div className="overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-soft transition-shadow hover:shadow-soft">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className="p-8 sm:p-12">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-sand-deep rounded-[1rem] flex items-center justify-center">
                      <Globe className="w-6 h-6 text-rust" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-ink">Chat Widget</h3>
                        <span className="px-2 py-0.5 bg-leaf-wash text-leaf text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-ink-mute">Drop-in chat bubble for any website</p>
                    </div>
                  </div>
                  <p className="text-ink-soft mb-8 leading-8">
                    Add your AI agent to any website with a single script tag. No framework required, works with React, Vue, plain HTML, Webflow, WordPress, and more.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {widgetFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-leaf flex-shrink-0 mt-0.5" />
                        <span className="text-night text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <Link href="/signup" className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition-colors hover:bg-black">
                      Get your embed code
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                    <a href={GITHUB_REPO_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-ink transition-colors hover:bg-white">
                      <Code2 className="w-4 h-4" />
                      View Source
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className=" bg-cream p-8 sm:p-12 flex flex-col items-center justify-center">
                  <div className="bg-ink rounded-2xl overflow-hidden shadow-2xl w-full max-w-xs font-mono text-xs">
                    <div className="bg-ink px-4 py-2.5 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-hotpink" />
                        <div className="w-2.5 h-2.5 rounded-full bg-honey" />
                        <div className="w-2.5 h-2.5 rounded-full bg-mint" />
                      </div>
                      <span className="text-ash text-xs ml-2">index.html</span>
                    </div>
                    <div className="p-4 leading-relaxed">
                      <pre className="text-mint whitespace-pre-wrap text-[10.5px] leading-relaxed">{widgetSnippet}</pre>
                    </div>
                  </div>
                  {/* Chat bubble preview */}
                  <div className="relative mt-6 w-full max-w-xs h-16">
                    <div className="absolute bottom-0 right-0 w-14 h-14 bg-ink rounded-full shadow-xl flex items-center justify-center">
                      <Zap className="w-6 h-6 text-white" />
                    </div>
                    <div className="absolute bottom-16 right-16 bg-white border border-line rounded-2xl rounded-br-sm px-4 py-2.5 shadow-lg text-xs text-ink-soft whitespace-nowrap">
                      Hi! How can I help you today?
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Chrome Extension */}
            <div className="overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-soft transition-shadow hover:shadow-soft">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className="p-8 sm:p-12">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-leaf-wash rounded-[1rem] flex items-center justify-center">
                      <Chrome className="w-6 h-6 text-leaf" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-ink">Chrome Extension</h3>
                        <span className="px-2 py-0.5 bg-leaf-wash text-leaf text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-ink-mute">Browser integration for Chromium-based browsers</p>
                    </div>
                  </div>
                  <p className="text-ink-soft mb-8 leading-8">
                    Access your AI agents from any tab. Select text, ask questions, save content to your knowledge base, all without leaving the page you're on.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {chromeFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-leaf flex-shrink-0 mt-0.5" />
                        <span className="text-night text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <a href={CHROME_EXTENSION_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition-colors hover:bg-black">
                      <Download className="w-4 h-4" />
                      Install Extension
                    </a>
                    <a href={GITHUB_REPO_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-ink transition-colors hover:bg-white">
                      <Code2 className="w-4 h-4" />
                      View Source
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
                <div className=" bg-white p-8 sm:p-12 flex flex-col justify-center">
                  <div className="bg-white rounded-2xl shadow-xl overflow-hidden border border-sand max-w-xs mx-auto w-full">
                    <div className="bg-sand px-3 py-2 flex items-center gap-2 border-b border-line">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-hotpink" />
                        <div className="w-2.5 h-2.5 rounded-full bg-honey" />
                        <div className="w-2.5 h-2.5 rounded-full bg-mint" />
                      </div>
                      <div className="flex-1 bg-white rounded text-xs text-ash px-2 py-0.5 text-center">your-site.com</div>
                        <div className="w-5 h-5 bg-ink rounded flex items-center justify-center">
                          <Zap className="w-3 h-3 text-white" />
                        </div>
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 bg-ink rounded-lg flex items-center justify-center">
                          <Zap className="w-3 h-3 text-white" />
                        </div>
                        <span className="text-sm font-bold text-ink">Synkora</span>
                      </div>
                      <div className="bg-cream rounded-lg p-3 mb-3 text-xs text-ink-mute italic">"Summarize the selected text…"</div>
                      <div className="bg-sky-wash border border-sky-wash rounded-lg p-3 text-xs text-ink-soft leading-relaxed">
                        Here's a concise summary: The article covers three main topics...
                      </div>
                      <div className="mt-3 flex gap-2">
                        <div className="flex-1 bg-sand rounded-lg h-7 text-xs text-ash flex items-center px-2">Ask follow-up…</div>
                        <div className="w-7 h-7 bg-ink rounded-lg flex items-center justify-center">
                          <ArrowRight className="w-3 h-3 text-white" />
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-4 mt-6">
                    <div className="flex items-center gap-1">
                      {[...Array(5)].map((_, i) => (
                        <Star key={i} className="w-3.5 h-3.5 fill-honey text-honey" />
                      ))}
                    </div>
                    <span className="text-sm text-ink-mute">Chrome Web Store</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Flutter Package */}
            <div className="overflow-hidden rounded-[2rem] border border-black/8 bg-white/74 shadow-soft transition-shadow hover:shadow-soft">
              <div className="grid lg:grid-cols-2 gap-0">
                <div className=" bg-cream p-8 sm:p-12 flex flex-col justify-center order-2 lg:order-1">
                  <div className="bg-ink rounded-2xl overflow-hidden shadow-2xl max-w-xs mx-auto w-full font-mono text-xs">
                    <div className="bg-ink px-4 py-2.5 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-hotpink" />
                        <div className="w-2.5 h-2.5 rounded-full bg-honey" />
                        <div className="w-2.5 h-2.5 rounded-full bg-mint" />
                      </div>
                      <span className="text-ash text-xs ml-2">pubspec.yaml</span>
                    </div>
                    <div className="p-4 leading-relaxed">
                      <div className="text-ink-mute mb-1"># Add to pubspec.yaml</div>
                      <pre className="text-mint whitespace-pre-wrap">{flutterSnippet}</pre>
                      <div className="mt-4 text-ink-mute mb-1"># Usage</div>
                      <pre className="text-steel whitespace-pre-wrap text-[10px] leading-relaxed">{flutterUsageSnippet}</pre>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-3 mt-6">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-full border border-line shadow-sm">
                      <Package className="w-3.5 h-3.5 text-azure" />
                      <span className="text-xs font-semibold text-ink-soft">pub.dev</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-full border border-line shadow-sm">
                      <Smartphone className="w-3.5 h-3.5 text-leaf" />
                      <span className="text-xs font-semibold text-ink-soft">iOS, Android, Web</span>
                    </div>
                  </div>
                </div>
                <div className="p-8 sm:p-12 order-1 lg:order-2">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 bg-sand-deep rounded-[1rem] flex items-center justify-center">
                      <Smartphone className="w-6 h-6 text-warn" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-ink">Flutter Package</h3>
                        <span className="px-2 py-0.5 bg-leaf-wash text-leaf text-xs font-semibold rounded-full">Available now</span>
                      </div>
                      <p className="text-sm text-ink-mute">Official Dart/Flutter SDK for Synkora</p>
                    </div>
                  </div>
                  <p className="text-ink-soft mb-8 leading-8">
                    Drop a fully-featured AI chat interface into any Flutter app. Stream responses, customize the theme, and manage conversation sessions, all with a few lines of code.
                  </p>
                  <ul className="space-y-3 mb-10">
                    {flutterFeatures.map((feat, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <CheckCircle2 className="w-5 h-5 text-leaf flex-shrink-0 mt-0.5" />
                        <span className="text-night text-sm leading-6">{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center gap-3 flex-wrap">
                    <a href={FLUTTER_PUB_URL} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition-colors hover:bg-black">
                      <Package className="w-4 h-4" />
                      View on pub.dev
                    </a>
                    <a href={`${GITHUB_REPO_URL}/tree/master/flutter`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/80 px-6 py-3 text-sm font-semibold text-ink transition-colors hover:bg-white">
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

      <section id="connect" ref={connectRef} className="border-t border-ink/10 bg-sand px-4 py-20 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="mb-12">
            <h2 className="mt-3 text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink">
              Your agents work where your team works
            </h2>
            <p className="mt-2 max-w-xl leading-7 text-ink-soft">
              Connect your agents to 15+ services via OAuth. Let them read emails, create tickets, push code, post messages, and more, securely and with per-user authorization.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {oauthIntegrations.map((integration) => (
              <div
                key={integration.name}
                className="relative flex items-center gap-3 overflow-hidden rounded-[1.4rem] border border-ink/10 bg-white p-4 shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] group hover:-translate-y-0.5 hover:border-white/14"
              >
                <div
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white shadow-sm ring-1 ring-ink/10"
                  style={{ backgroundColor: integration.color }}
                >
                  {integration.initial || (
                    <svg aria-hidden="true" className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
                    </svg>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink truncate">{integration.name}</div>
                  <div className={`mt-1 inline-block rounded-md px-1.5 py-0.5 text-xs font-medium ${categoryColors[integration.category] || 'border border-ink/10 bg-ink/5 text-ink-soft'}`}>
                    {integration.category}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <p className="text-sm text-ink-mute mt-6 text-center">
            More coming soon. All connections use OAuth 2.0. No passwords stored.
          </p>
        </div>
      </section>

      <section className="bg-paper px-4 py-20 sm:px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-ink p-8 shadow-soft sm:p-14">
            <div className="absolute inset-0" />
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
              className="inline-flex items-center gap-2 rounded-full bg-mint px-8 py-4 text-base font-semibold text-ink transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
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
