'use client'

import { useState, useEffect } from 'react'
import { Zap } from 'lucide-react'
import toast from 'react-hot-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

// Fixed launch target: 48 hours from 2026-03-03 deployment
const LAUNCH_TARGET = new Date('2026-03-05T00:00:00.000Z')

interface TimeLeft {
  hours: number
  minutes: number
  seconds: number
}

const roles = ['Product Manager', 'Engineer', 'Marketer', 'Support Agent', 'Data Analyst']

export default function CountdownPage() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubscribed, setIsSubscribed] = useState(false)
  const [timeLeft, setTimeLeft] = useState<TimeLeft>({ hours: 48, minutes: 0, seconds: 0 })
  const [mounted, setMounted] = useState(false)
  const [currentRole, setCurrentRole] = useState(0)

  useEffect(() => {
    setMounted(true)

    const calculateTimeLeft = () => {
      const now = new Date()
      const difference = LAUNCH_TARGET.getTime() - now.getTime()

      if (difference <= 0) {
        return { hours: 0, minutes: 0, seconds: 0 }
      }

      const hours = Math.floor(difference / (1000 * 60 * 60))
      const minutes = Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60))
      const seconds = Math.floor((difference % (1000 * 60)) / 1000)

      return { hours, minutes, seconds }
    }

    setTimeLeft(calculateTimeLeft())

    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft())
    }, 1000)

    // Rotate roles
    const roleTimer = setInterval(() => {
      setCurrentRole((prev) => (prev + 1) % roles.length)
    }, 2000)

    return () => {
      clearInterval(timer)
      clearInterval(roleTimer)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return

    setIsSubmitting(true)

    try {
      const response = await fetch(`${API_URL}/api/v1/contact`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: 'Early Access Subscriber',
          email,
          subject: 'Early Access Subscription',
          message: 'User subscribed for early access launch notification.',
        }),
      })

      if (response.ok) {
        setIsSubscribed(true)
        toast.success('You\'re on the list!')
      } else {
        toast.error('Something went wrong. Please try again.')
      }
    } catch (error) {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatNumber = (num: number) => num.toString().padStart(2, '0')

  if (!mounted) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="w-14 h-14 bg-brand/20 rounded-2xl motion-safe:animate-pulse" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center px-6 relative overflow-hidden">
      {/* Animated Grid Background */}
      <div className="absolute inset-0 opacity-20">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(239, 68, 68, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(239, 68, 68, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      {/* Gradient Orbs */}

      {/* Content */}
      <div className="relative z-10 max-w-3xl w-full text-center">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-12">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-ink rounded-xl flex items-center justify-center">
              <Zap className="w-7 h-7 text-white" />
            </div>
            <span className="text-3xl font-bold text-white">Synkora</span>
          </div>
          <span className="text-ink-mute text-sm tracking-wide">No-Code AI Agent Platform</span>
        </div>

        {/* Headline with rotating role */}
        <div className="mb-6">
          <p className="text-4xl md:text-6xl font-black text-white tracking-tight">
            Your Next
          </p>
          <div className="h-[50px] md:h-[75px] flex items-center justify-center overflow-hidden">
            <span
              key={currentRole}
              className="text-4xl md:text-6xl font-black text-transparent bg-clip-text bg-ink whitespace-nowrap"
            >
              {roles[currentRole]}
            </span>
          </div>
          <p className="text-4xl md:text-6xl font-black text-white tracking-tight">
            Is Ready To Work
          </p>
        </div>

        <p className="text-xl text-ash mb-16 max-w-xl mx-auto leading-relaxed">
          AI teammates that actually get things done. Not another chatbot.
        </p>

        {/* Countdown Timer - Minimal */}
        <div className="flex items-center justify-center gap-2 md:gap-4 mb-16 font-mono">
          <div className="flex flex-col items-center">
            <span className="text-5xl md:text-7xl font-black text-white tabular-nums">
              {formatNumber(timeLeft.hours)}
            </span>
            <span className="text-xs text-ink-soft mt-2">hrs</span>
          </div>

          <span className="text-4xl md:text-6xl font-light text-leaf/50 -mt-6">:</span>

          <div className="flex flex-col items-center">
            <span className="text-5xl md:text-7xl font-black text-white tabular-nums">
              {formatNumber(timeLeft.minutes)}
            </span>
            <span className="text-xs text-ink-soft mt-2">min</span>
          </div>

          <span className="text-4xl md:text-6xl font-light text-leaf/50 -mt-6">:</span>

          <div className="flex flex-col items-center">
            <span className="text-5xl md:text-7xl font-black text-white tabular-nums">
              {formatNumber(timeLeft.seconds)}
            </span>
            <span className="text-xs text-ink-soft mt-2">sec</span>
          </div>
        </div>

        {/* Subscribe Form */}
        {isSubscribed ? (
          <div className="border border-leaf/30 rounded-full px-8 py-4 inline-block">
            <p className="text-mint font-medium">
              You're in. We'll be in touch.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="max-w-lg mx-auto">
            <div className="flex flex-col sm:flex-row gap-3 p-2 bg-white/5 rounded-2xl border border-white/10">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                className="flex-1 px-6 py-4 bg-transparent text-white placeholder-ink-soft focus:outline-none text-lg"
              />
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-8 py-4 bg-white hover:bg-sand text-black font-bold rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {isSubmitting ? 'Joining…' : 'Get Early Access'}
              </button>
            </div>
            <p className="text-ink-soft text-sm mt-4">
              Join 500+ founders waiting for launch
            </p>
          </form>
        )}
      </div>

      {/* Bottom Pills */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-4 text-xs text-ink-soft">
        <span className="px-3 py-1.5 border border-ink rounded-full">Open Source</span>
        <span className="px-3 py-1.5 border border-ink rounded-full">Your LLM Keys</span>
        <span className="px-3 py-1.5 border border-ink rounded-full">Self-Host</span>
      </div>
    </div>
  )
}
