import AnimatedNav from '@/components/landing/AnimatedNav'
import AnimatedHero from '@/components/landing/AnimatedHero'
import AnimatedFeatures from '@/components/landing/AnimatedFeatures'
import AgentsSectionClient from '@/components/landing/AgentsSectionClient'
import PricingPreviewClient from '@/components/landing/PricingPreviewClient'
import CTASectionClient from '@/components/landing/CTASectionClient'
import CountdownPage from '@/components/CountdownPage'
import Link from 'next/link'
import { Zap, MessageSquare, ArrowRight, Play, Code2, Blocks, Rocket } from 'lucide-react'

const COMING_SOON = process.env.NEXT_PUBLIC_COMING_SOON === 'true'

export default function LandingPage() {
  if (COMING_SOON) {
    return <CountdownPage />
  }

  return (
    <div className="min-h-screen bg-white">
      <AnimatedNav />
      <AnimatedHero />

      {/* Social Proof Strip */}
      <section className="py-8 px-6 bg-gray-50 border-y border-gray-100">
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-8 sm:gap-16 text-center">
            <div>
              <div className="text-2xl font-bold text-gray-900">MIT</div>
              <div className="text-xs text-gray-500 mt-0.5">Open Source License</div>
            </div>
            <div className="hidden sm:block w-px h-8 bg-gray-200" />
            <div>
              <div className="text-2xl font-bold text-gray-900">Self-host</div>
              <div className="text-xs text-gray-500 mt-0.5">in 5 minutes</div>
            </div>
            <div className="hidden sm:block w-px h-8 bg-gray-200" />
            <div>
              <div className="text-2xl font-bold text-gray-900">6+</div>
              <div className="text-xs text-gray-500 mt-0.5">Deployment channels</div>
            </div>
            <div className="hidden sm:block w-px h-8 bg-gray-200" />
            <div>
              <div className="text-2xl font-bold text-gray-900">BYOK</div>
              <div className="text-xs text-gray-500 mt-0.5">Bring your own LLM keys</div>
            </div>
            <div className="hidden sm:block w-px h-8 bg-gray-200" />
            <a
              href="https://github.com/getsynkora/synkora-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-gray-700 hover:text-gray-900 transition-colors"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              <div>
                <div className="text-sm font-semibold leading-none">Star on GitHub</div>
                <div className="text-xs text-gray-500 mt-0.5">getsynkora/synkora-ai</div>
              </div>
            </a>
          </div>
        </div>
      </section>

      {/* Demo Video Section */}
      <section id="demo" className="relative py-20 sm:py-28 px-4 sm:px-6 overflow-hidden bg-gradient-to-b from-white to-gray-50">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-red-100/60 rounded-full blur-[100px]" />
        </div>

        <div className="relative max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-red-50 border border-red-100 text-red-600 rounded-full text-sm font-semibold mb-5">
              <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              Product Demo
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4 tracking-tight">
              See Synkora in action
            </h2>
            <p className="text-lg text-gray-500 max-w-xl mx-auto">
              Build production-ready AI agents — from the web UI or directly via API
            </p>
          </div>

          <div className="relative">
            <div className="absolute -inset-2 bg-gradient-to-b from-red-200/40 to-gray-200/40 rounded-3xl blur-2xl" />
            <div className="relative rounded-2xl overflow-hidden border border-gray-200 shadow-2xl shadow-gray-300/60 bg-white">
              <div className="flex items-center gap-2 px-4 py-3 bg-gray-100 border-b border-gray-200">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                  <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
                  <div className="w-3 h-3 rounded-full bg-[#28c840]" />
                </div>
                <div className="flex-1 mx-4">
                  <div className="flex items-center gap-2 px-3 py-1 bg-white border border-gray-200 rounded-md max-w-xs mx-auto">
                    <svg className="w-3 h-3 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <span className="text-xs text-gray-400 font-mono truncate">app.synkora.ai</span>
                  </div>
                </div>
              </div>
              <div className="aspect-video bg-gray-100">
                <video
                  src="/demo_video.mp4"
                  poster="https://github.com/user-attachments/assets/4e0b11be-b9d8-4cde-9524-c8ec9467059f"
                  controls
                  playsInline
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          </div>

          <div className="text-center mt-10">
            <Link
              href="https://app.synkora.ai/signup"
              className="inline-flex items-center gap-2 px-7 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-red-500/30"
            >
              <Zap className="w-4 h-4" />
              Start Building Free
            </Link>
          </div>
        </div>
      </section>

      {/* Animated Features Section */}
      <AnimatedFeatures />

      {/* How It Works Section */}
      <section className="py-14 sm:py-20 px-4 sm:px-6 bg-gradient-to-b from-white to-gray-50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-full text-sm font-semibold mb-4">
              <Play className="w-4 h-4" />
              How It Works
            </div>
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              From idea to deployed agent in minutes
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              No infrastructure to configure. No framework to learn. Just build.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { num: '01', icon: Code2, title: 'Create', desc: 'Define your agent — personality, LLM provider, tools — via UI or API', color: 'red' },
              { num: '02', icon: Blocks, title: 'Connect', desc: 'Add knowledge bases, database connections, and 50+ integrations', color: 'orange' },
              { num: '03', icon: MessageSquare, title: 'Test', desc: 'Use the built-in playground to iterate with real-time feedback', color: 'blue' },
              { num: '04', icon: Rocket, title: 'Deploy', desc: 'Ship to Slack, WhatsApp, Teams, web widget, or REST API', color: 'green' },
            ].map((step, idx) => (
              <div key={idx} className="relative bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-lg transition-all">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                  step.color === 'red' ? 'bg-red-100' :
                  step.color === 'orange' ? 'bg-orange-100' :
                  step.color === 'blue' ? 'bg-blue-100' : 'bg-green-100'
                }`}>
                  <step.icon className={`w-6 h-6 ${
                    step.color === 'red' ? 'text-red-600' :
                    step.color === 'orange' ? 'text-orange-600' :
                    step.color === 'blue' ? 'text-blue-600' : 'text-green-600'
                  }`} />
                </div>
                <span className="text-4xl font-bold text-gray-100 absolute top-4 right-4">{step.num}</span>
                <h3 className="text-lg font-bold text-gray-900 mb-2">{step.title}</h3>
                <p className="text-gray-600 text-sm">{step.desc}</p>
              </div>
            ))}
          </div>

          <div className="text-center mt-10">
            <Link href="/how-it-works" className="inline-flex items-center gap-2 text-red-600 hover:text-red-700 font-semibold">
              See the full walkthrough
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Self-host section */}
      <section className="py-14 sm:py-20 px-4 sm:px-6 bg-gray-900">
        <div className="max-w-5xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 text-green-400 rounded-full text-sm font-mono mb-6">
                <span className="w-2 h-2 bg-green-400 rounded-full" />
                Self-hosted in minutes
              </div>
              <h2 className="text-3xl font-bold text-white mb-4">
                Your infrastructure. Your data. Your rules.
              </h2>
              <p className="text-gray-400 leading-relaxed mb-6">
                Run Synkora on your own servers with Docker. No data leaves your environment. Use your own PostgreSQL, Redis, and S3-compatible storage. MIT licensed — no usage fees, no phone-home.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <a
                  href="https://docs.synkora.ai/getting-started/quick-start"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-white text-gray-900 font-semibold rounded-lg hover:bg-gray-100 transition-colors text-sm"
                >
                  Self-host docs
                  <ArrowRight className="w-4 h-4" />
                </a>
                <a
                  href="https://github.com/getsynkora/synkora-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gray-800 text-white font-semibold rounded-lg hover:bg-gray-700 transition-colors text-sm"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  View on GitHub
                </a>
              </div>
            </div>
            <div className="bg-gray-950 rounded-2xl p-6 border border-gray-800 font-mono text-sm">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
                <div className="w-3 h-3 rounded-full bg-[#28c840]" />
                <span className="text-gray-500 text-xs ml-2">terminal</span>
              </div>
              <div className="space-y-2 text-sm">
                <div><span className="text-gray-500"># Clone the repo</span></div>
                <div><span className="text-green-400">$</span> <span className="text-white">git clone https://github.com/getsynkora/synkora-ai</span></div>
                <div><span className="text-green-400">$</span> <span className="text-white">cd synkora-ai</span></div>
                <div className="pt-1"><span className="text-gray-500"># Copy env and start</span></div>
                <div><span className="text-green-400">$</span> <span className="text-white">cp .env.example .env</span></div>
                <div><span className="text-green-400">$</span> <span className="text-white">docker-compose up -d</span></div>
                <div className="pt-2 text-gray-400">
                  <span className="text-green-400">✓</span> Running at <span className="text-blue-400">http://localhost:3005</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pre-built Agents — client island (API fetch + GSAP) */}
      <AgentsSectionClient />

      {/* Why not just use a framework? */}
      <section className="py-14 sm:py-20 px-4 sm:px-6 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-3">Platform, not a framework</h2>
            <p className="text-lg text-gray-600 max-w-xl mx-auto">
              Frameworks give you building blocks. Synkora gives you the whole platform — deployed, monitored, and ready to use.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                name: 'LangChain / CrewAI',
                color: 'border-gray-200',
                tag: 'Framework',
                tagColor: 'bg-gray-100 text-gray-600',
                points: ['Python code only', 'No web UI', 'No deployment infrastructure', 'No multi-tenancy', 'You build everything yourself'],
                cta: null,
              },
              {
                name: 'Synkora',
                color: 'border-red-400 ring-2 ring-red-400',
                tag: 'Platform',
                tagColor: 'bg-red-100 text-red-600',
                points: ['Web UI + REST API', 'Multi-tenant workspaces', 'Deploy to 6+ channels', 'RAG, billing, scheduling built in', 'Self-host or cloud'],
                cta: 'Get Started Free',
              },
              {
                name: 'Flowise',
                color: 'border-gray-200',
                tag: 'Visual builder',
                tagColor: 'bg-gray-100 text-gray-600',
                points: ['Drag-and-drop UI', 'Single-user, local-first', 'Good for prototyping', 'Not built for production teams', 'No multi-tenancy'],
                cta: null,
              },
            ].map((col, i) => (
              <div key={i} className={`rounded-2xl border-2 p-6 ${col.color} ${i === 1 ? 'shadow-xl' : 'shadow-sm'}`}>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-gray-900">{col.name}</h3>
                  <span className={`text-xs font-semibold px-2 py-1 rounded-full ${col.tagColor}`}>{col.tag}</span>
                </div>
                <ul className="space-y-2 mb-5">
                  {col.points.map((p, j) => (
                    <li key={j} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className={`mt-0.5 flex-shrink-0 text-base leading-none ${i === 1 ? 'text-green-500' : 'text-gray-300'}`}>{i === 1 ? '✓' : '–'}</span>
                      {p}
                    </li>
                  ))}
                </ul>
                {col.cta && (
                  <Link
                    href="https://app.synkora.ai/signup"
                    className="block w-full text-center px-4 py-2.5 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl text-sm transition-colors"
                  >
                    {col.cta}
                  </Link>
                )}
              </div>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link href="/alternatives" className="inline-flex items-center gap-2 text-red-600 hover:text-red-700 font-semibold text-sm">
              See detailed comparisons
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Pricing Preview — client island (API fetch) */}
      <PricingPreviewClient />

      {/* CTA + Footer — client island (GSAP animations) */}
      <CTASectionClient />
    </div>
  )
}
