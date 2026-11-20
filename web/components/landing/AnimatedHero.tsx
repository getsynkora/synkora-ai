import Link from 'next/link'
import { Database, Globe2, ShieldCheck, Sparkles, Workflow } from 'lucide-react'

const rise = (delay: string) => ({ '--d': delay }) as React.CSSProperties

const surfaceCards = [
  {
    title: 'Knowledge Base',
    subtitle: 'Ground responses on your own data',
    icon: Database,
    position: 'left-[2%] top-[13%]',
    style: 'w-[250px] -rotate-[10deg]',
    accent: 'bg-mint',
  },
  {
    title: 'Human Approval',
    subtitle: 'Insert guardrails before actions',
    icon: ShieldCheck,
    position: 'right-[2%] top-[7%]',
    style: 'w-[248px] rotate-[9deg]',
    accent: 'bg-blush',
  },
  {
    title: 'Workflow Engine',
    subtitle: 'Tools, memory, and orchestration',
    icon: Workflow,
    position: 'left-[10%] bottom-[10%]',
    style: 'w-[262px] rotate-[7deg]',
    accent: 'bg-honey',
  },
  {
    title: 'Deploy Anywhere',
    subtitle: 'Slack, WhatsApp, Teams, API',
    icon: Globe2,
    position: 'right-[9%] bottom-[14%]',
    style: 'w-[252px] -rotate-[8deg]',
    accent: 'bg-ink',
  },
]

export default function AnimatedHero() {
  return (
    <div className="landing relative overflow-hidden bg-paper pt-36">
      <div className="px-6 pb-20">
        <div className="mx-auto grid max-w-[1480px] gap-14 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.98fr)] xl:items-center">
          <div className="max-w-4xl">
            <h1
              className="rise max-w-4xl text-5xl font-medium leading-[0.95] tracking-[-0.05em] text-ink md:text-7xl"
              style={{ overflowWrap: 'break-word', minWidth: 0 }}
            >
              The enterprise AI platform{' '}
              <span className="border-b-[3px] border-leaf pb-1">your team</span> controls
            </h1>

            <p className="rise mt-8 max-w-2xl text-xl leading-relaxed text-ink-soft" style={rise('0.1s')}>
              Deploy secure, auditable AI agents across your organization, on your infrastructure and under your rules.
            </p>

            <div className="rise mt-10 flex flex-col items-start gap-4 sm:flex-row" style={rise('0.2s')}>
              <Link
                href="https://app.synkora.ai/signup"
                className="inline-flex w-full items-center justify-center rounded-full bg-ink px-8 py-4 text-lg font-semibold text-paper transition-colors hover:bg-ink/85 sm:w-auto"
              >
                Start Building Free
              </Link>
              <a
                href="mailto:enterprise@synkora.ai"
                className="inline-flex w-full items-center justify-center rounded-full border border-ink/15 px-8 py-4 text-lg font-semibold text-ink transition-colors hover:bg-white sm:w-auto"
              >
                Talk to Sales
              </a>
            </div>
          </div>

          <div className="rise relative hidden min-h-[680px] min-w-0 xl:block" style={rise('0.15s')} aria-hidden="true">
            <div className="absolute inset-x-[5%] bottom-[6%] top-[4%] overflow-hidden rounded-[3rem] border border-ink/10 bg-sand shadow-soft">
              <div
                className="absolute inset-[6%] rounded-[2.4rem] border border-ink/10 bg-paper"
                style={{
                  backgroundImage:
                    'linear-gradient(rgb(var(--ink) / 0.045) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--ink) / 0.045) 1px, transparent 1px)',
                  backgroundSize: '38px 38px',
                }}
              />

              <svg viewBox="0 0 900 700" className="absolute inset-[10%] h-[80%] w-[80%]" aria-hidden="true">
                <circle cx="450" cy="350" r="220" fill="none" className="stroke-ink/10" strokeWidth="1.1" strokeDasharray="8 18" />
                <circle cx="450" cy="350" r="165" fill="none" className="stroke-mint/40" strokeWidth="1.5" strokeDasharray="6 14" />
                <circle cx="450" cy="350" r="116" fill="none" className="stroke-blush/30" strokeWidth="1.2" strokeDasharray="5 12" />
                <path d="M140 128 C 248 118 338 180 388 292 S 514 508 662 540" fill="none" className="stroke-mint" strokeWidth="2.6" strokeLinecap="round" />
                <path d="M708 132 C 650 214 592 278 534 320 C 498 346 470 356 450 356 C 430 356 402 346 366 320 C 304 274 252 212 186 150" fill="none" className="stroke-blush" strokeWidth="2.4" strokeLinecap="round" />
                <path d="M174 564 C 292 528 346 486 392 410 C 420 364 432 340 450 330 C 476 314 520 322 564 344 C 624 374 676 438 732 522" fill="none" className="stroke-honey" strokeWidth="2.6" strokeLinecap="round" />
                <path d="M742 534 C 664 468 606 424 556 394 C 510 366 482 348 450 348 C 414 348 382 370 324 410 C 266 450 222 502 174 566" fill="none" className="stroke-mint" strokeWidth="2.2" strokeLinecap="round" />
              </svg>

              <div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2">
                <div className="absolute inset-[15px] rounded-full border border-ink/10 bg-white" />
                <div className="absolute inset-[34px] flex items-center justify-center rounded-full bg-ink">
                  <Sparkles className="h-10 w-10 text-paper" />
                </div>
              </div>
            </div>

            {surfaceCards.map((card) => (
              <div
                key={card.title}
                className={`absolute ${card.position} ${card.style} rounded-2xl border border-ink/10 bg-white p-5 shadow-soft`}
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-sand-deep">
                  <card.icon className="h-5 w-5 text-ink" />
                </div>
                <h3 className="text-lg font-semibold tracking-[-0.03em] text-ink">{card.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{card.subtitle}</p>
                <span className={`mt-5 block h-1 w-10 rounded-full ${card.accent}`} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
