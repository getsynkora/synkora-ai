'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useAuth } from '@/lib/hooks/useAuth'
import { secureStorage } from '@/lib/auth/secure-storage'
import { SocialLoginButton } from '@/components/social-auth'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { Bot, Layers3, Shield, Workflow } from 'lucide-react'
import { useTranslations } from 'next-intl'

function SignInContent() {
  const t = useTranslations('auth.signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { signIn, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  // Get redirect URL from query params
  const redirectUrl = searchParams.get('redirect')

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(redirectUrl ? decodeURIComponent(redirectUrl) : '/agents')
    }
  }, [isAuthenticated, isLoading, redirectUrl, router])

  // Handle OAuth callback
  useEffect(() => {
    const loginStatus = searchParams.get('login')
    const provider = searchParams.get('provider')
    const exchangeCode = searchParams.get('exchange_code')

    if (loginStatus === 'success' && exchangeCode) {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      fetch(`${apiUrl}/api/v1/auth/token-exchange?code=${exchangeCode}`, { credentials: 'include' })
        .then((res) => {
          if (!res.ok) throw new Error('Exchange failed')
          return res.json()
        })
        .then(({ access_token, expires_in }) => {
          secureStorage.storeTokens({ access_token, expires_in })
          toast.success(t('successWithProvider', { provider: provider ?? '' }))
          window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : '/agents'
        })
        .catch(() => {
          const msg = t('failedRetry')
          setError(msg)
          toast.error(msg)
        })
    } else if (loginStatus === 'error') {
      const message = searchParams.get('message') || t('socialFailed')
      toast.error(message)
      setError(message)
    }
  }, [redirectUrl, searchParams, router])

  // Show loader while checking auth state — must be after all hooks
  if (isLoading && !isSubmitting) {
    return (
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
        </div>
      </AuthPageFrame>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      await signIn(email, password)
      toast.success(t('success'))
      // Redirect to original page or default to dashboard
      const targetUrl = redirectUrl ? decodeURIComponent(redirectUrl) : '/dashboard'
      router.push(targetUrl)
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
            ? err.response.data.detail
            : t('invalidCredentials'))
        : err.message || t('failed')
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSocialLogin = (provider: 'google' | 'microsoft' | 'apple') => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    window.location.href = `${apiUrl}/api/v1/auth/${provider}/login`
  }

  const workspaceSignals = [
    {
      icon: Bot,
      title: t('agentsTitle'),
      description: t('agentsDescription'),
      className: 'border-ink/10 bg-white',
      iconClassName: 'bg-sand-deep text-ink',
    },
    {
      icon: Workflow,
      title: t('workflowsTitle'),
      description: t('workflowsDescription'),
      className: 'border-ink/10 bg-white',
      iconClassName: 'bg-sand-deep text-ink',
    },
    {
      icon: Layers3,
      title: t('knowledgeTitle'),
      description: t('knowledgeDescription'),
      className: 'border-ink/10 bg-white',
      iconClassName: 'bg-sand-deep text-ink',
    },
  ]

  return (
    <AuthPageFrame>
      <div className="grid gap-6 lg:min-h-[calc(100vh-10rem)] lg:grid-cols-[1.08fr_0.92fr]">
        <div className="relative hidden overflow-hidden rounded-[2.25rem] border border-black/10 bg-sand p-10 text-ink lg:flex lg:flex-col lg:justify-between">

          <div className="relative z-10">

            <h2 className="max-w-xl text-4xl font-semibold leading-tight text-ink">
              {t('heroLine1')}
              <span className="block text-leaf">{t('heroLine2')}</span>
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-soft">
              {t('heroBody')}
            </p>
          </div>

          <div className="relative z-10 my-10 space-y-4">
            <div className="rounded-[1.85rem] border border-ink/10 bg-white p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold text-ink-mute">
                    {t('sessionReadyTitle')}
                  </div>
                  <p className="mt-3 max-w-lg text-base leading-relaxed text-ink-soft">
                    {t('sessionReadyBody')}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {workspaceSignals.map((signal) => {
                const Icon = signal.icon

                return (
                  <div
                    key={signal.title}
                    className={`rounded-[1.65rem] border p-5 ${signal.className}`}
                  >
                    <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${signal.iconClassName}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="mt-4 text-base font-semibold text-ink">{signal.title}</div>
                    <div className="mt-2 text-sm leading-relaxed text-ink-soft">{signal.description}</div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="relative z-10 flex flex-wrap gap-3 pt-2">
            <div className="rounded-full border border-ink/10 bg-white px-4 py-2 text-sm font-medium text-ink">
              {t('bringKeys')}
            </div>
            <div className="rounded-full border border-ink/10 bg-white px-4 py-2 text-sm font-medium text-ink">
              {t('openSource')}
            </div>
            <div className="rounded-full border border-ink/10 bg-white px-4 py-2 text-sm font-medium text-ink">
              {t('selfHost')}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center py-2 lg:py-8">
          <div className="w-full max-w-xl">
            <div className="mb-8">
              <h1 className="mt-5 text-3xl font-semibold tracking-tight text-ink sm:text-5xl">{t('title')}</h1>
              <p className="mt-3 text-base text-ink-soft sm:text-lg">
                {t('subtitle')}
              </p>
            </div>

            <div className="rounded-[2rem] border border-black/10 bg-white p-6 shadow-soft sm:p-8">
              <div className="mb-8">
                <SocialLoginButton
                  provider="google"
                  onClick={() => handleSocialLogin('google')}
                  variant="full"
                />
              </div>

              <div className="relative my-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-line"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-white px-4 font-medium text-ink-mute">{t('orContinue')}</span>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {error && (
                  <div className="flex items-center gap-2 rounded-[1.25rem] border border-blush bg-blush-wash px-4 py-3 text-sm text-danger">
                    <svg aria-hidden="true" className="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-semibold text-ink-soft">
                    {t('email')}
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('emailPlaceholder')}
                  />
                </div>

                <div>
                  <label htmlFor="password" className="mb-2 block text-sm font-semibold text-ink-soft">
                    {t('password')}
                  </label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('passwordPlaceholder')}
                  />
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <label className="flex items-center text-sm text-ink-soft">
                    <input
                      type="checkbox"
                      className="h-5 w-5 cursor-pointer rounded border-taupe text-ink focus:ring-ink"
                    />
                    <span className="ml-2">{t('remember')}</span>
                  </label>
                  <Link href="/forgot-password" className="text-sm font-semibold text-leaf transition-colors hover:text-forest">
                    {t('forgot')}
                  </Link>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full rounded-[1.35rem] bg-ink px-6 py-4 text-lg font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <span className="flex items-center justify-center">
                      <svg aria-hidden="true" className="-ml-1 mr-3 h-5 w-5 motion-safe:animate-spin text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t('submitting')}
                    </span>
                  ) : (
                    t('submit')
                  )}
                </button>
              </form>

              <div className="mt-8 text-center">
                <p className="text-ink-soft">
                  {t('noAccount')}{' '}
                  <Link href="/signup" className="font-bold text-leaf transition-colors hover:text-forest">
                    {t('signUpFree')}
                  </Link>
                </p>
              </div>
            </div>

            <p className="mt-8 text-center text-sm text-ink-mute">
              {t.rich('agree', {
                terms: (chunks) => (
                  <Link href="/terms" className="font-medium text-leaf hover:text-forest">{chunks}</Link>
                ),
                privacy: (chunks) => (
                  <Link href="/privacy" className="font-medium text-leaf hover:text-forest">{chunks}</Link>
                ),
              })}
            </p>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm text-ink-mute">
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <Shield className="h-4 w-4" />
                <span>{t('ssl')}</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>{t('encrypted')}</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>{t('private')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AuthPageFrame>
  )
}

export default function SignInPage() {
  return (
    <Suspense fallback={
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
        </div>
      </AuthPageFrame>
    }>
      <SignInContent />
    </Suspense>
  )
}
