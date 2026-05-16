'use client'

import { useState, useMemo, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useAuth } from '@/lib/hooks/useAuth'
import { SocialLoginButton } from '@/components/social-auth'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { ArrowRight, Bot, Check, CheckCircle2, Database, KeyRound, Shield, Sparkles, Workflow, X } from 'lucide-react'

interface PasswordRequirement {
  label: string
  test: (password: string) => boolean
}

const passwordRequirements: PasswordRequirement[] = [
  { label: 'At least 12 characters', test: (p) => p.length >= 12 },
  { label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { label: 'One number', test: (p) => /\d/.test(p) },
  { label: 'One special character', test: (p) => /[!@#$%^&*(),.?":{}|<>\[\]\\;'`~_+=\-/]/.test(p) },
]

export default function SignUpPage() {
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
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-red-500"></div>
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
      setError('Password does not meet all requirements')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setIsLoading(true)

    try {
      await signUp(email, password, name)
      toast.success('Account created successfully! Please check your email to verify your account.')
      router.push('/signin')
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail
        ? (Array.isArray(err.response.data.detail)
            ? err.response.data.detail.map((e: any) => e.msg).join(', ')
            : err.response.data.detail)
        : err.message || 'Failed to sign up'
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
      title: 'Agents',
      description: 'Ship task-specific agents with configurable behavior and memory.',
      className: 'border-[#7de5c1]/18 bg-[#7de5c1]/10',
      iconClassName: 'bg-[#7de5c1] text-[#101915]',
    },
    {
      icon: Database,
      title: 'Knowledge',
      description: 'Connect documents, sources, and retrieval pipelines in one place.',
      className: 'border-white/10 bg-white/[0.08]',
      iconClassName: 'bg-white/12 text-[#f7f2e7]',
    },
    {
      icon: Workflow,
      title: 'Workflows',
      description: 'Route tools, channels, and automation without fragmentation.',
      className: 'border-[#f6c794]/18 bg-[#f6c794]/10',
      iconClassName: 'bg-[#f6c794] text-[#2f2414]',
    },
  ]

  return (
    <AuthPageFrame>
      <div className="grid gap-6 lg:min-h-[calc(100vh-10rem)] lg:grid-cols-[0.92fr_1.08fr]">
        <div className="flex items-center justify-center py-2 lg:py-8">
          <div className="w-full max-w-xl">
            <div className="mb-8">
              <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
                <Sparkles className="h-3.5 w-3.5 text-[#2d8b69]" />
                Build on Synkora
              </div>
              <h1 className="mt-5 text-3xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
                Create your platform workspace
              </h1>
              <p className="mt-3 text-base text-gray-600 sm:text-lg">
                Build agents, workflows, and LLM-powered products from one workspace.
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

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="flex items-center gap-2 rounded-[1.25rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <svg className="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="name" className="mb-2 block text-sm font-semibold text-gray-700">
                    Full name
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="Enter your full name"
                  />
                </div>

                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-semibold text-gray-700">
                    Work email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="you@company.com"
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
                    onFocus={() => setShowPasswordRequirements(true)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="Create a strong password"
                  />
                  {showPasswordRequirements && password.length > 0 && (
                    <div className="mt-3 space-y-1.5 rounded-[1.15rem] border border-black/10 bg-[#f4efe4] p-3">
                      {passwordValidation.map((req, idx) => (
                        <div key={idx} className="flex items-center gap-1.5">
                          {req.met ? (
                            <Check className="h-3.5 w-3.5 flex-shrink-0 text-green-500" />
                          ) : (
                            <X className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
                          )}
                          <span className={`text-xs ${req.met ? 'text-green-600' : 'text-gray-500'}`}>
                            {req.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {!showPasswordRequirements || password.length === 0 ? (
                    <p className="mt-2 text-xs text-gray-500">
                      Min 12 characters with uppercase, lowercase, number & special character
                    </p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="mb-2 block text-sm font-semibold text-gray-700">
                    Confirm password
                  </label>
                  <input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                    placeholder="Confirm your password"
                  />
                  {confirmPassword.length > 0 && (
                    <div className="mt-2 flex items-center gap-1.5">
                      {passwordsMatch ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-green-500" />
                          <span className="text-xs text-green-600">Passwords match</span>
                        </>
                      ) : (
                        <>
                          <X className="h-3.5 w-3.5 text-red-500" />
                          <span className="text-xs text-red-500">Passwords do not match</span>
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-start pt-2">
                  <input
                    type="checkbox"
                    required
                    className="mt-0.5 h-5 w-5 cursor-pointer rounded border-gray-300 text-red-500 focus:ring-red-500"
                  />
                  <label className="ml-3 text-sm text-gray-600">
                    I agree to the{' '}
                    <Link href="/terms" className="font-semibold text-red-500 hover:text-red-600">
                      Terms of Service
                    </Link>
                    {' '}and{' '}
                    <Link href="/privacy" className="font-semibold text-red-500 hover:text-red-600">
                      Privacy Policy
                    </Link>
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-[1.35rem] bg-red-500 px-6 py-4 text-lg font-bold text-white transition-all disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center">
                      <svg className="-ml-1 mr-3 h-5 w-5 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Creating account...
                    </span>
                  ) : (
                    <>
                      Create account
                      <ArrowRight className="h-5 w-5" />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-8 text-center">
                <p className="text-gray-600">
                  Already have an account?{' '}
                  <Link href="/signin" className="font-bold text-red-500 transition-colors hover:text-red-600">
                    Sign in
                  </Link>
                </p>
              </div>
            </div>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-sm text-gray-500">
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

        <div className="relative hidden overflow-hidden rounded-[2.25rem] border border-black/10 bg-[#151515] p-10 text-[#f7f2e7] shadow-[0_32px_80px_rgba(0,0,0,0.22)] lg:flex lg:flex-col lg:justify-between">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(125,229,193,0.24),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(255,255,255,0.12),transparent_28%)]" />
          <div className="absolute right-10 top-10 h-40 w-40 rounded-full bg-[#7de5c1]/10 blur-3xl" />
          <div className="absolute -left-12 top-12 h-32 w-32 rounded-[2.25rem] border border-white/10 bg-white/[0.03]" />
          <div className="absolute bottom-8 right-8 h-28 w-28 rounded-full border border-white/8 bg-[radial-gradient(circle,rgba(255,255,255,0.08),transparent_70%)] blur-md" />

          <div className="relative z-10">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/8 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[#d8d0c3]">
              <KeyRound className="h-4 w-4 text-[#7de5c1]" />
              Platform Setup
            </div>
            <h2 className="max-w-xl text-5xl font-semibold leading-tight text-white">
              Build your
              <span className="block text-[#7de5c1]">AI platform stack</span>
            </h2>
            <p className="mt-6 max-w-md text-xl leading-relaxed text-[#c8c0b5]">
              Launch agents, tools, knowledge, and delivery surfaces without stitching together five separate products.
            </p>
          </div>

          <div className="relative z-10 grid grid-cols-2 gap-4">
            {platformCapabilities.map((item) => {
              const Icon = item.icon

              return (
                <div key={item.title} className={`rounded-[1.5rem] border p-4 backdrop-blur-sm ${item.className}`}>
                  <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${item.iconClassName}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="mt-4 text-sm font-semibold text-white">{item.title}</div>
                  <div className="mt-1 text-xs leading-relaxed text-[#c8c0b5]">{item.description}</div>
                </div>
              )
            })}
            <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.06] p-4 backdrop-blur-sm">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#d8d0c3]">
                Launch profile
              </div>
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between gap-3 text-sm text-[#f7f2e7]">
                  <span>Bring your model keys</span>
                  <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7de5c1]">
                    Optional
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm text-[#f7f2e7]">
                  <span>Open-source core</span>
                  <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#f6c794]">
                    Flexible
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm text-[#f7f2e7]">
                  <span>Self-host when needed</span>
                  <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#f2b8bc]">
                    Secure
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="relative z-10 rounded-[1.9rem] border border-white/10 bg-white/10 p-6 backdrop-blur-lg">
            <div className="mb-4 flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <svg key={i} className="h-5 w-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
            <p className="mb-4 leading-relaxed text-white/90">
              &quot;Synkora gave us a single platform for agents, retrieval, and delivery. We went from disconnected experiments to a real product stack.&quot;
            </p>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#7de5c1] font-bold text-[#101915]">
                A
              </div>
              <div>
                <div className="font-semibold text-white">Avery Chen</div>
                <div className="text-sm text-[#c8c0b5]">Platform Lead, Northstar AI</div>
              </div>
            </div>
          </div>

          <div className="relative z-10 flex flex-wrap gap-6 text-sm text-gray-300">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-[#7de5c1]" />
              <span>Bring your LLM keys</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-[#7de5c1]" />
              <span>Open-source core</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-[#7de5c1]" />
              <span>Self-host ready</span>
            </div>
          </div>
        </div>
      </div>
    </AuthPageFrame>
  )
}
