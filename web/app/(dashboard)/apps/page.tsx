'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api/client'
import type { App } from '@/lib/types'

export default function AppsPage() {
  const [apps, setApps] = useState<App[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadApps()
  }, [])

  const loadApps = async () => {
    try {
      const data = await apiClient.getApps()
      setApps(data)
    } catch (error) {
      console.error('Failed to load apps:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-leaf"></div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight mb-2">Apps</h1>
        <p className="text-ink-soft">Create and manage your AI applications</p>
      </div>

      {/* Create New App Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <button className="group relative bg-white border-2 border-dashed border-taupe rounded-xl p-8 hover:border-leaf hover:bg-leaf-wash/50 transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 flex flex-col items-center justify-center min-h-[240px]">
          <div className="w-16 h-16 bg-leaf-wash rounded-full flex items-center justify-center mb-4 group-hover:bg-mint transition-colors">
            <svg aria-hidden="true" className="w-8 h-8 text-leaf" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-ink mb-1">Create New App</h3>
          <p className="text-sm text-ink-mute text-center">Start building your AI application</p>
        </button>

        {/* App Cards */}
        {apps.map((app) => (
          <div
            key={app.id}
            className="group bg-white rounded-xl border border-line hover:border-leaf hover:shadow-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200 overflow-hidden"
          >
            <div className="p-6">
              {/* App Icon */}
              <div className="w-12 h-12 bg-azure rounded-lg flex items-center justify-center mb-4">
                <svg aria-hidden="true" className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>

              {/* App Info */}
              <h3 className="text-lg font-semibold text-ink mb-2 line-clamp-1">{app.name}</h3>
              <p className="text-sm text-ink-mute mb-4 line-clamp-2 min-h-[40px]">
                {app.description || 'No description provided'}
              </p>

              {/* App Meta */}
              <div className="flex items-center justify-between text-xs text-ash mb-4">
                <span className="flex items-center gap-1">
                  <svg aria-hidden="true" className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {new Date(app.created_at).toLocaleDateString()}
                </span>
                <span className="px-2 py-1 rounded-full text-xs font-medium bg-leaf-wash text-forest">
                  {app.mode}
                </span>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button className="flex-1 px-4 py-2 bg-leaf hover:bg-forest text-white text-sm font-medium rounded-lg transition-colors">
                  Open
                </button>
                <button className="p-2 hover:bg-sand rounded-lg transition-colors">
                  <svg aria-hidden="true" className="w-5 h-5 text-ink-soft" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {apps.length === 0 && (
        <div className="text-center py-16">
          <div className="w-24 h-24 bg-sand rounded-full flex items-center justify-center mx-auto mb-4">
            <svg aria-hidden="true" className="w-12 h-12 text-ash" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-ink mb-2">No apps yet</h3>
          <p className="text-ink-mute mb-6">Create your first AI application to get started</p>
          <button className="px-6 py-3 bg-leaf hover:bg-forest text-white font-medium rounded-lg transition-colors">
            Create App
          </button>
        </div>
      )}
    </div>
  )
}
