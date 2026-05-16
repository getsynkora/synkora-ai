'use client'

import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const features = [
  {
    icon: '🧑‍💼',
    title: 'AI Product Manager',
    description: 'Automate backlog prioritization, sprint planning, and status reports. Your AI PM keeps projects on track around the clock.',
  },
  {
    icon: '👨‍💻',
    title: 'AI Software Engineer',
    description: 'Code review, bug triage, documentation generation, and CI/CD monitoring. An AI teammate that never misses a PR.',
  },
  {
    icon: '📢',
    title: 'AI Marketing Lead',
    description: 'Content creation, campaign analysis, SEO optimization, and social media management. Scale your marketing effortlessly.',
  },
]

export default function AnimatedFeatures() {
  const sectionRef = useRef<HTMLElement>(null)
  const cardsRef = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const cards = cardsRef.current.filter(Boolean) as HTMLDivElement[]
    const triggers: ScrollTrigger[] = []

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

    return () => {
      triggers.forEach((t) => t.kill())
    }
  }, [])

  return (
    <section ref={sectionRef} className="overflow-hidden bg-[#f7f2e7] px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-[#171717]">
            AI Agents for Every Role
          </h2>
          <p className="text-xl leading-relaxed text-[#575149]">
            Deploy intelligent teammates that handle real work, not just chat
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
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-[#79dfbc]/65 text-3xl">
                {feature.icon}
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
