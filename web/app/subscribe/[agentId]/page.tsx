'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Bell, CheckCircle, Loader2 } from 'lucide-react'
import { subscribeToAgent } from '@/lib/api/subscriptions'

export default function SubscribePage() {
  const params = useParams()
  const agentId = params?.agentId as string

  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    try {
      setStatus('loading')
      const result = await subscribeToAgent(agentId, email.trim())
      setMessage(result.message)
      setStatus('success')
    } catch (err: any) {
      setMessage(err.message || 'Something went wrong. Please try again.')
      setStatus('error')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-sand w-full max-w-md p-8">
        {status === 'success' ? (
          <div className="text-center">
            <div className="w-16 h-16 bg-leaf-wash rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-leaf" />
            </div>
            <h2 className="text-xl font-bold text-ink mb-2">You&apos;re subscribed!</h2>
            <p className="text-ink-soft text-sm">{message}</p>
            <p className="text-ash text-xs mt-3">
              You&apos;ll receive an email each time a new report is published. Check your inbox for a confirmation.
            </p>
          </div>
        ) : (
          <>
            <div className="text-center mb-6">
              <div className="w-14 h-14 bg-sand-deep rounded-full flex items-center justify-center mx-auto mb-4">
                <Bell className="w-7 h-7 text-leaf" />
              </div>
              <h1 className="text-2xl font-bold text-ink">Subscribe to reports</h1>
              <p className="text-ink-mute text-sm mt-2">
                Get this agent&apos;s scheduled reports delivered to your inbox automatically.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-ink-soft mb-1.5">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-4 py-2.5 border border-taupe rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ink focus:border-transparent transition-colors"
                />
              </div>

              {status === 'error' && (
                <p className="text-sm text-danger bg-blush-wash px-3 py-2 rounded-lg">{message}</p>
              )}

              <button
                type="submit"
                disabled={status === 'loading'}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-ink hover:bg-ink/85 text-white font-medium rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === 'loading' ? (
                  <>
                    <Loader2 className="w-4 h-4 motion-safe:animate-spin" />
                    Subscribing...
                  </>
                ) : (
                  <>
                    <Bell className="w-4 h-4" />
                    Subscribe
                  </>
                )}
              </button>

              <p className="text-center text-xs text-ash">
                You can unsubscribe at any time via the link in each email.
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
