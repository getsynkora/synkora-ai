'use client'

import { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'
import AuthPageFrame from '@/components/auth/AuthPageFrame'

function AcceptInviteContent() {
  const [isProcessing, setIsProcessing] = useState(true)
  const [isSuccess, setIsSuccess] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [teamName, setTeamName] = useState('')
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const acceptInvitation = async (token: string) => {
      try {
        const response = await apiClient.request('POST', '/api/v1/teams/invitations/accept', { token })

        setIsSuccess(true)
        const memberData = response.data || response
        setTeamName(memberData.team_name || 'the team')
        toast.success('Successfully joined the team!')

        // Redirect to dashboard after 3 seconds
        setTimeout(() => {
          router.push('/agents')
        }, 3000)
      } catch (err: any) {
        const errorMsg = extractErrorMessage(err, 'Failed to accept invitation')

        // Check if user needs to sign in
        if (err.response?.status === 401) {
          // Store the invitation URL to redirect back after login
          const returnUrl = `/accept-invite?token=${token}`
          sessionStorage.setItem('postLoginRedirect', returnUrl)
          router.push(`/signin?redirect=${encodeURIComponent(returnUrl)}`)
          return
        }

        setErrorMessage(errorMsg)
        toast.error(errorMsg)
        setIsProcessing(false)
      }
    }

    const tokenParam = searchParams.get('token')
    if (tokenParam) {
      acceptInvitation(tokenParam)
    } else {
      setIsProcessing(false)
      setErrorMessage('Invalid invitation link. No token provided.')
    }
  }, [searchParams, router])

  return (
    <AuthPageFrame>
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
        <div className="text-center mb-8">
          {isProcessing ? (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-red-500">
                <svg className="animate-spin h-10 w-10 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Accepting invitation</h1>
              <p className="text-gray-600">Please wait while we process your invitation...</p>
            </>
          ) : isSuccess ? (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-[#2d8b69]">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome to the team!</h1>
              <p className="text-gray-600">You have successfully joined {teamName}. Redirecting to dashboard...</p>
            </>
          ) : (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-[#191919]">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Invitation failed</h1>
              <p className="text-gray-600">{errorMessage}</p>
            </>
          )}
        </div>

        <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-[0_24px_60px_rgba(0,0,0,0.08)] sm:p-8">
          {isProcessing ? (
            <div className="text-center py-8">
              <div className="inline-block animate-pulse">
                <div className="h-2 w-48 bg-gray-200 rounded mb-3"></div>
                <div className="h-2 w-32 bg-gray-200 rounded mx-auto"></div>
              </div>
            </div>
          ) : isSuccess ? (
            <div className="text-center py-4">
              <p className="text-gray-600 mb-4">You can now access the team&apos;s agents and resources.</p>
              <Link
                href="/agents"
                className="inline-block w-full rounded-[1.1rem] bg-red-500 px-4 py-3 font-bold text-white transition-all"
              >
                Go to Dashboard
              </Link>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-gray-600 mb-4">
                {errorMessage.includes('expired') || errorMessage.includes('invalid')
                  ? 'The invitation link may have expired or is invalid. Please ask for a new invitation.'
                  : errorMessage.includes('different email')
                  ? 'Please sign in with the email address the invitation was sent to.'
                  : errorMessage.includes('already a member')
                  ? 'You are already a member of this team.'
                  : 'Please try again or contact the team administrator.'}
              </p>
              <div className="space-y-3">
                {errorMessage.includes('different email') && (
                  <Link
                    href="/signin"
                    className="inline-block w-full rounded-[1.1rem] bg-red-500 px-4 py-3 font-bold text-white transition-all"
                  >
                    Sign In with Different Account
                  </Link>
                )}
                {errorMessage.includes('already a member') && (
                  <Link
                    href="/agents"
                    className="inline-block w-full rounded-[1.1rem] bg-red-500 px-4 py-3 font-bold text-white transition-all"
                  >
                    Go to Dashboard
                  </Link>
                )}
                {!errorMessage.includes('already a member') && (
                  <Link
                    href="/signin"
                    className="inline-block w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-3 px-4 rounded-lg transition-colors"
                  >
                    Back to Sign In
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>

        {!isProcessing && (
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Need help?{' '}
              <a href={`mailto:${process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@localhost'}`} className="font-medium text-red-600 hover:text-red-700">
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

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-red-500"></div>
        </div>
      </AuthPageFrame>
    }>
      <AcceptInviteContent />
    </Suspense>
  )
}
