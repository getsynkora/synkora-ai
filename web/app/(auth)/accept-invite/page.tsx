'use client'

import { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import { extractErrorMessage } from '@/lib/api/error'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { useTranslations } from 'next-intl'

function AcceptInviteContent() {
  const t = useTranslations('auth.acceptInvite')
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
        toast.success(t('joinedToast'))

        // Redirect to dashboard after 3 seconds
        setTimeout(() => {
          router.push('/agents')
        }, 3000)
      } catch (err: any) {
        const errorMsg = extractErrorMessage(err, t('failed'))

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
      setErrorMessage(t('noToken'))
    }
  }, [searchParams, router])

  return (
    <AuthPageFrame>
      <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
        <div className="text-center mb-8">
          {isProcessing ? (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-ink">
                <svg aria-hidden="true" className="motion-safe:animate-spin h-10 w-10 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('accepting')}</h1>
              <p className="text-ink-soft">{t('pleaseWait')}</p>
            </>
          ) : isSuccess ? (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-leaf">
                <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('welcome')}</h1>
              <p className="text-ink-soft">{t('joined', { team: teamName })}</p>
            </>
          ) : (
            <>
              <div className="mb-4 inline-flex h-16 w-16 items-center justify-center rounded-[1.5rem] bg-ink">
                <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('invitationFailed')}</h1>
              <p className="text-ink-soft">{errorMessage}</p>
            </>
          )}
        </div>

        <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-soft sm:p-8">
          {isProcessing ? (
            <div className="text-center py-8">
              <div className="inline-block motion-safe:animate-pulse">
                <div className="h-2 w-48 bg-line rounded mb-3"></div>
                <div className="h-2 w-32 bg-line rounded mx-auto"></div>
              </div>
            </div>
          ) : isSuccess ? (
            <div className="text-center py-4">
              <p className="text-ink-soft mb-4">{t('canAccess')}</p>
              <Link
                href="/agents"
                className="inline-block w-full rounded-[1.1rem] bg-ink px-4 py-3 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              >
                {t('goToDashboard')}
              </Link>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-ink-soft mb-4">
                {errorMessage.includes('expired') || errorMessage.includes('invalid')
                  ? t('linkExpired')
                  : errorMessage.includes('different email')
                  ? t('differentEmail')
                  : errorMessage.includes('already a member')
                  ? t('alreadyMember')
                  : t('tryAgain')}
              </p>
              <div className="space-y-3">
                {errorMessage.includes('different email') && (
                  <Link
                    href="/signin"
                    className="inline-block w-full rounded-[1.1rem] bg-ink px-4 py-3 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                  >
                    {t('differentAccount')}
                  </Link>
                )}
                {errorMessage.includes('already a member') && (
                  <Link
                    href="/agents"
                    className="inline-block w-full rounded-[1.1rem] bg-ink px-4 py-3 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                  >
                    {t('goToDashboard')}
                  </Link>
                )}
                {!errorMessage.includes('already a member') && (
                  <Link
                    href="/signin"
                    className="inline-block w-full bg-sand hover:bg-line text-ink-soft font-medium py-3 px-4 rounded-lg transition-colors"
                  >
                    {t('backToSignIn')}
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>

        {!isProcessing && (
          <div className="mt-6 text-center">
            <p className="text-sm text-ink-soft">
              {t('needHelp')}{' '}
              <a href={`mailto:${process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@localhost'}`} className="font-medium text-leaf hover:text-forest">
                {t('contactSupport')}
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
          <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
        </div>
      </AuthPageFrame>
    }>
      <AcceptInviteContent />
    </Suspense>
  )
}
