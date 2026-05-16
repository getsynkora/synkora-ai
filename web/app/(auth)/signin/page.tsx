'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useAuth } from '@/lib/hooks/useAuth'
import { secureStorage } from '@/lib/auth/secure-storage'
import { SocialLoginButton } from '@/components/social-auth'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { Bot, KeyRound, Layers3, Shield, Sparkles, Workflow } from 'lucide-react'

function SignInContent() {
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
          toast.success(`Signed in successfully with ${provider}!`)
          window.location.href = redirectUrl ? decodeURIComponent(redirectUrl) : '/agents'
        })
        .catch(() => {
          const msg = 'Sign-in failed. Please try again.'
          setError(msg)
          toast.error(msg)
        })
    } else if (loginStatus === 'error') {
      const message = searchParams.get('message') || 'Social login failed'
      toast.error(message)
      setError(message)
    }
  }, [redirectUrl, searchParams, router])

  // Show loader while checking auth state — must be after all hooks
  if (isLoading && !isSubmitting) {
    return (
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-red-500"></div>
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
      toast.success('Signed in successfully!')
      // Redirect to original page or default to dashboard
      const targetUrl = redirectUrl ? decodeURIComponent(redirectUrl) : '/dashboard'
      router.push(targetUrl)
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'string'
            ? err.response.data.detail
            : 'Invalid email or password')
        : err.message || 'Failed to sign in'
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
      title: 'Agents',
      description: 'Manage active agents, prompts, and deployment states.',
      className: 'border-[#7de5c1]/20 bg-[#7de5c1]/12',
      iconClassName: 'bg-[#7de5c1] text-[#101915]',
    },
    {
      icon: Workflow,
      title: 'Workflows',
      description: 'Track tools, channels, and production automations.',
      className: 'border-white/10 bg-white/[0.08]',
      iconClassName: 'bg-white/12 text-[#f7f2e7]',
    },
    {
      icon: Layers3,
      title: 'Knowledge',
      description: 'Keep retrieval, documents, and sources aligned.',
      className: 'border-[#f6c794]/18 bg-[#f6c794]/10',
      iconClassName: 'bg-[#f6c794] text-[#2f2414]',
    },
  ]

  return (
    <AuthPageFrame>
      <div className="grid gap-6 lg:min-h-[calc(100vh-10rem)] lg:grid-cols-[1.08fr_0.92fr]">
        <div className="relative hidden overflow-hidden rounded-[2.25rem] border border-black/10 bg-[#151515] p-10 text-[#f7f2e7] shadow-[0_32px_80px_rgba(0,0,0,0.22)] lg:flex lg:flex-col lg:justify-between">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(125,229,193,0.24),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(255,255,255,0.12),transparent_28%)]" />
          <div className="absolute -right-12 top-12 h-40 w-40 rounded-full border border-white/10 bg-white/5 blur-2xl" />
          <div className="absolute -left-12 top-12 h-32 w-32 rounded-[2.25rem] border border-white/10 bg-white/[0.03]" />
          <div className="absolute bottom-8 right-8 h-28 w-28 rounded-full border border-white/8 bg-[radial-gradient(circle,rgba(255,255,255,0.08),transparent_70%)] blur-md" />

          <div className="relative z-10">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/8 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[#d8d0c3]">
              <Sparkles className="h-4 w-4 text-[#7de5c1]" />
              Workspace Access
            </div>

            <h2 className="max-w-xl text-4xl font-semibold leading-tight text-white">
              Return to your
              <span className="block text-[#7de5c1]">platform workspace</span>
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-[#c8c0b5]">
              Sign in to manage agents, knowledge, tools, and delivery channels from one control layer.
            </p>
          </div>

          <div className="relative z-10 my-10 space-y-4">
            <div className="rounded-[1.85rem] border border-white/10 bg-white/[0.08] p-6 backdrop-blur-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold uppercase tracking-[0.18em] text-[#d8d0c3]">
                    Session-ready platform
                  </div>
                  <p className="mt-3 max-w-lg text-base leading-relaxed text-[#c8c0b5]">
                    Pick up where you left off across orchestration, retrieval, and shipping surfaces.
                  </p>
                </div>
                <div className="rounded-full border border-white/10 bg-white/[0.08] px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-[#f7f2e7]">
                  Live
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {workspaceSignals.map((signal) => {
                const Icon = signal.icon

                return (
                  <div
                    key={signal.title}
                    className={`rounded-[1.65rem] border p-5 backdrop-blur-sm ${signal.className}`}
                  >
                    <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${signal.iconClassName}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="mt-4 text-base font-semibold text-white">{signal.title}</div>
                    <div className="mt-2 text-sm leading-relaxed text-[#c8c0b5]">{signal.description}</div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="relative z-10 flex flex-wrap gap-3 pt-2">
            <div className="rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-medium text-[#f7f2e7] backdrop-blur-sm">
              Bring your LLM keys
            </div>
            <div className="rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-medium text-[#f7f2e7] backdrop-blur-sm">
              Open-source core
            </div>
            <div className="rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-medium text-[#f7f2e7] backdrop-blur-sm">
              Self-host ready
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center py-2 lg:py-8">
          <div className="w-full max-w-xl">
            <div className="mb-8">
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
                <KeyRound className="h-3.5 w-3.5 text-[#2d8b69]" />
                Sign in
              </div>
              <h1 className="mt-5 text-3xl font-semibold tracking-tight text-gray-900 sm:text-5xl">Sign in</h1>
              <p className="mt-3 text-base text-gray-600 sm:text-lg">
                Access your agents, workflows, and platform workspace.
              </p>
            </div>

            <div className="rounded-[2rem] border border-black/10 bg-white p-6 shadow-[0_28px_70px_rgba(0,0,0,0.08)] sm:p-8">
              <div className="mb-8">
                <SocialLoginButton
                  provider="google"
                  onClick={() => handleSocialLogin('google')}
                  variant="full"
                />
              </div>

              <div className="relative my-8">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-white px-4 font-medium text-gray-500">or continue with email</span>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {error && (
                  <div className="flex items-center gap-2 rounded-[1.25rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <svg className="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-semibold text-gray-700">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="Enter your email"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="mb-2 block text-sm font-semibold text-gray-700">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="Enter your password"
                  />
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <label className="flex items-center text-sm text-gray-600">
                    <input
                      type="checkbox"
                      className="h-5 w-5 cursor-pointer rounded border-gray-300 text-red-500 focus:ring-red-500"
                    />
                    <span className="ml-2">Remember me</span>
                  </label>
                  <Link href="/forgot-password" className="text-sm font-semibold text-red-500 transition-colors hover:text-red-600">
                    Forgot password?
                  </Link>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full rounded-[1.35rem] bg-red-500 px-6 py-4 text-lg font-bold text-white transition-all disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <span className="flex items-center justify-center">
                      <svg className="-ml-1 mr-3 h-5 w-5 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Signing in...
                    </span>
                  ) : (
                    'Sign in'
                  )}
                </button>
              </form>

              <div className="mt-8 text-center">
                <p className="text-gray-600">
                  Don&apos;t have an account?{' '}
                  <Link href="/signup" className="font-bold text-red-500 transition-colors hover:text-red-600">
                    Sign up for free
                  </Link>
                </p>
              </div>
            </div>

            <p className="mt-8 text-center text-sm text-gray-500">
              By signing in, you agree to our{' '}
              <Link href="/terms" className="font-medium text-red-500 hover:text-red-600">Terms</Link>
              {' '}and{' '}
              <Link href="/privacy" className="font-medium text-red-500 hover:text-red-600">Privacy Policy</Link>
            </p>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm text-gray-500">
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <Shield className="h-4 w-4" />
                <span>256-bit SSL</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Data encrypted at rest</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2">
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Your data stays private</span>
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
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-red-500"></div>
        </div>
      </AuthPageFrame>
    }>
      <SignInContent />
    </Suspense>
  )
}
