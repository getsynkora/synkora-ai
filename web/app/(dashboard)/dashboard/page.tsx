'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/hooks/useAuth'
import { apiClient } from '@/lib/api/client'
import Link from 'next/link'
import { Bot, BookOpen, Database, Server, Plus, TrendingUp, Activity, Sparkles } from 'lucide-react'

interface DashboardStats {
  totalAgents: number
  knowledgeBases: number
  dataSources: number
  mcpServers: number
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState<DashboardStats>({
    totalAgents: 0,
    knowledgeBases: 0,
    dataSources: 0,
    mcpServers: 0
  })
  const [loading, setLoading] = useState(true)
  const [recentActivity, setRecentActivity] = useState<any[]>([])

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      
      // Fetch all data in parallel
      const [agentsResponse, knowledgeBases, dataSources, mcpServers] = await Promise.all([
        apiClient.getAgents().catch(() => ({ agents: [], pagination: { total: 0 } })),
        apiClient.getKnowledgeBases().catch(() => []),
        apiClient.getDataSources().catch(() => []),
        apiClient.getMCPServers().catch(() => [])
      ])

      // Extract agents array from response
      const agents = Array.isArray(agentsResponse) ? agentsResponse : (agentsResponse.agents || [])
      const totalAgents = agentsResponse.pagination?.total || agents.length

      setStats({
        totalAgents: totalAgents,
        knowledgeBases: Array.isArray(knowledgeBases) ? knowledgeBases.length : 0,
        dataSources: Array.isArray(dataSources) ? dataSources.length : 0,
        mcpServers: Array.isArray(mcpServers) ? mcpServers.length : 0
      })

      // Build recent activity from the data
      const activities: any[] = []
      
      // Add recent agents (last 3) - use data already fetched, no extra round-trip
      if (Array.isArray(agents) && agents.length > 0) {
        agents.slice(0, 3).forEach((agent: any) => {
          activities.push({
            type: 'agent',
            title: 'Agent created',
            description: `${agent.agent_name || agent.name} was created`,
            time: agent.created_at,
            icon: Bot,
            color: 'teal'
          })
        })
      }

      // Add recent knowledge bases (last 2)
      if (Array.isArray(knowledgeBases) && knowledgeBases.length > 0) {
        knowledgeBases.slice(-2).reverse().forEach((kb: any) => {
          activities.push({
            type: 'knowledge_base',
            title: 'Knowledge base updated',
            description: `${kb.name} was updated`,
            time: kb.updated_at || kb.created_at,
            icon: BookOpen,
            color: 'green'
          })
        })
      }

      // Add recent data sources (last 2)
      if (Array.isArray(dataSources) && dataSources.length > 0) {
        dataSources.slice(-2).reverse().forEach((ds: any) => {
          activities.push({
            type: 'data_source',
            title: 'Data source connected',
            description: `${ds.name} was connected`,
            time: ds.created_at,
            icon: Database,
            color: 'purple'
          })
        })
      }

      // Sort by time and take top 3
      activities.sort((a, b) => {
        const timeA = new Date(a.time || 0).getTime()
        const timeB = new Date(b.time || 0).getTime()
        return timeB - timeA
      })

      setRecentActivity(activities.slice(0, 3))
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getTimeAgo = (timestamp: string) => {
    if (!timestamp) return 'Recently'
    
    const now = new Date().getTime()
    const time = new Date(timestamp).getTime()
    const diff = now - time
    
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    
    if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
    if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`
    return `${days} day${days !== 1 ? 's' : ''} ago`
  }

  const statsData = [
    {
      name: 'Total Agents',
      value: loading ? '...' : stats.totalAgents.toString(),
      icon: <Bot className="w-5 h-5" />,
      lightColor: 'bg-[#ffe1ea]',
      textColor: 'text-[#171717]',
      href: '/agents'
    },
    {
      name: 'Knowledge Bases',
      value: loading ? '...' : stats.knowledgeBases.toString(),
      icon: <BookOpen className="w-5 h-5" />,
      lightColor: 'bg-[#fff0d9]',
      textColor: 'text-[#171717]',
      href: '/knowledge-bases'
    },
    {
      name: 'Data Sources',
      value: loading ? '...' : stats.dataSources.toString(),
      icon: <Database className="w-5 h-5" />,
      lightColor: 'bg-[#def4eb]',
      textColor: 'text-[#171717]',
      href: '/data-sources'
    },
    {
      name: 'MCP Servers',
      value: loading ? '...' : stats.mcpServers.toString(),
      icon: <Server className="w-5 h-5" />,
      lightColor: 'bg-[#ebe5fb]',
      textColor: 'text-[#171717]',
      href: '/mcp-servers'
    }
  ]

  const quickActions = [
    {
      name: 'Create Agent',
      description: 'Build a new AI agent',
      icon: <Plus className="w-5 h-5" />,
      href: '/agents/create',
      featured: true
    },
    {
      name: 'Browse Agents',
      description: 'Explore public agents',
      icon: <Activity className="w-5 h-5" />,
      href: '/browse',
      featured: false
    },
    {
      name: 'Add Knowledge Base',
      description: 'Upload documents',
      icon: <BookOpen className="w-5 h-5" />,
      href: '/knowledge-bases/create',
      featured: false
    },
    {
      name: 'Connect Data Source',
      description: 'Link external data',
      icon: <Database className="w-5 h-5" />,
      href: '/data-sources/connect',
      featured: false
    }
  ]

  const getActivityColor = (color: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      teal: { bg: 'bg-[#def4eb]', text: 'text-[#171717]' },
      green: { bg: 'bg-[#fff0d9]', text: 'text-[#171717]' },
      purple: { bg: 'bg-[#ebe5fb]', text: 'text-[#171717]' },
      blue: { bg: 'bg-[#ffe1ea]', text: 'text-[#171717]' }
    }
    return colors[color] || colors.teal
  }

  return (
    <div className="min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem] py-1">
        <div className="dashboard-surface mb-6 rounded-[2rem] p-5 md:p-6 xl:p-7">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
            <Sparkles className="h-3 w-3 text-[#ff5f8f]" />
            Workspace Overview
          </div>
          <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
            Welcome back,
            <span className="editorial-highlight ml-3">{user?.name || 'User'}</span>
          </h1>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-[#5b564e] md:text-[15px]">
            Here&apos;s what&apos;s happening with your AI platform today.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <div className="dashboard-chip rounded-full px-4 py-2 text-[13px] font-medium">
              {stats.totalAgents} agents
            </div>
            <div className="dashboard-chip rounded-full px-4 py-2 text-[13px] font-medium">
              {stats.knowledgeBases} knowledge bases
            </div>
            <div className="dashboard-chip rounded-full px-4 py-2 text-[13px] font-medium">
              {stats.dataSources} data sources
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4 xl:gap-5">
          {statsData.map((stat) => (
            <Link
              key={stat.name}
              href={stat.href}
              className="dashboard-panel relative rounded-[1.6rem] p-5 transition-all duration-300 hover:-translate-y-1"
            >
              <div className="mb-3 flex items-start justify-between">
                <div className={`${stat.lightColor} rounded-full p-2.5`}>
                  <div className={`${stat.textColor} h-5 w-5`}>
                    {stat.icon}
                  </div>
                </div>
                <TrendingUp className="h-4.5 w-4.5 text-[#8a8378]" />
              </div>
              <h3 className="mb-1 text-[1.65rem] font-semibold tracking-[-0.04em] text-[#171717]">{stat.value}</h3>
              <p className="text-[13px] font-medium text-[#6c655c]">{stat.name}</p>
            </Link>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="mb-6">
          <h2 className="mb-4 text-[1.05rem] font-semibold text-[#171717] md:text-[1.45rem]">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:gap-5">
            {quickActions.map((action) => (
              <Link
                key={action.name}
                href={action.href}
                className={`rounded-[1.6rem] p-5 transition-all duration-300 hover:-translate-y-1 ${
                  action.featured
                    ? 'bg-[#181818] text-[#f7f2e7] shadow-[0_24px_60px_rgba(0,0,0,0.16)]'
                    : 'dashboard-panel text-[#171717]'
                }`}
              >
                <div className="mb-3">
                  <div className={`inline-flex rounded-full p-2.5 ${action.featured ? 'bg-white/10' : 'bg-[#ffe1ea]'}`}>
                    {action.icon}
                  </div>
                </div>
                <h3 className="mb-1 text-[15px] font-semibold md:text-[1rem]">{action.name}</h3>
                <p className={`text-[13px] ${action.featured ? 'text-white/80' : 'text-[#6c655c]'}`}>{action.description}</p>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="dashboard-surface overflow-hidden rounded-[1.8rem]">
          <div className="border-b border-black/[0.08] px-4 py-4 md:px-5">
            <h2 className="text-[1.05rem] font-semibold text-[#171717] md:text-[1.45rem]">Recent Activity</h2>
          </div>
          <div className="divide-y divide-black/[0.06]">
            {loading ? (
              <div className="p-5 text-center text-sm text-[#6c655c]">Loading activity...</div>
            ) : recentActivity.length === 0 ? (
              <div className="p-5 text-center text-sm text-[#6c655c]">
                No recent activity. Start by creating an agent or knowledge base!
              </div>
            ) : (
              recentActivity.map((activity, index) => {
                const colors = getActivityColor(activity.color)
                const Icon = activity.icon
                
                return (
                  <div key={index} className="p-4 transition-colors duration-200 hover:bg-white/[0.45] md:px-5 md:py-4">
                    <div className="flex items-center gap-3">
                      <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${colors.bg}`}>
                        <Icon className={`h-4.5 w-4.5 ${colors.text}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-[14px] font-medium text-[#171717] md:text-[15px]">{activity.title}</p>
                        <p className="truncate text-[13px] text-[#6c655c]">{activity.description}</p>
                      </div>
                      <span className="whitespace-nowrap text-[12px] text-[#8a8378] md:text-[13px]">{getTimeAgo(activity.time)}</span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
