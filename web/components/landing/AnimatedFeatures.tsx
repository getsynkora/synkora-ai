'use client'

import { useEffect, useRef } from 'react'
import { HeadphonesIcon, BarChart3, Code2 } from 'lucide-react'

const features = [
  {
    Icon: HeadphonesIcon,
    accent: '#79dfbc',
    title: 'Enterprise Support Hub',
    description: 'Handle customer queries 24/7 using your knowledge base, with HITL approval gates for escalations, full audit trail, and RBAC-controlled access.',
  },
  {
    Icon: Code2,
    accent: '#f0c56d',
    title: 'Engineering Intelligence',
    description: 'Automated code review, CI/CD monitoring, and incident triage — integrated with GitHub, GitLab, Jira, and Slack via secured OAuth credentials.',
  },
  {
    Icon: BarChart3,
    accent: '#ff8fb2',
    title: 'Executive Analytics',
    description: 'Real-time dashboards, automated reporting, and data insights from your connected databases — with encrypted connections and row-level access control.',
  },
]

export default function AnimatedFeatures() {
  const sectionRef = useRef<HTMLElement>(null)
  const cardsRef = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const cards = cardsRef.current.filter(Boolean) as HTMLDivElement[]
    const triggers: { kill: () => void }[] = []
    let cancelled = false

    Promise.all([import('gsap'), import('gsap/ScrollTrigger')]).then(
      ([{ default: gsap }, { ScrollTrigger }]) => {
        if (cancelled) return
        gsap.registerPlugin(ScrollTrigger)

        cards.forEach((card, index) => {
          const st = ScrollTrigger.create({
            trigger: card,
            start: 'top 82%',
            onEnter: () => {
              gsap.fromTo(
                card,
                { opacity: 0, y: 50 },
                { opacity: 1, y: 0, duration: 0.7, delay: index * 0.12, ease: 'power3.out' }
              )
            },
            once: true,
          })
          triggers.push(st)

          const onEnterHover = () => gsap.to(card, { y: -8, duration: 0.28, ease: 'power2.out' })
          const onLeaveHover = () => gsap.to(card, { y: 0, duration: 0.28, ease: 'power2.out' })

          card.addEventListener('mouseenter', onEnterHover)
          card.addEventListener('mouseleave', onLeaveHover)
        })
      }
    )

    return () => {
      cancelled = true
      triggers.forEach((t) => t.kill())
    }
  }, [])

  return (
    <section ref={sectionRef} className="overflow-hidden bg-[#f7f2e7] px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-[#171717]">
            Enterprise AI, deployed across your org
          </h2>
          <p className="text-xl leading-relaxed text-[#575149]">
            Real agents doing real work — with the audit trails, access controls, and integrations your enterprise requires
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          {features.map((feature, index) => (
            <div
              key={index}
              ref={(el) => {
                cardsRef.current[index] = el
              }}
              className="cursor-pointer rounded-[2rem] border border-black/10 bg-white/60 p-8 shadow-[0_18px_40px_rgba(0,0,0,0.05)] backdrop-blur"
            >
              <div
                className="mb-6 flex h-14 w-14 items-center justify-center rounded-[1rem] border border-black/8"
                style={{ background: `linear-gradient(135deg, ${feature.accent}30, rgba(255,255,255,0.9))` }}
              >
                <feature.Icon className="h-6 w-6 text-[#171717]" />
              </div>
              <h3 className="mb-3 text-xl font-semibold tracking-[-0.03em] text-[#171717]">{feature.title}</h3>
              <p className="leading-relaxed text-[#575149]">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
