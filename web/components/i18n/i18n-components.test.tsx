import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import en from '../../messages/en.json'
import de from '../../messages/de.json'

const refresh = vi.fn()
const request = vi.fn()
let authenticated = false

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh, push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock('@/lib/api/client', () => ({ apiClient: { request: (...args: unknown[]) => request(...args) } }))
vi.mock('@/lib/store/authStore', () => ({
  useAuthStore: (select: (state: { isAuthenticated: boolean }) => unknown) => select({ isAuthenticated: authenticated }),
}))

vi.mock('axios', () => ({ default: { post: vi.fn() } }))
vi.mock('@/lib/api/error', () => ({ extractErrorMessage: () => 'error' }))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/components/auth/AuthPageFrame', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))


import { LanguageSwitcher } from './LanguageSwitcher'
import { useSyncAccountLanguage } from './useSyncAccountLanguage'

const messages = { en, de }

function withIntl(locale: 'en' | 'de', ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages[locale]}>
      {ui}
    </NextIntlClientProvider>
  )
}

function clearCookie() {
  document.cookie = 'NEXT_LOCALE=; path=/; max-age=0'
}

beforeEach(() => {
  refresh.mockClear()
  request.mockReset()
  request.mockResolvedValue({})
  authenticated = false
  clearCookie()
})

describe('LanguageSwitcher', () => {
  it('shows each language in its own name, with the current one selected', () => {
    render(withIntl('de', <LanguageSwitcher />))

    expect(screen.getByRole('combobox')).toHaveValue('de')
    expect(screen.getByRole('option', { name: 'English' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Deutsch' })).toBeInTheDocument()
    expect(screen.getByLabelText('Sprache')).toBeInTheDocument()
  })

  it('remembers the choice and refreshes, without calling the API when signed out', async () => {
    render(withIntl('en', <LanguageSwitcher />))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'de' } })

    expect(document.cookie).toContain('NEXT_LOCALE=de')
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(request).not.toHaveBeenCalled()
  })

  it('also saves the language on the account when signed in', async () => {
    authenticated = true
    render(withIntl('en', <LanguageSwitcher />))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'de' } })

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith('PUT', '/api/v1/profile/me', { interface_language: 'de' }),
    )
  })

  it('keeps the choice in this browser if saving it fails', async () => {
    authenticated = true
    request.mockRejectedValue(new Error('offline'))
    render(withIntl('en', <LanguageSwitcher />))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'de' } })

    await waitFor(() => expect(request).toHaveBeenCalled())
    expect(document.cookie).toContain('NEXT_LOCALE=de')
    expect(refresh).toHaveBeenCalled()
  })

  it('ignores picking the language already shown', () => {
    render(withIntl('en', <LanguageSwitcher />))

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'en' } })

    expect(refresh).not.toHaveBeenCalled()
    expect(document.cookie).not.toContain('NEXT_LOCALE')
  })
})

function Probe({ language }: { language: string | undefined }) {
  useSyncAccountLanguage(language)
  return null
}

describe('useSyncAccountLanguage', () => {
  it("applies the account's language to a browser that has not chosen one", () => {
    render(withIntl('en', <Probe language="de" />))

    expect(document.cookie).toContain('NEXT_LOCALE=de')
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('leaves a language chosen in this browser alone', () => {
    document.cookie = 'NEXT_LOCALE=en; path=/'
    render(withIntl('en', <Probe language="de" />))

    expect(document.cookie).toContain('NEXT_LOCALE=en')
    expect(refresh).not.toHaveBeenCalled()
  })

  it('does nothing when the account language is already shown or unknown', () => {
    const { rerender } = render(withIntl('de', <Probe language="de" />))
    rerender(withIntl('de', <Probe language="fr" />))
    rerender(withIntl('de', <Probe language={undefined} />))

    expect(refresh).not.toHaveBeenCalled()
  })
})

describe('a translated page', () => {
  it('renders the forgot-password page in German', async () => {
    const { default: ForgotPasswordPage } = await import('../../app/(auth)/forgot-password/page')
    render(withIntl('de', <ForgotPasswordPage />))

    expect(screen.getByRole('heading', { name: 'Passwort vergessen?' })).toBeInTheDocument()
    expect(screen.getByText('E-Mail-Adresse')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Link zum Zurücksetzen senden' })).toBeInTheDocument()
    expect(screen.queryByText('Forgot password?')).not.toBeInTheDocument()
  })

  it('renders the same page in English', async () => {
    const { default: ForgotPasswordPage } = await import('../../app/(auth)/forgot-password/page')
    render(withIntl('en', <ForgotPasswordPage />))

    expect(screen.getByRole('heading', { name: 'Forgot password?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send reset link' })).toBeInTheDocument()
  })
})
