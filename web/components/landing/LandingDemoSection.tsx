'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'

export default function LandingDemoSection() {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const tryPlay = async () => {
      try {
        video.muted = true
        await video.play()
      } catch {
        // Ignore autoplay rejections; controls remain available for manual playback.
      }
    }

    void tryPlay()
    video.addEventListener('canplay', tryPlay)

    return () => {
      video.removeEventListener('canplay', tryPlay)
    }
  }, [])

  return (
    <section id="demo" className="landing px-4 py-20 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <h2 className="mb-4 text-4xl font-medium tracking-[-0.05em] text-ink sm:text-5xl">
            See Synkora in action
          </h2>
          <p className="mx-auto max-w-xl text-lg leading-relaxed text-ink-soft">
            Build production-ready AI agents, from the web UI or directly via API
          </p>
        </div>

        <div className="overflow-hidden rounded-2xl border border-ink/10 bg-sand-deep shadow-soft">
          <div className="relative aspect-video">
            <video
              ref={videoRef}
              src="/demo_video.mp4"
              poster="https://github.com/user-attachments/assets/4e0b11be-b9d8-4cde-9524-c8ec9467059f"
              autoPlay
              controls
              loop
              muted
              playsInline
              preload="metadata"
              aria-label="Product demo: building an agent in Synkora"
              className="h-full w-full object-cover"
            />
          </div>
        </div>

        <div className="mt-10 text-center">
          <Link
            href="https://app.synkora.ai/signup"
            className="inline-flex items-center rounded-full bg-ink px-7 py-3 text-sm font-semibold text-paper transition-colors hover:bg-ink/85"
          >
            Start Building Free
          </Link>
        </div>
      </div>
    </section>
  )
}
