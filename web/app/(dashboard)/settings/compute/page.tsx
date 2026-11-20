'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { ArrowLeft, Box, CheckCircle, Info, Loader2, TestTube, XCircle } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

interface SandboxStatus {
  sandbox_service_url: string | null
  sandbox_available: boolean
}

export default function ComputeSettingsPage() {
  const router = useRouter()
  const [status, setStatus] = useState<SandboxStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    apiClient.request('GET', '/api/v1/compute/status')
      .then(setStatus)
      .catch(() => toast.error('Failed to load compute status'))
      .finally(() => setLoading(false))
  }, [])

  const handleTest = async () => {
    setTesting(true)
    try {
      const data = await apiClient.request('POST', '/api/v1/compute/test')
      if (data.success) {
        toast.success(`Sandbox test passed (${data.latency_ms}ms)`)
      } else {
        toast.error(data.error || 'Sandbox test failed')
      }
    } catch {
      toast.error('Sandbox test failed')
    } finally {
      setTesting(false)
    }
  }

  return (
    <DashboardPageShell
      title="Compute"
      description="Sandbox service for agent code execution."
      icon={Box}
      badge="Settings"
      backHref="/settings/profile"
      backLabel="Back to Settings"
      maxWidthClassName="max-w-3xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Compute' },
      ]}
      actions={
        !loading ? (
          <button
            onClick={handleTest}
            disabled={testing || !status?.sandbox_available}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-leaf-wash bg-cream px-4 py-3 text-sm font-semibold text-forest transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-paper-dim hover:text-forest disabled:opacity-50"
          >
            {testing ? <Loader2 className="h-4 w-4 motion-safe:animate-spin" /> : <TestTube className="h-4 w-4" />}
            Test Sandbox
          </button>
        ) : null
      }
    >
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 motion-safe:animate-spin text-ink" />
        </div>
      ) : (
        <DashboardPagePanel className="space-y-5 p-6 md:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-[-0.02em] text-ink">synkora-sandbox</h2>
              <p className="mt-1 text-sm text-ink-mute">Execution environment for isolated agent workspaces.</p>
            </div>
            <div
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${
                status?.sandbox_available
                  ? 'bg-leaf-wash text-forest'
                  : 'bg-blush-wash text-wine'
              }`}
            >
              {status?.sandbox_available ? (
                <CheckCircle className="h-3.5 w-3.5" />
              ) : (
                <XCircle className="h-3.5 w-3.5" />
              )}
              {status?.sandbox_available ? 'Service is running' : 'Service unavailable'}
            </div>
          </div>

          {status?.sandbox_service_url ? (
            <div className="rounded-[1.2rem] border border-black/5 bg-white/80 px-4 py-3">
              <p className="text-[11px] font-semibold text-clay">Service URL</p>
              <p className="mt-2 break-all font-mono text-xs text-ink-soft">{status.sandbox_service_url}</p>
            </div>
          ) : null}

          <div className="rounded-[1.25rem] border border-line bg-cream px-4 py-4">
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-sand-deep p-2">
                <Info className="h-4 w-4 text-bark" />
              </div>
              <p className="text-sm leading-6 text-ink-soft">
                Each agent gets an isolated workspace directory. Workspaces are ephemeral and are created at conversation start, then removed when the conversation ends. No additional configuration is required.
              </p>
            </div>
          </div>
        </DashboardPagePanel>
      )}
    </DashboardPageShell>
  )
}
