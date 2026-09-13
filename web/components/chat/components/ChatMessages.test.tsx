import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ChatMessages } from './ChatMessages'
import type { Message } from '../types'

vi.mock('./ChatMessage', () => ({
  ChatMessage: ({ message, isStreaming }: { message: Message; isStreaming: boolean }) => (
    <div data-testid="message" data-streaming={isStreaming}>{message.content}</div>
  ),
}))

const history = Array.from({ length: 125 }, (_, index): Message => ({
  id: String(index), role: 'assistant', content: `message ${index}`, timestamp: new Date(0),
}))

describe('chat history pagination', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('renders recent history and keeps the live message visible', () => {
    render(<ChatMessages messages={history} isStreaming conversationId="one" />)
    expect(screen.getAllByTestId('message')).toHaveLength(50)
    expect(screen.queryByText('message 0')).not.toBeInTheDocument()
    expect(screen.getByText('message 124')).toHaveAttribute('data-streaming', 'true')
    expect(screen.getByText('message 123')).toHaveAttribute('data-streaming', 'false')
  })

  it('allows older messages to be read without losing recent ones', () => {
    render(<ChatMessages messages={history} conversationId="one" />)
    fireEvent.click(screen.getByRole('button', { name: 'Show earlier messages (75)' }))
    expect(screen.getAllByTestId('message')).toHaveLength(100)
    fireEvent.click(screen.getByRole('button', { name: 'Show earlier messages (25)' }))
    expect(screen.getAllByTestId('message')).toHaveLength(125)
    expect(screen.getByText('message 0')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show earlier messages/ })).not.toBeInTheDocument()
  })

  it('resets the history window when switching conversations', () => {
    const { rerender } = render(<ChatMessages messages={history} conversationId="one" />)
    fireEvent.click(screen.getByRole('button', { name: /Show earlier messages/ }))
    rerender(<ChatMessages messages={history} conversationId="two" />)
    expect(screen.getAllByTestId('message')).toHaveLength(50)
  })
})
