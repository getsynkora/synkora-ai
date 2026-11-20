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
    accent: 'bg-sand-deep text-rust',
    panel: ' bg-cream',
  },
  {
    icon: Code,
    title: 'API-First Foundation',
    description: 'REST, SSE, and real-time interfaces for chat, automations, and product integrations across your stack.',
    accent: 'bg-leaf-wash text-leaf',
    panel: ' bg-white',
  },
  {
    icon: ShieldCheck,
    title: 'Built for Production',
    description: 'Tenant isolation, keys, quotas, observability, and deployment channels designed for real teams and real workloads.',
    accent: 'bg-sand-deep text-warn',
    panel: ' bg-cream',
  },
  {
    icon: Sparkles,
    title: 'LLM-Native Runtime',
    description: 'Model routing, prompt controls, knowledge retrieval, and tool execution in one platform instead of scattered infrastructure.',
    accent: 'bg-blush-wash text-wine',
    panel: ' bg-white',
  },
]

const platformCapabilities = [
  {
    title: 'AI Platform',
    description: 'Centralize agent management, tenants, billing, APIs, and operational controls in one product surface.',
    mark: 'PLT',
    accent: 'bg-sand-deep text-rust',
  },
  {
    title: 'LLM Platform',
    description: 'Work with your own model providers, route intelligently, and keep cost and quality controls close to the application layer.',
    mark: 'LLM',
    accent: 'bg-leaf-wash text-leaf',
  },
  {
    title: 'Deployment Platform',
    description: 'Ship once to web, chat surfaces, internal tools, and APIs without rebuilding the product for every channel.',
    mark: 'DEP',
    accent: 'bg-sand-deep text-warn',
  },
]

export default function AboutPage() {
  return (
    <PublicPageFrame mainClassName="">
      <section className="relative overflow-hidden bg-paper px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">

        <div className="relative max-w-5xl mx-auto text-center">
          <h1 className="text-4xl sm:text-6xl font-medium tracking-[-0.06em] text-ink">
            The Open-Source
            <span className="mt-3 block text-leaf sm:w-fit sm:mx-auto">
              Enterprise AI Platform
            </span>
          </h1>
          <p className="mt-6 max-w-3xl mx-auto text-base sm:text-xl leading-8 text-ink-soft">
            Synkora is the platform layer for building, deploying, and operating AI agents, LLM workflows, and model-powered products - with your own providers, your own data, and infrastructure you control.
          </p>

          <div className="mt-12 grid gap-4 sm:grid-cols-3 text-left">
            {[
              { label: 'Enterprise security', value: 'SAML/OIDC, RBAC, Audit Logs' },
              { label: 'Full data ownership', value: 'Self-host, MIT Licensed' },
              { label: 'Multi-tenant platform', value: 'APIs, controls, isolation' },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[1.7rem] border border-black/8 bg-white/62 p-5 shadow-soft"
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

      <section className="bg-sand px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 items-center">
            <div>
              <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-5">
                Make AI products easier to build and easier to own
              </h2>
              <p className="text-lg text-ink-soft mb-6 leading-8">
                Most teams do not need another framework demo. They need a real platform that can manage agents, LLM providers, knowledge, tools, tenants, billing, and deployment channels without stitching everything together from scratch.
              </p>
              <p className="text-lg text-ink-soft leading-8">
                Synkora exists to give teams that platform: an open-source foundation for AI products and LLM applications that can move from prototype to production without switching stacks halfway through.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {platformPillars.map((pillar) => (
                <div
                  key={pillar.title}
                  className={`rounded-[1.8rem] border border-black/8 p-6 shadow-soft ${pillar.panel}`}
                >
                  <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-[1rem] ${pillar.accent}`}>
                    <pillar.icon className="w-6 h-6" />
                  </div>
                  <h3 className="font-semibold text-ink mb-2 tracking-[-0.03em]">{pillar.title}</h3>
                  <p className="text-sm leading-6 text-ink-soft">{pillar.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-4">
              Built around platforms, not just prompts
            </h2>
            <p className="mx-auto max-w-2xl text-base sm:text-xl text-ink-soft leading-8">
              Synkora is designed for teams that need a durable foundation for AI products, not a collection of disconnected experiments.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {platformCapabilities.map((item) => (
              <div
                key={item.title}
                className="rounded-[2rem] border border-black/8 bg-white/72 p-8 shadow-soft"
              >
                <div className={`mb-6 flex h-12 w-12 items-center justify-center rounded-[1rem] text-sm font-semibold tracking-[0.12em] ${item.accent}`}>
                  {item.mark}
                </div>
                <h3 className="text-xl font-semibold tracking-[-0.03em] text-ink mb-3">{item.title}</h3>
                <p className="text-ink-soft leading-7">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-sand px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-5xl font-medium tracking-[-0.05em] text-ink mb-6">
            Built by Raju Mazumder
          </h2>
          <p className="text-lg text-ink-soft mb-6 leading-8">
            Synkora was created by <strong className="text-ink">Raju Mazumder</strong> to solve a platform problem: teams wanted to ship AI products and LLM-powered systems, but the infrastructure story was fragmented, repetitive, and too easy to outgrow.
          </p>
          <p className="text-lg text-ink-soft mb-8 leading-8">
            The result is an open-source platform focused on operational reality - APIs, multi-tenancy, agents, knowledge, integrations, deployment surfaces, and the controls needed to run AI seriously.
          </p>
          <a
            href="https://linkedin.com/in/rajumazumder"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-mint px-7 py-3.5 font-semibold text-ink transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
          >
            Connect on LinkedIn
          </a>
        </div>
      </section>

      <section className="bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="max-w-4xl mx-auto">
          <div className="relative overflow-hidden rounded-[2.7rem] border border-black/10 bg-ink p-10 text-center shadow-soft md:p-14">
            <div className="absolute inset-0" />
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
                  className="inline-flex items-center gap-2 rounded-full bg-mint px-8 py-4 font-semibold text-ink transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
                >
                  <Zap className="w-5 h-5" />
                  Get Started Free
                </Link>
                <Link
                  href="https://github.com/getsynkora/synkora-ai"
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
