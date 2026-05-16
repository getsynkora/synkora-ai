'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { secureStorage } from '@/lib/auth/secure-storage'
import AuthPageFrame from '@/components/auth/AuthPageFrame'

type Status = 'loading' | 'authorizing' | 'success' | 'needs_login' | 'error'

function ExtensionAuthContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const code_challenge = searchParams.get('code_challenge')
    const code_challenge_method = searchParams.get('code_challenge_method') ?? 'S256'
    const state = searchParams.get('state')
    const redirect_uri = searchParams.get('redirect_uri')

    if (!code_challenge || !state || !redirect_uri) {
      setError('Invalid authorization request — missing required parameters.')
      setStatus('error')
      return
    }

    const token = secureStorage.getAccessToken()
    if (!token) {
      // Not logged in — send to signin with return URL
      const returnTo = encodeURIComponent(window.location.href)
      router.replace(`/signin?redirect=${returnTo}`)
      return
    }

    // Logged in — call the API with Bearer token
    setStatus('authorizing')
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:5001'
    const params = new URLSearchParams({ code_challenge, code_challenge_method, state, redirect_uri })

    fetch(`${apiUrl}/console/api/auth/extension/authorize?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.code) throw new Error(data.detail ?? 'Authorization failed')
        setStatus('success')
        // Include api_url so the extension can call the API directly for token exchange
        const callbackParams = new URLSearchParams({
          code: data.code,
          state: data.state ?? state,
          api_url: apiUrl,
        })
        window.location.href = `${redirect_uri}?${callbackParams}`
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Authorization failed')
        setStatus('error')
      })
  }, [searchParams, router])

  if (status === 'loading' || status === 'authorizing') {
    return (
      <div className="flex flex-col items-center gap-3">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-red-500 border-t-transparent" />
        <p className="text-sm text-gray-500">
          {status === 'authorizing' ? 'Authorizing extension…' : 'Loading…'}
        </p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#d9f3ea]">
          <svg className="h-5 w-5 text-[#2d8b69]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-800">Authorized! Returning to extension…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
        <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
      <p className="text-sm font-medium text-gray-800">Authorization failed</p>
      <p className="text-xs text-gray-500 text-center">{error}</p>
    </div>
  )
}

export default function ExtensionAuthPage() {
  return (
    <AuthPageFrame>
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
        <div className="flex w-80 flex-col items-center gap-6 rounded-[1.9rem] border border-black/10 bg-white p-8 shadow-[0_24px_60px_rgba(0,0,0,0.08)]">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500">
              <span className="text-sm font-bold text-white">S</span>
            </div>
            <span className="text-sm font-semibold text-gray-800">Synkora</span>
          </div>
          <div className="text-center">
            <p className="mb-1 text-sm font-medium text-gray-800">Connecting browser extension</p>
            <p className="text-xs text-gray-400">You will be redirected back automatically</p>
          </div>
          <Suspense fallback={<div className="h-6 w-6 animate-spin rounded-full border-2 border-red-500 border-t-transparent" />}>
            <ExtensionAuthContent />
          </Suspense>
        </div>
      </div>
    </AuthPageFrame>
  )
}
