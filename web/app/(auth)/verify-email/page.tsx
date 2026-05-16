'use client'

import { useState, useEffect, Suspense } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import axios from 'axios'
import AuthPageFrame from '@/components/auth/AuthPageFrame'

function VerifyEmailContent() {
  const [isVerifying, setIsVerifying] = useState(true)
  const [isSuccess, setIsSuccess] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const verifyEmail = async (verificationToken: string) => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        await axios.post(`${apiUrl}/console/api/auth/verify-email`, {
          token: verificationToken
        })

        setIsSuccess(true)
        toast.success('Email verified successfully!')

        // Redirect to signin after 3 seconds
        setTimeout(() => {
          router.push('/signin')
        }, 3000)
      } catch (err: any) {
        const errorMsg = extractErrorMessage(err, 'Failed to verify email')
        setErrorMessage(errorMsg)
        toast.error(errorMsg)
      } finally {
        setIsVerifying(false)
      }
    }

    const tokenParam = searchParams.get('token')
    if (tokenParam) {
      verifyEmail(tokenParam)
    } else {
      setIsVerifying(false)
      setErrorMessage('Invalid verification link')
    }
  }, [searchParams, router])

  return (
    <AuthPageFrame>
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
        <div className="text-center mb-8">
          {isVerifying ? (
            <>
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-red-500">
                <svg className="animate-spin h-10 w-10 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Verifying your email</h1>
              <p className="text-gray-600">Please wait while we verify your email address...</p>
            </>
          ) : isSuccess ? (
            <>
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-[#2d8b69]">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Email verified!</h1>
              <p className="text-gray-600">Your email has been successfully verified. Redirecting to sign in...</p>
            </>
          ) : (
            <>
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-[#191919]">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Verification failed</h1>
              <p className="text-gray-600">{errorMessage}</p>
            </>
          )}
        </div>

        <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-[0_24px_60px_rgba(0,0,0,0.08)] sm:p-8">
          {isVerifying ? (
            <div className="text-center py-8">
              <div className="inline-block animate-pulse">
                <div className="h-2 w-48 bg-red-100 rounded mb-3"></div>
                <div className="h-2 w-32 bg-red-100 rounded mx-auto"></div>
              </div>
            </div>
          ) : isSuccess ? (
            <div className="text-center py-4">
              <p className="text-gray-600 mb-6">You can now sign in to your account.</p>
              <Link
                href="/signin"
                className="inline-flex w-full items-center justify-center rounded-[1.2rem] bg-red-500 px-4 py-3.5 font-bold text-white transition-all"
              >
                Go to Sign In
              </Link>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-gray-600 mb-6">
                {errorMessage.includes('expired') || errorMessage.includes('invalid')
                  ? 'The verification link may have expired or is invalid.'
                  : 'Please try again or contact support if the problem persists.'}
              </p>
              <div className="space-y-3">
                <Link
                  href="/signup"
                  className="inline-flex w-full items-center justify-center rounded-[1.2rem] bg-red-500 px-4 py-3.5 font-bold text-white transition-all"
                >
                  Sign Up Again
                </Link>
                <Link
                  href="/signin"
                  className="inline-flex items-center justify-center w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3.5 px-4 rounded-xl transition-colors"
                >
                  Back to Sign In
                </Link>
              </div>
            </div>
          )}
        </div>

        {!isVerifying && (
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Need help?{' '}
              <a href={`mailto:${process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@localhost'}`} className="font-semibold text-red-600 hover:text-red-700">
                Contact support
              </a>
            </p>
          </div>
        )}
        </div>
      </div>
    </AuthPageFrame>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-red-500"></div>
        </div>
      </AuthPageFrame>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
