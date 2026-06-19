'use client'

import { useEffect, useRef } from 'react'

export default function ReadingProgress() {
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const update = () => {
      const bar = barRef.current
      if (!bar) return
      const scrollTop = window.scrollY
      const docHeight = document.documentElement.scrollHeight - window.innerHeight
      const progress = docHeight > 0 ? scrollTop / docHeight : 0
      bar.style.transform = `scaleX(${progress})`
    }
    window.addEventListener('scroll', update, { passive: true })
    update()
    return () => window.removeEventListener('scroll', update)
  }, [])

  return (
    <div
      ref={barRef}
      aria-hidden="true"
      className="fixed left-0 top-0 z-50 h-[3px] w-full origin-left"
      style={{
        background: 'linear-gradient(90deg, #79dfbc 0%, #2d8b69 60%, #1f6d52 100%)',
        transform: 'scaleX(0)',
        transition: 'transform 80ms linear',
      }}
    />
  )
}
