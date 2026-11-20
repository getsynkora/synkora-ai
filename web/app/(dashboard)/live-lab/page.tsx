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
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-danger"></div>
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
          <div className="inline-flex items-center gap-2 rounded-full border border-leaf-wash bg-leaf-wash px-4 py-2 text-sm font-semibold text-forest">
            <span className="h-2 w-2 rounded-full bg-leaf motion-safe:animate-pulse" />
            {activeExecutions.length} running
          </div>
        ) : null
      }
    >
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5 md:gap-4">
        {[
          { label: 'Active Now', value: activeExecutions.length, icon: Activity, tone: 'bg-leaf-wash text-forest' },
          { label: 'Recent', value: recentExecutions.length, icon: Clock, tone: 'bg-sand text-bark' },
          { label: 'Successful', value: successCount, icon: CheckCircle, tone: 'bg-leaf-wash text-forest' },
          { label: 'Errors', value: errorCount, icon: XCircle, tone: 'bg-blush-wash text-wine' },
          { label: 'Tools Used', value: totalToolsUsed, icon: Wrench, tone: 'bg-sky-wash text-azure' },
        ].map((stat) => (
          <DashboardPagePanel key={stat.label} className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className={`rounded-[0.95rem] p-2 ${stat.tone}`}>
                <stat.icon className="h-4 w-4" />
              </div>
              <p className="text-xs font-semibold text-clay">{stat.label}</p>
            </div>
            <p className="text-2xl font-semibold tracking-[-0.04em] text-ink">{stat.value}</p>
          </DashboardPagePanel>
        ))}
      </div>

      <section className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-leaf motion-safe:animate-pulse" />
          <h2 className="text-base font-semibold text-ink">Active Executions</h2>
          <span className="ml-1 text-xs text-ink-mute">{activeExecutions.length} running</span>
        </div>
        <ActiveExecutionsList executions={activeExecutions} />
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold text-ink">Recent Executions</h2>
        <RecentExecutionsList executions={recentExecutions} />
      </section>
    </DashboardPageShell>
  )
}
