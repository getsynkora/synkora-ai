'use client'

import { useEffect, useCallback, useRef } from 'react'
import { useLiveLabStore } from '@/lib/store/liveLabStore'
import { getExecutions } from '@/lib/api/live-lab'
import { ActiveExecutionsList } from '@/components/live-lab/ActiveExecutionsList'
import { RecentExecutionsList } from '@/components/live-lab/RecentExecutionsList'
import {
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Wrench,
} from 'lucide-react'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

export default function LiveLabPage() {
  const {
    activeExecutions,
    recentExecutions,
    isLoading,
    setActiveExecutions,
    setRecentExecutions,
    setLoading,
  } = useLiveLabStore()

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const data = await getExecutions('all', 100)
      setActiveExecutions(data.active || [])
      setRecentExecutions(data.recent || [])
    } catch (err) {
      console.error('Failed to fetch executions:', err)
    } finally {
      setLoading(false)
    }
  }, [setActiveExecutions, setRecentExecutions, setLoading])

  useEffect(() => {
    fetchData()
    intervalRef.current = setInterval(fetchData, 3000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchData])

  const successCount = recentExecutions.filter((e) => e.status === 'complete').length
  const errorCount = recentExecutions.filter((e) => e.status === 'error').length
  const totalToolsUsed = recentExecutions.reduce((sum, e) => sum + e.total_tools, 0)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
      </div>
    )
  }

  return (
    <DashboardPageShell
      title="Live Lab"
      description="Real-time agent execution monitoring."
      icon={Activity}
      badge="Labs"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Live Lab' },
      ]}
      stats={[
        { label: 'Active', value: activeExecutions.length },
        { label: 'Recent', value: recentExecutions.length },
      ]}
      actions={
        activeExecutions.length > 0 ? (
          <div className="inline-flex items-center gap-2 rounded-full border border-[#d8e5d9] bg-[#ebf5ee] px-4 py-2 text-sm font-semibold text-[#24543b]">
            <span className="h-2 w-2 rounded-full bg-[#2b7a52] animate-pulse" />
            {activeExecutions.length} running
          </div>
        ) : null
      }
    >
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5 md:gap-4">
        {[
          { label: 'Active Now', value: activeExecutions.length, icon: Activity, tone: 'bg-[#ebf5ee] text-[#24543b]' },
          { label: 'Recent', value: recentExecutions.length, icon: Clock, tone: 'bg-[#f3ecde] text-[#7c5d45]' },
          { label: 'Successful', value: successCount, icon: CheckCircle, tone: 'bg-[#ebf5ee] text-[#24543b]' },
          { label: 'Errors', value: errorCount, icon: XCircle, tone: 'bg-[#f8ecef] text-[#8a445c]' },
          { label: 'Tools Used', value: totalToolsUsed, icon: Wrench, tone: 'bg-[#eef4fb] text-[#345c8a]' },
        ].map((stat) => (
          <DashboardPagePanel key={stat.label} className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className={`rounded-[0.95rem] p-2 ${stat.tone}`}>
                <stat.icon className="h-4 w-4" />
              </div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">{stat.label}</p>
            </div>
            <p className="text-2xl font-semibold tracking-[-0.04em] text-gray-950">{stat.value}</p>
          </DashboardPagePanel>
        ))}
      </div>

      <section className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#2b7a52] animate-pulse" />
          <h2 className="text-base font-semibold text-gray-900">Active Executions</h2>
          <span className="ml-1 text-xs text-gray-500">{activeExecutions.length} running</span>
        </div>
        <ActiveExecutionsList executions={activeExecutions} />
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold text-gray-900">Recent Executions</h2>
        <RecentExecutionsList executions={recentExecutions} />
      </section>
    </DashboardPageShell>
  )
}
