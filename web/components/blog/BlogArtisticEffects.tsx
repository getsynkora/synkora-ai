'use client'

import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  opacity: number
  opacityDir: number
}

export default function BlogArtisticEffects() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // ── 1. Floating constellation canvas ────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    const PARTICLE_COUNT = 28
    const CONNECTION_DIST = 160
    const particles: Particle[] = []

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize, { passive: true })

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        r: Math.random() * 2 + 0.6,
        opacity: Math.random() * 0.35 + 0.08,
        opacityDir: (Math.random() > 0.5 ? 1 : -1) * 0.0018,
      })
    }

    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // connections first (below dots)
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i]
          const b = particles[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const d = Math.sqrt(dx * dx + dy * dy)
          if (d < CONNECTION_DIST) {
            const alpha = (1 - d / CONNECTION_DIST) * 0.1
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.strokeStyle = `rgba(45,139,105,${alpha})`
            ctx.lineWidth = 0.7
            ctx.stroke()
          }
        }
      }

      // dots
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        p.opacity += p.opacityDir
        if (p.opacity < 0.06 || p.opacity > 0.45) p.opacityDir *= -1

        if (p.x < -10) p.x = canvas.width + 10
        if (p.x > canvas.width + 10) p.x = -10
        if (p.y < -10) p.y = canvas.height + 10
        if (p.y > canvas.height + 10) p.y = -10

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(45,139,105,${p.opacity})`
        ctx.fill()
      }

      animId = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  // ── 2. Mouse-tracking spotlight on article surface ───────────────────────
  useEffect(() => {
    const article = document.querySelector('[data-blog-article]') as HTMLElement | null
    if (!article) return

    const onMove = (e: MouseEvent) => {
      const rect = article.getBoundingClientRect()
      article.style.setProperty('--mx', `${e.clientX - rect.left}px`)
      article.style.setProperty('--my', `${e.clientY - rect.top}px`)
      article.classList.add('glow-active')
    }
    const onLeave = () => article.classList.remove('glow-active')

    article.addEventListener('mousemove', onMove, { passive: true })
    article.addEventListener('mouseleave', onLeave, { passive: true })
    return () => {
      article.removeEventListener('mousemove', onMove)
      article.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  // ── 3. Scroll-reveal for every direct markdown block ────────────────────
  useEffect(() => {
    const blocks = document.querySelectorAll('.content-markdown > *')
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('sr-in')
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.07, rootMargin: '0px 0px -48px 0px' }
    )

    blocks.forEach((el, i) => {
      el.classList.add('sr-block')
      ;(el as HTMLElement).style.transitionDelay = `${Math.min(i * 25, 180)}ms`
      observer.observe(el)
    })

    return () => observer.disconnect()
  }, [])

  // ── 4. h2 heading underline draw on entry ───────────────────────────────
  useEffect(() => {
    const headings = document.querySelectorAll('.content-markdown h2')
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('h2-visible')
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.5 }
    )
    headings.forEach((h) => observer.observe(h))
    return () => observer.disconnect()
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0"
      style={{ opacity: 0.7 }}
      aria-hidden="true"
    />
  )
}
