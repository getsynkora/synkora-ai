import Link from 'next/link'
import { Zap, Target, Sparkles, Code, Globe, Heart, ArrowRight, Database, Layers, ShieldCheck } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'About – Synkora',
  description: 'Synkora is an open-source AI and LLM platform for building, deploying, and operating agents, workflows, and model-powered products with API-first infrastructure.',
}

const platformPillars = [
  {
    icon: Layers,
    title: 'Platform Layer',
    description: 'A single control plane for agents, prompts, tools, channels, billing, and multi-tenant workspaces.',
    accent: 'bg-[#ffe8de] text-[#cf673e]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,248,242,0.96),rgba(250,237,228,0.9))]',
  },
  {
    icon: Code,
    title: 'API-First Foundation',
    description: 'REST, SSE, and real-time interfaces for chat, automations, and product integrations across your stack.',
    accent: 'bg-[#e4f2ef] text-[#2d8b69]',
    panel: 'bg-[linear-gradient(145deg,rgba(246,252,250,0.96),rgba(231,245,240,0.9))]',
  },
  {
    icon: ShieldCheck,
    title: 'Built for Production',
    description: 'Tenant isolation, keys, quotas, observability, and deployment channels designed for real teams and real workloads.',
    accent: 'bg-[#fff0d8] text-[#d58a27]',
    panel: 'bg-[linear-gradient(145deg,rgba(255,251,242,0.96),rgba(248,239,220,0.9))]',
  },
  {
    icon: Sparkles,
    title: 'LLM-Native Runtime',
    description: 'Model routing, prompt controls, knowledge retrieval, and tool execution in one platform instead of scattered infrastructure.',
    accent: 'bg-[#f6e8f0] text-[#b55e8b]',
    panel: 'bg-[linear-gradient(145deg,rgba(252,246,250,0.96),rgba(246,232,240,0.9))]',
  },
]

const platformCapabilities = [
  {
    title: 'AI Platform',
    description: 'Centralize agent management, tenants, billing, APIs, and operational controls in one product surface.',
    mark: 'PLT',
    accent: 'bg-[#ffe8de] text-[#cf673e]',
  },
  {
    title: 'LLM Platform',
    description: 'Work with your own model providers, route intelligently, and keep cost and quality controls close to the application layer.',
    mark: 'LLM',
    accent: 'bg-[#e4f2ef] text-[#2d8b69]',
  },
  {
    title: 'Deployment Platform',
    description: 'Ship once to web, chat surfaces, internal tools, and APIs without rebuilding the product for every channel.',
    mark: 'DEP',
    accent: 'bg-[#fff0d8] text-[#d58a27]',
  },
]

export default function AboutPage() {
  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-[#f7f2e7] px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-[8%] top-[8%] h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.94),transparent_72%)]" />
          <div className="absolute right-[6%] top-[10%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(240,232,216,0.92),transparent_72%)]" />
          <div className="absolute left-[18%] top-[36%] h-56 w-56 rounded-full bg-[radial-gradient(circle,rgba(125,229,193,0.16),transparent_72%)]" />
        </div>

        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e] shadow-[0_12px_28px_rgba(0,0,0,0.04)] backdrop-blur mb-6">
            <Heart className="w-4 h-4" />
            About Synkora
          </div>
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-[#171717]">
            The Open-Source
            <span className="editorial-highlight mt-3 inline-block sm:block sm:w-fit sm:mx-auto">
              AI and LLM Platform
            </span>
          </h1>
          <p className="mt-6 max-w-3xl mx-auto text-base sm:text-xl leading-8 text-[#5a544a]">
            Synkora is the platform layer for building, deploying, and operating AI agents, LLM workflows, and model-powered products - with your own providers, your own data, and infrastructure you control.
          </p>

          <div className="mt-12 grid gap-4 sm:grid-cols-3 text-left">
            {[
              { label: 'Own your stack', value: 'Open-source by default' },
              { label: 'Build once', value: 'Deploy across channels' },
              { label: 'Run in production', value: 'Tenants, APIs, controls' },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[1.7rem] border border-black/8 bg-white/62 p-5 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur"
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

      <section className="bg-[#f4eee1] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 items-center">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
                <Target className="w-4 h-4" />
                Our Mission
              </div>
              <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-[#171717] mb-5">
                Make AI products easier to build and easier to own
              </h2>
              <p className="text-lg text-[#5f594f] mb-6 leading-8">
                Most teams do not need another framework demo. They need a real platform that can manage agents, LLM providers, knowledge, tools, tenants, billing, and deployment channels without stitching everything together from scratch.
              </p>
              <p className="text-lg text-[#5f594f] leading-8">
                Synkora exists to give teams that platform: an open-source foundation for AI products and LLM applications that can move from prototype to production without switching stacks halfway through.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {platformPillars.map((pillar) => (
                <div
                  key={pillar.title}
                  className={`rounded-[1.8rem] border border-black/8 p-6 shadow-[0_18px_40px_rgba(0,0,0,0.05)] ${pillar.panel}`}
                >
                  <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-[1rem] ${pillar.accent}`}>
                    <pillar.icon className="w-6 h-6" />
                  </div>
                  <h3 className="font-semibold text-[#171717] mb-2 tracking-[-0.03em]">{pillar.title}</h3>
                  <p className="text-sm leading-6 text-[#5f594f]">{pillar.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/60 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b463e]">
              <Database className="w-4 h-4" />
              Platform Focus
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-[#171717] mb-4">
              Built around platforms, not just prompts
            </h2>
            <p className="mx-auto max-w-2xl text-base sm:text-xl text-[#5d564c] leading-8">
              Synkora is designed for teams that need a durable foundation for AI products, not a collection of disconnected experiments.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {platformCapabilities.map((item) => (
              <div
                key={item.title}
                className="rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur"
              >
                <div className={`mb-6 flex h-12 w-12 items-center justify-center rounded-[1rem] text-sm font-semibold tracking-[0.12em] ${item.accent}`}>
                  {item.mark}
                </div>
                <h3 className="text-xl font-semibold tracking-[-0.03em] text-[#171717] mb-3">{item.title}</h3>
                <p className="text-[#5f594f] leading-7">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#171717] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold uppercase tracking-[0.18em] text-[#d7d0c5]">
            <Globe className="w-4 h-4 text-[#7de5c1]" />
            Builder Story
          </div>
          <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-white mb-6">
            Built by Raju Mazumder
          </h2>
          <p className="text-lg text-[#cfc7bb] mb-6 leading-8">
            Synkora was created by <strong className="text-white">Raju Mazumder</strong> to solve a platform problem: teams wanted to ship AI products and LLM-powered systems, but the infrastructure story was fragmented, repetitive, and too easy to outgrow.
          </p>
          <p className="text-lg text-[#cfc7bb] mb-8 leading-8">
            The result is an open-source platform focused on operational reality - APIs, multi-tenancy, agents, knowledge, integrations, deployment surfaces, and the controls needed to run AI seriously.
          </p>
          <a
            href="https://linkedin.com/in/rajumazumder"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-7 py-3.5 font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
          >
            Connect on LinkedIn
          </a>
        </div>
      </section>

      <section className="bg-[#f7f2e7] px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-[#171717] p-10 text-center shadow-[0_34px_90px_rgba(0,0,0,0.2)] md:p-14">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_24%),radial-gradient(circle_at_82%_18%,rgba(125,229,193,0.16),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(255,143,178,0.12),transparent_20%)]" />
            <div className="absolute inset-[10px] rounded-[2.2rem] border border-white/8" />
            <div className="relative">
              <h2 className="text-3xl font-medium tracking-[-0.05em] text-white mb-4">
                Ready to build on Synkora?
              </h2>
              <p className="text-lg text-white/85 mb-8 max-w-xl mx-auto leading-8">
                Start with the platform foundation now, then scale into agents, knowledge, integrations, and deployment channels without switching stacks.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 rounded-full bg-[#7de5c1] px-8 py-4 font-semibold text-[#101915] transition-transform hover:-translate-y-0.5"
                >
                  <Zap className="w-5 h-5" />
                  Get Started Free
                </Link>
                <Link
                  href="https://github.com/rajuniit/synkora-ai"
                  target="_blank"
                  className="inline-flex items-center gap-2 rounded-full border border-white/16 bg-white/6 px-8 py-4 font-semibold text-white transition-colors hover:bg-white/10"
                >
                  View on GitHub
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
