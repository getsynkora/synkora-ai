'use client'

import { useState } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import Link from 'next/link'
import toast from 'react-hot-toast'
import axios from 'axios'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { useTranslations } from 'next-intl'

export default function ForgotPasswordPage() {
  const t = useTranslations('auth.forgotPassword')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      await axios.post(`${apiUrl}/console/api/auth/forgot-password`, {
        email
      })
      
      setIsSubmitted(true)
      toast.success(t('sent'))
    } catch (err: any) {
      const errorMessage = extractErrorMessage(err, t('failed'))
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  if (isSubmitted) {
    return (
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
          <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-ink">
              <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-ink mb-2">{t('checkEmail')}</h1>
            <p className="text-ink-soft">
              {t.rich('sentTo', { email, strong: (chunks) => <strong>{chunks}</strong> })}
            </p>
          </div>

          <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-soft sm:p-8">
            <div className="text-center space-y-4">
              <p className="text-sm text-ink-soft">
                {t('noEmail')}
              </p>
              <button
                onClick={() => setIsSubmitted(false)}
                className="text-sm font-medium text-leaf hover:text-forest"
              >
                {t('tryAnother')}
              </button>
            </div>

            <div className="mt-6 pt-6 border-t border-line text-center">
              <Link href="/signin" className="text-sm font-medium text-leaf hover:text-forest">
                {t('back')}
              </Link>
            </div>
          </div>
          </div>
        </div>
      </AuthPageFrame>
    )
  }

  return (
    <AuthPageFrame>
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-ink">
            <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-ink mb-2">{t('title')}</h1>
          <p className="text-ink-soft">{t('subtitle')}</p>
        </div>

        <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-soft sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-ink-soft mb-2">
                {t('emailLabel')}
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-[1.1rem] border border-line bg-cream px-4 py-3 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                placeholder={t('emailPlaceholder')}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-[1.1rem] bg-ink px-4 py-3 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <svg aria-hidden="true" className="motion-safe:animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {t('sending')}
                </span>
              ) : (
                t('submit')
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link href="/signin" className="text-sm font-medium text-leaf hover:text-forest">
              {t('back')}
            </Link>
          </div>
        </div>
        </div>
      </div>
    </AuthPageFrame>
  )
}
