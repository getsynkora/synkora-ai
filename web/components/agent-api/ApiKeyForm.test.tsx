import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiKeyForm } from './ApiKeyForm'

describe('handoff permissions', () => {
  it('requires explicit opt-in and keeps read separate from write', () => {
    const submit = vi.fn()
    render(<ApiKeyForm agentId="agent-a" onSubmit={submit} onCancel={() => {}} />)
    const read = screen.getByRole('checkbox', { name: /Read handoffs/i })
    const write = screen.getByRole('checkbox', { name: /Manage handoffs/i })
    expect(read).not.toBeChecked()
    expect(write).not.toBeChecked()
    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: 'Reader' } })
    fireEvent.click(read)
    fireEvent.click(screen.getByRole('button', { name: 'Create API Key' }))
    expect(submit).toHaveBeenCalledWith(expect.objectContaining({
      agent_id: 'agent-a', permissions: ['chat', 'handoff:read'],
    }))
  })
})
