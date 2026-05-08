'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { ArrowLeft, Plus, Trash2, Loader2, Tag, Copy } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface DiscountCode {
  id: string
  code: string
  discount_type: 'PERCENTAGE' | 'FLAT_CREDITS'
  discount_value: number
  max_uses: number | null
  used_count: number
  valid_from: string | null
  valid_until: string | null
  is_active: boolean
}

interface NewCodeForm {
  code: string
  discount_type: 'PERCENTAGE' | 'FLAT_CREDITS'
  discount_value: string
  max_uses: string
  valid_from: string
  valid_until: string
}

const EMPTY_FORM: NewCodeForm = {
  code: '',
  discount_type: 'PERCENTAGE',
  discount_value: '',
  max_uses: '',
  valid_from: '',
  valid_until: '',
}

export default function DiscountCodesPage() {
  const { agentName } = useParams() as { agentName: string }
  const [codes, setCodes] = useState<DiscountCode[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<NewCodeForm>(EMPTY_FORM)

  const load = useCallback(async () => {
    try {
      const res = await apiClient.request('GET', `/api/v1/agents/${agentName}/discount-codes`)
      setCodes(res?.codes || res || [])
    } catch {
      setCodes([])
    } finally {
      setLoading(false)
    }
  }, [agentName])

  useEffect(() => { load() }, [load])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim() || !form.discount_value) {
      toast.error('Code and discount value are required')
      return
    }
    setSaving(true)
    try {
      await apiClient.request('POST', `/api/v1/agents/${agentName}/discount-codes`, {
        code: form.code.trim().toUpperCase(),
        discount_type: form.discount_type,
        discount_value: Number(form.discount_value),
        max_uses: form.max_uses ? Number(form.max_uses) : null,
        valid_from: form.valid_from || null,
        valid_until: form.valid_until || null,
      })
      toast.success('Discount code created')
      setForm(EMPTY_FORM)
      setShowForm(false)
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to create code')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (codeId: string, code: string) => {
    if (!confirm(`Delete discount code "${code}"?`)) return
    try {
      await apiClient.request('DELETE', `/api/v1/agents/${agentName}/discount-codes/${codeId}`)
      toast.success('Code deleted')
      setCodes(prev => prev.filter(c => c.id !== codeId))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to delete')
    }
  }

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    toast.success('Copied!')
  }

  const generateCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    const code = Array.from({ length: 8 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
    setForm(f => ({ ...f, code }))
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-8">
        <Link
          href={`/agents/${agentName}/edit`}
          className="mb-2 inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Discount Codes</h1>
            <p className="text-sm text-gray-500 mt-1">Create codes to give users discounted access to this agent</p>
          </div>
          <button
            onClick={() => setShowForm(v => !v)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus className="h-4 w-4" />
            New code
          </button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleCreate} className="rounded-lg border border-primary-200 bg-primary-50 p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Create discount code</h2>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Code</label>
              <input
                type="text"
                value={form.code}
                onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="SUMMER20"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:border-primary-500 focus:outline-none uppercase"
              />
            </div>
            <div className="flex items-end">
              <button
                type="button"
                onClick={generateCode}
                className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm text-gray-600 transition-colors"
              >
                Generate
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Discount type</label>
              <select
                value={form.discount_type}
                onChange={e => setForm(f => ({ ...f, discount_type: e.target.value as any }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              >
                <option value="PERCENTAGE">Percentage (%)</option>
                <option value="FLAT_CREDITS">Flat credits off</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {form.discount_type === 'PERCENTAGE' ? 'Discount (%)' : 'Credits off'}
              </label>
              <input
                type="number"
                min="1"
                max={form.discount_type === 'PERCENTAGE' ? 100 : undefined}
                value={form.discount_value}
                onChange={e => setForm(f => ({ ...f, discount_value: e.target.value }))}
                placeholder={form.discount_type === 'PERCENTAGE' ? '20' : '50'}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max uses</label>
              <input
                type="number" min="1"
                value={form.max_uses}
                onChange={e => setForm(f => ({ ...f, max_uses: e.target.value }))}
                placeholder="Unlimited"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Valid from</label>
              <input
                type="datetime-local"
                value={form.valid_from}
                onChange={e => setForm(f => ({ ...f, valid_from: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Expires</label>
              <input
                type="datetime-local"
                value={form.valid_until}
                onChange={e => setForm(f => ({ ...f, valid_until: e.target.value }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM) }}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create code
            </button>
          </div>
        </form>
      )}

      {/* Codes list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
        </div>
      ) : codes.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Tag className="h-12 w-12 mx-auto mb-4 opacity-20" />
          <p className="font-medium">No discount codes yet</p>
          <p className="text-sm mt-1">Create codes to offer discounts on agent subscriptions</p>
        </div>
      ) : (
        <div className="space-y-3">
          {codes.map(c => (
            <div key={c.id} className="rounded-lg border border-gray-200 bg-white p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono font-semibold text-gray-900 text-sm tracking-wide">{c.code}</span>
                  <button onClick={() => copyCode(c.code)} className="text-gray-400 hover:text-gray-600">
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                  {!c.is_active && (
                    <span className="px-1.5 py-0.5 bg-red-100 text-red-600 rounded text-xs">Inactive</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                  <span>
                    {c.discount_type === 'PERCENTAGE' ? `${c.discount_value}% off` : `${c.discount_value} credits off`}
                  </span>
                  <span>
                    {c.used_count} used{c.max_uses ? ` / ${c.max_uses} max` : ' (unlimited)'}
                  </span>
                  {c.valid_until && (
                    <span>Expires {new Date(c.valid_until).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {c.max_uses && (
                  <div className="w-20 text-right">
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-400 rounded-full"
                        style={{ width: `${Math.min(100, (c.used_count / c.max_uses) * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 mt-0.5 block">
                      {Math.round((c.used_count / c.max_uses) * 100)}%
                    </span>
                  </div>
                )}
                <button
                  onClick={() => handleDelete(c.id, c.code)}
                  className="ml-2 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
