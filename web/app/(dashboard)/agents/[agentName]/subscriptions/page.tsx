'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { ArrowLeft, Bell, BellOff, Trash2, Users, Copy, CheckCircle } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { toggleSubscriptions, getSubscribers, deleteSubscriber } from '@/lib/api/subscriptions'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface Subscriber {
  id: string
  agent_id: string
  email: string
  is_active: boolean
}

export default function AgentSubscriptionsPage() {
  const params = useParams()
  const agentName = decodeURIComponent(params?.agentName as string || '')

  const [agentId, setAgentId] = useState('')
  const [allowSubscriptions, setAllowSubscriptions] = useState(false)
  const [subscribers, setSubscribers] = useState<Subscriber[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)
  const [copied, setCopied] = useState(false)

  const subscribeUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/subscribe/${agentId}`
    : ''

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const agent = await apiClient.getAgent(agentName)
      setAgentId(agent.id)
      setAllowSubscriptions(agent.allow_subscriptions ?? false)
      const subs = await getSubscribers(agent.id)
      setSubscribers(subs)
    } catch {
      toast.error('Failed to load subscription data')
    } finally {
      setLoading(false)
    }
  }, [agentName])

  useEffect(() => { load() }, [load])

  const handleToggle = async () => {
    try {
      setToggling(true)
      const result = await toggleSubscriptions(agentId)
      setAllowSubscriptions(result.allow_subscriptions)
      toast.success(result.allow_subscriptions ? 'Subscriptions enabled' : 'Subscriptions disabled')
    } catch {
      toast.error('Failed to update subscription setting')
    } finally {
      setToggling(false)
    }
  }

  const handleDelete = async (sub: Subscriber) => {
    if (!confirm(`Remove ${sub.email} from subscribers?`)) return
    try {
      await deleteSubscriber(agentId, sub.id)
      setSubscribers(prev => prev.filter(s => s.id !== sub.id))
      toast.success('Subscriber removed')
    } catch {
      toast.error('Failed to remove subscriber')
    }
  }

  const handleCopyLink = () => {
    navigator.clipboard.writeText(subscribeUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-gray-200 border-t-red-500" />
      </div>
    )
  }

  const activeCount = subscribers.filter(s => s.is_active).length

  return (
    <AgentPageShell
      agentName={agentName}
      title="Email Subscriptions"
      description={<>Manage who receives reports when <span className="font-semibold text-gray-900">{agentName}</span> runs on schedule.</>}
      icon={Bell}
      badge="Audience Delivery"
      maxWidthClassName="max-w-[90rem]"
      stats={[
        { label: 'Active', value: activeCount },
        { label: 'Status', value: allowSubscriptions ? 'Enabled' : 'Paused' },
      ]}
    >

        {/* Toggle Card */}
        <AgentPagePanel className="p-5 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {allowSubscriptions
                ? <Bell className="w-5 h-5 text-green-600" />
                : <BellOff className="w-5 h-5 text-gray-400" />}
              <div>
                <p className="font-semibold text-gray-900 text-sm">
                  {allowSubscriptions ? 'Subscriptions enabled' : 'Subscriptions disabled'}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {allowSubscriptions
                    ? 'Anyone with the subscribe link can sign up for reports'
                    : 'New subscriptions are paused — existing subscribers will not receive emails'}
                </p>
              </div>
            </div>
            <button
              onClick={handleToggle}
              disabled={toggling}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none disabled:opacity-60 ${
                allowSubscriptions ? 'bg-green-500' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  allowSubscriptions ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </AgentPagePanel>

        {/* Subscribe Link */}
        {allowSubscriptions && agentId && (
          <AgentPagePanel className="p-5 mb-4">
            <p className="text-sm font-semibold text-gray-700 mb-2">Public subscribe link</p>
            <p className="text-xs text-gray-500 mb-3">Share this link — visitors enter their email to subscribe to scheduled reports.</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-700 truncate">
                {subscribeUrl}
              </code>
              <button
                onClick={handleCopyLink}
                className="flex items-center gap-1.5 rounded-[1rem] bg-[#171717] px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </AgentPagePanel>
        )}

        {/* Subscribers List */}
        <AgentPagePanel className="overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-semibold text-gray-900">Subscribers</span>
            </div>
            <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">
              {activeCount} active
            </span>
          </div>

          {subscribers.length === 0 ? (
            <div className="py-12 text-center">
              <Bell className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No subscribers yet</p>
              {allowSubscriptions && (
                <p className="text-xs text-gray-400 mt-1">Share the subscribe link above to get started</p>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-gray-50">
              {subscribers.map(sub => (
                <li key={sub.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 font-semibold text-sm">
                      {sub.email[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{sub.email}</p>
                      <span className={`text-xs font-medium ${sub.is_active ? 'text-green-600' : 'text-gray-400'}`}>
                        {sub.is_active ? 'Active' : 'Unsubscribed'}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(sub)}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Remove subscriber"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </AgentPagePanel>
    </AgentPageShell>
  )
}
