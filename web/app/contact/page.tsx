'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Zap, Mail, MessageSquare, Github, Send, CheckCircle, AlertCircle } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    message: '',
  })
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('loading')
    setErrorMessage('')

    try {
      const response = await fetch(`${API_URL}/api/v1/contact`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setStatus('success')
        setFormData({ name: '', email: '', subject: '', message: '' })
      } else {
        setStatus('error')
        setErrorMessage(data.detail || data.message || 'Something went wrong. Please try again.')
      }
    } catch {
      setStatus('error')
      setErrorMessage('Unable to send message. Please try again later.')
    }
  }

  return (
    <PublicPageFrame mainClassName="pt-28">
      <div className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12">
            {/* Contact Info */}
            <div>
              <h1 className="mb-6 text-4xl font-medium tracking-[-0.05em] text-ink">
                Talk to the Synkora team
              </h1>
              <p className="mb-8 text-lg leading-relaxed text-ink-soft">
                Have questions about enterprise features, self-hosting, or want to discuss your use case? We respond within 24 hours.
              </p>

              {/* Contact Methods */}
              <div className="space-y-6">
                <a
                  href="mailto:hello@synkora.ai"
                  className="flex items-start gap-4 rounded-[1.25rem] border border-black/10 bg-white/60 p-4 shadow-soft transition-shadow hover:shadow-soft"
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[0.875rem] bg-mint/25">
                    <Mail className="w-6 h-6 text-leaf" />
                  </div>
                  <div>
                    <h3 className="mb-1 font-semibold text-ink">Email Us</h3>
                    <p className="font-medium text-leaf">hello@synkora.ai</p>
                    <p className="mt-1 text-sm text-ink-mute">We typically respond within 24 hours</p>
                  </div>
                </a>

                <a
                  href="https://github.com/getsynkora/synkora-ai/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-4 rounded-[1.25rem] border border-black/10 bg-white/60 p-4 shadow-soft transition-shadow hover:shadow-soft"
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[0.875rem] bg-black/6">
                    <Github className="w-6 h-6 text-ink" />
                  </div>
                  <div>
                    <h3 className="mb-1 font-semibold text-ink">GitHub Issues</h3>
                    <p className="font-medium text-ink-soft">Report bugs & request features</p>
                    <p className="mt-1 text-sm text-ink-mute">For technical issues and feature requests</p>
                  </div>
                </a>

                <a
                  href="https://discord.gg/synkora-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-4 rounded-[1.25rem] border border-black/10 bg-white/60 p-4 shadow-soft transition-shadow hover:shadow-soft"
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[0.875rem] bg-mint/25">
                    <svg aria-hidden="true" className="w-6 h-6 text-leaf" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z"/>
                    </svg>
                  </div>
                  <div>
                    <h3 className="mb-1 font-semibold text-ink">Discord Community</h3>
                    <p className="font-medium text-ink-soft">Join our community</p>
                    <p className="mt-1 text-sm text-ink-mute">Chat with other developers and get help</p>
                  </div>
                </a>
              </div>

              {/* Other Emails */}
              <div className="mt-6 rounded-[1.25rem] border border-black/10 bg-white/60 p-5 shadow-soft">
                <h3 className="mb-3 text-sm font-semibold text-ink-soft">Specific Inquiries</h3>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center justify-between gap-4">
                    <span className="text-ink-mute">Enterprise Sales</span>
                    <a href="mailto:enterprise@synkora.ai" className="font-medium text-leaf hover:underline">enterprise@synkora.ai</a>
                  </li>
                  <li className="flex items-center justify-between gap-4">
                    <span className="text-ink-mute">Security Issues</span>
                    <a href="mailto:security@synkora.ai" className="font-medium text-leaf hover:underline">security@synkora.ai</a>
                  </li>
                  <li className="flex items-center justify-between gap-4">
                    <span className="text-ink-mute">Support</span>
                    <a href="mailto:support@synkora.ai" className="font-medium text-leaf hover:underline">support@synkora.ai</a>
                  </li>
                </ul>
              </div>
            </div>

            {/* Contact Form */}
            <div className="rounded-[2rem] border border-black/10 bg-white/60 p-8 shadow-soft">
              <h2 className="mb-6 text-2xl font-semibold tracking-[-0.03em] text-ink">Send us a Message</h2>

              {status === 'success' ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-leaf-wash rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckCircle className="w-8 h-8 text-leaf" />
                  </div>
                  <h3 className="text-xl font-semibold text-ink mb-2">Message Sent!</h3>
                  <p className="text-ink-soft mb-6">
                    Thank you for reaching out. We'll get back to you within 24 hours.
                  </p>
                  <button
                    onClick={() => setStatus('idle')}
                    className="font-medium text-leaf hover:text-forest"
                  >
                    Send Another Message
                  </button>
                </div>
              ) : status === 'error' ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-sand-deep rounded-full flex items-center justify-center mx-auto mb-4">
                    <AlertCircle className="w-8 h-8 text-danger" />
                  </div>
                  <h3 className="text-xl font-semibold text-ink mb-2">Oops! Something went wrong</h3>
                  <p className="text-ink-soft mb-6">
                    {errorMessage}
                  </p>
                  <button
                    onClick={() => setStatus('idle')}
                    className="font-medium text-leaf hover:text-forest"
                  >
                    Try Again
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div>
                    <label htmlFor="name" className="mb-1.5 block text-sm font-medium text-ink-soft">
                      Your Name
                    </label>
                    <input
                      type="text"
                      id="name"
                      required
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-line focus:border-leaf focus:ring-2 focus:ring-mint/30 transition-[color,background-color,border-color,box-shadow,opacity,transform] outline-none"
                      placeholder="John Doe"
                    />
                  </div>

                  <div>
                    <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-ink-soft">
                      Email Address
                    </label>
                    <input
                      type="email"
                      id="email"
                      required
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-line focus:border-leaf focus:ring-2 focus:ring-mint/30 transition-[color,background-color,border-color,box-shadow,opacity,transform] outline-none"
                      placeholder="john@example.com"
                    />
                  </div>

                  <div>
                    <label htmlFor="subject" className="mb-1.5 block text-sm font-medium text-ink-soft">
                      Subject
                    </label>
                    <select
                      id="subject"
                      required
                      value={formData.subject}
                      onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-line focus:border-leaf focus:ring-2 focus:ring-mint/30 transition-[color,background-color,border-color,box-shadow,opacity,transform] outline-none bg-white"
                    >
                      <option value="">Select a topic</option>
                      <option value="General Inquiry">General Inquiry</option>
                      <option value="Enterprise Licensing">Enterprise Licensing</option>
                      <option value="Technical Support">Technical Support</option>
                      <option value="Partnership Opportunity">Partnership Opportunity</option>
                      <option value="Feedback">Feedback</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="message" className="mb-1.5 block text-sm font-medium text-ink-soft">
                      Message
                    </label>
                    <textarea
                      id="message"
                      required
                      rows={5}
                      value={formData.message}
                      onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-line focus:border-leaf focus:ring-2 focus:ring-mint/30 transition-[color,background-color,border-color,box-shadow,opacity,transform] outline-none resize-none"
                      placeholder="Tell us what's on your mind…"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={status === 'loading'}
                    className="flex w-full items-center justify-center gap-2 rounded-full bg-ink px-6 py-3.5 font-semibold text-paper shadow-sm transition-transform motion-reduce:transition-none hover:-translate-y-0.5 disabled:opacity-70"
                  >
                    {status === 'loading' ? (
                      <>
                        <svg aria-hidden="true" className="motion-safe:animate-spin h-5 w-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="w-5 h-5" />
                        Send Message
                      </>
                    )}
                  </button>

                  <p className="text-xs text-ink-mute text-center">
                    We typically respond within 24 hours.
                  </p>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>

    </PublicPageFrame>
  )
}
