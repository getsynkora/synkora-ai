'use client'

import { useState, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useAuth } from '@/lib/hooks/useAuth'
import { SocialLoginButton } from '@/components/social-auth'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { ArrowRight, Bot, Check, CheckCircle2, Database, Shield, Workflow, X } from 'lucide-react'
import { useLocale, useTranslations } from 'next-intl'

interface PasswordRequirement {
  /** Key under auth.signup in the messages files. */
  label: string
  test: (password: string) => boolean
}

const passwordRequirements: PasswordRequirement[] = [
  { label: 'reqMinLength', test: (p) => p.length >= 12 },
  { label: 'reqUppercase', test: (p) => /[A-Z]/.test(p) },
  { label: 'reqLowercase', test: (p) => /[a-z]/.test(p) },
  { label: 'reqNumber', test: (p) => /\d/.test(p) },
  { label: 'reqSpecial', test: (p) => /[!@#$%^&*(),.?":{}|<>\[\]\\;'`~_+=\-/]/.test(p) },
]

export default function SignUpPage() {
  const t = useTranslations('auth.signup')
  const locale = useLocale()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showPasswordRequirements, setShowPasswordRequirements] = useState(false)
  const { signUp, isAuthenticated, isLoading: authLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace('/agents')
    }
  }, [isAuthenticated, authLoading, router])

  // Must be before any early return to satisfy Rules of Hooks
  const passwordValidation = useMemo(() => {
    return passwordRequirements.map((req) => ({
      ...req,
      met: req.test(password),
    }))
  }, [password])

  if (authLoading && !isLoading) {
    return (
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
        </div>
      </AuthPageFrame>
    )
  }

  const isPasswordValid = passwordValidation.every((req) => req.met)
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!isPasswordValid) {
      setError(t('passwordRequirements'))
      return
    }

    if (password !== confirmPassword) {
      setError(t('passwordsMismatch'))
      return
    }

    setIsLoading(true)

    try {
      await signUp(email, password, name, locale)
      toast.success(t('created'))
      router.push('/signin')
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail
        ? (Array.isArray(err.response.data.detail)
            ? err.response.data.detail.map((e: any) => e.msg).join(', ')
            : err.response.data.detail)
        : err.message || t('failed')
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSocialLogin = (provider: 'google' | 'microsoft' | 'apple') => {
    // Redirect to backend OAuth endpoint
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    window.location.href = `${apiUrl}/api/v1/auth/${provider}/login`
  }

  const platformCapabilities = [
    {
      icon: Bot,
      title: t('agentsTitle'),
      description: t('agentsDescription'),
      className: 'border-ink/10 bg-white',
      iconClassName: 'bg-sand-deep text-ink',
    },
    {
      icon: Database,
      title: t('knowledgeTitle'),
      description: t('knowledgeDescription'),
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
  ]

  return (
    <AuthPageFrame>
      <div className="grid gap-6 lg:min-h-[calc(100vh-10rem)] lg:grid-cols-[0.92fr_1.08fr]">
        <div className="flex items-center justify-center py-2 lg:py-8">
          <div className="w-full max-w-xl">
            <div className="mb-8">
              <h1 className="mt-5 text-3xl font-semibold tracking-tight text-ink sm:text-5xl">
                {t('title')}
              </h1>
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

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="flex items-center gap-2 rounded-[1.25rem] border border-blush bg-blush-wash px-4 py-3 text-sm text-danger">
                    <svg aria-hidden="true" className="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="name" className="mb-2 block text-sm font-semibold text-ink-soft">
                    {t('fullName')}
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('fullNamePlaceholder')}
                  />
                </div>

                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-semibold text-ink-soft">
                    {t('workEmail')}
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('workEmailPlaceholder')}
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
                    onFocus={() => setShowPasswordRequirements(true)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('passwordPlaceholder')}
                  />
                  {showPasswordRequirements && password.length > 0 && (
                    <div className="mt-3 space-y-1.5 rounded-[1.15rem] border border-black/10 bg-paper p-3">
                      {passwordValidation.map((req, idx) => (
                        <div key={idx} className="flex items-center gap-1.5">
                          {req.met ? (
                            <Check className="h-3.5 w-3.5 flex-shrink-0 text-leaf" />
                          ) : (
                            <X className="h-3.5 w-3.5 flex-shrink-0 text-ash" />
                          )}
                          <span className={`text-xs ${req.met ? 'text-leaf' : 'text-ink-mute'}`}>
                            {t(req.label)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {!showPasswordRequirements || password.length === 0 ? (
                    <p className="mt-2 text-xs text-ink-mute">
                      {t('passwordHint')}
                    </p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="mb-2 block text-sm font-semibold text-ink-soft">
                    {t('confirmPassword')}
                  </label>
                  <input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-line bg-cream px-4 py-4 text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ink"
                    placeholder={t('confirmPasswordPlaceholder')}
                  />
                  {confirmPassword.length > 0 && (
                    <div className="mt-2 flex items-center gap-1.5">
                      {passwordsMatch ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-leaf" />
                          <span className="text-xs text-leaf">{t('passwordsMatch')}</span>
                        </>
                      ) : (
                        <>
                          <X className="h-3.5 w-3.5 text-leaf" />
                          <span className="text-xs text-leaf">{t('passwordsMismatch')}</span>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-start pt-2">
                  <input
                    type="checkbox"
                    required
                    className="mt-0.5 h-5 w-5 cursor-pointer rounded border-taupe text-ink focus:ring-ink"
                  />
                  <label className="ml-3 text-sm text-ink-soft">
                    {t.rich('agree', {
                      terms: (chunks) => (
                        <Link href="/terms" className="font-semibold text-leaf hover:text-forest">{chunks}</Link>
                      ),
                      privacy: (chunks) => (
                        <Link href="/privacy" className="font-semibold text-leaf hover:text-forest">{chunks}</Link>
                      ),
                    })}
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-[1.35rem] bg-ink px-6 py-4 text-lg font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center">
                      <svg aria-hidden="true" className="-ml-1 mr-3 h-5 w-5 motion-safe:animate-spin text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t('submitting')}
                    </span>
                  ) : (
                    <>
                      {t('submit')}
                      <ArrowRight className="h-5 w-5" />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-8 text-center">
                <p className="text-ink-soft">
                  {t('haveAccount')}{' '}
                  <Link href="/signin" className="font-bold text-leaf transition-colors hover:text-forest">
                    {t('signIn')}
                  </Link>
                </p>
              </div>
            </div>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-sm text-ink-mute">
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

        <div className="relative hidden overflow-hidden rounded-[2.25rem] border border-black/10 bg-sand p-10 text-ink lg:flex lg:flex-col lg:justify-between">

          <div className="relative z-10">
            <h2 className="max-w-xl text-5xl font-semibold leading-tight text-ink">
              {t('setupLine1')}
              <span className="block text-leaf">{t('setupLine2')}</span>
            </h2>
            <p className="mt-6 max-w-md text-xl leading-relaxed text-ink-soft">
              {t('setupBody')}
            </p>
          </div>

          <div className="relative z-10 grid grid-cols-2 gap-4">
            {platformCapabilities.map((item) => {
              const Icon = item.icon

              return (
                <div key={item.title} className={`rounded-[1.5rem] border p-4 ${item.className}`}>
                  <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${item.iconClassName}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="mt-4 text-sm font-semibold text-ink">{item.title}</div>
                  <div className="mt-1 text-xs leading-relaxed text-ink-soft">{item.description}</div>
                </div>
              )
            })}
            <div className="rounded-[1.5rem] border border-ink/10 bg-white p-4">
              <div className="text-xs font-semibold text-ink-mute">
                {t('launchProfile')}
              </div>
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between gap-3 text-sm text-ink">
                  <span>{t('modelKeys')}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-leaf">
                    {t('optional')}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm text-ink">
                  <span>{t('openSource')}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-leaf">
                    {t('flexible')}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm text-ink">
                  <span>{t('selfHost')}</span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-leaf">
                    {t('secure')}
                  </span>
                </div>
              </div>
            </div>
          </div>


          <div className="relative z-10 flex flex-wrap gap-6 text-sm text-ink-mute">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-leaf" />
              <span>{t('bringKeys')}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-leaf" />
              <span>{t('openSource')}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-leaf" />
              <span>{t('selfHostReady')}</span>
            </div>
          </div>
        </div>
      </div>
    </AuthPageFrame>
  )
}
