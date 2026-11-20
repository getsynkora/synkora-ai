'use client'

import { useState, useEffect, Suspense } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import axios from 'axios'
import AuthPageFrame from '@/components/auth/AuthPageFrame'
import { useTranslations } from 'next-intl'

function VerifyEmailContent() {
  const t = useTranslations('auth.verifyEmail')
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
        toast.success(t('verifiedToast'))

        // Redirect to signin after 3 seconds
        setTimeout(() => {
          router.push('/signin')
        }, 3000)
      } catch (err: any) {
        const errorMsg = extractErrorMessage(err, t('failed'))
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
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-ink">
                <svg aria-hidden="true" className="motion-safe:animate-spin h-10 w-10 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('verifying')}</h1>
              <p className="text-ink-soft">{t('pleaseWait')}</p>
            </>
          ) : isSuccess ? (
            <>
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-leaf">
                <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('verified')}</h1>
              <p className="text-ink-soft">{t('redirecting')}</p>
            </>
          ) : (
            <>
              <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-[1.75rem] bg-ink">
                <svg aria-hidden="true" className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-3xl font-bold text-ink mb-2">{t('verificationFailed')}</h1>
              <p className="text-ink-soft">{errorMessage}</p>
            </>
          )}
        </div>

        <div className="rounded-[1.9rem] border border-black/10 bg-white p-5 shadow-soft sm:p-8">
          {isVerifying ? (
            <div className="text-center py-8">
              <div className="inline-block motion-safe:animate-pulse">
                <div className="h-2 w-48 bg-blush-wash rounded mb-3"></div>
                <div className="h-2 w-32 bg-blush-wash rounded mx-auto"></div>
              </div>
            </div>
          ) : isSuccess ? (
            <div className="text-center py-4">
              <p className="text-ink-soft mb-6">{t('canSignIn')}</p>
              <Link
                href="/signin"
                className="inline-flex w-full items-center justify-center rounded-[1.2rem] bg-ink px-4 py-3.5 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              >
                {t('goToSignIn')}
              </Link>
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-ink-soft mb-6">
                {errorMessage.includes('expired') || errorMessage.includes('invalid')
                  ? t('linkExpired')
                  : t('tryAgain')}
              </p>
              <div className="space-y-3">
                <Link
                  href="/signup"
                  className="inline-flex w-full items-center justify-center rounded-[1.2rem] bg-ink px-4 py-3.5 font-bold text-white transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                >
                  {t('signUpAgain')}
                </Link>
                <Link
                  href="/signin"
                  className="inline-flex items-center justify-center w-full bg-sand hover:bg-line text-ink-soft font-semibold py-3.5 px-4 rounded-xl transition-colors"
                >
                  {t('backToSignIn')}
                </Link>
              </div>
            </div>
          )}
        </div>

        {!isVerifying && (
          <div className="mt-6 text-center">
            <p className="text-sm text-ink-soft">
              {t('needHelp')}{' '}
              <a href={`mailto:${process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@localhost'}`} className="font-semibold text-leaf hover:text-forest">
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

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <AuthPageFrame>
        <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center">
          <div className="h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink"></div>
        </div>
      </AuthPageFrame>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
