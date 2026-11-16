import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { describe, expect, it, vi } from 'vitest'
import en from '../../../../messages/en.json'
import de from '../../../../messages/de.json'
import { ChatMessage } from '../ChatMessage'
import type { Message } from '../../types'

vi.mock('@/lib/api/client', () => ({ apiClient: {} }))
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const messages = { en, de }

function show(locale: 'en' | 'de', message: Message, props: Record<string, unknown> = {}) {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages[locale]}>
      <ChatMessage message={message} {...props} />
    </NextIntlClientProvider>,
  )
}

const reply: Message = { id: '1', role: 'assistant', content: 'Hello there', timestamp: new Date() }
const question: Message = { id: '2', role: 'user', content: 'Hi', timestamp: new Date() }

describe('ChatMessage language', () => {
  it('labels a reply in German', () => {
    show('de', reply, { onCopy: vi.fn(), onRetry: vi.fn(), onFeedback: vi.fn() })

    expect(screen.getByTitle('Hilfreich')).toBeInTheDocument()
    expect(screen.getByTitle('Nicht hilfreich')).toBeInTheDocument()
    expect(screen.getByTitle('Neu generieren')).toBeInTheDocument()
    expect(screen.queryByTitle('Helpful')).not.toBeInTheDocument()
  })

  it('labels the same reply in English', () => {
    show('en', reply, { onCopy: vi.fn(), onRetry: vi.fn(), onFeedback: vi.fn() })

    expect(screen.getByTitle('Helpful')).toBeInTheDocument()
    expect(screen.getByTitle('Regenerate')).toBeInTheDocument()
  })

  it("shows a person's own message with German actions and time", () => {
    show('de', question, { onDelete: vi.fn() })

    expect(screen.getByTitle('Nachricht löschen')).toBeInTheDocument()
    expect(screen.getByTitle('Nachricht kopieren')).toBeInTheDocument()
    expect(screen.getByText('Sie')).toBeInTheDocument()
    expect(screen.getByText('Gerade eben')).toBeInTheDocument()
  })

  it('says "Just now" in English', () => {
    show('en', question)

    expect(screen.getByText('Just now')).toBeInTheDocument()
    expect(screen.getByText('You')).toBeInTheDocument()
  })

  it('formats older times with the language', () => {
    const older = { ...question, timestamp: new Date(Date.now() - 3 * 3600_000) }
    show('de', older)

    expect(screen.getByText('vor 3 Std.')).toBeInTheDocument()
  })
})
