'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Mail, CreditCard, Database, BarChart3, Activity, Lock, PlugZap } from 'lucide-react'
import { useIntegrations } from '@/hooks/useIntegrations'
import { usePermissions } from '@/hooks/usePermissions'
import { IntegrationCard } from '@/components/integrations'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import DashboardPageShell, { DashboardPagePanel, DashboardPageTabs } from '@/components/dashboard/DashboardPageShell'

const INTEGRATION_TYPES = [
  { value: 'email', label: 'Email', icon: Mail, description: 'Email service providers' },
  { value: 'payment', label: 'Payment', icon: CreditCard, description: 'Payment gateways' },
  { value: 'storage', label: 'Storage', icon: Database, description: 'Cloud storage services' },
  { value: 'analytics', label: 'Analytics', icon: BarChart3, description: 'Analytics platforms' },
  { value: 'monitoring', label: 'Monitoring', icon: Activity, description: 'Monitoring services' },
]

export default function IntegrationsPage() {
  const router = useRouter()
  const [selectedType, setSelectedType] = useState<string>('all')
  const { configs, loading, error, testConnection, activateConfig, deleteConfig, refetch } = useIntegrations()
  const { hasPermission, loading: permissionsLoading } = usePermissions()

  // Check permissions
  const canCreate = hasPermission('integration_configs', 'create')
  const canUpdate = hasPermission('integration_configs', 'update')
  const canDelete = hasPermission('integration_configs', 'delete')
  const canRead = hasPermission('integration_configs', 'read')
  const isPlatformOwner = hasPermission('platform', 'read')

  const handleTest = async (id: string) => {
    try {
      await testConnection(id)
      alert('Connection test successful!')
    } catch (err: any) {
      alert(`Connection test failed: ${err.message}`)
    }
  }

  const handleActivate = async (id: string) => {
    try {
      await activateConfig(id)
      await refetch()
    } catch (err: any) {
      alert(`Failed to activate: ${err.message}`)
    }
  }

  const handleDelete = async (id: string) => {
    if (!canDelete) {
      alert('You do not have permission to delete integration configurations')
      return
    }
    
    if (!confirm('Are you sure you want to delete this integration configuration?')) {
      return
    }
    
    try {
      await deleteConfig(id)
      await refetch()
    } catch (err: any) {
      alert(`Failed to delete: ${err.message}`)
    }
  }

  // Filter configs based on role:
  // - Platform Owners see all configs (including platform configs)
  // - Other users only see tenant-specific configs (not platform configs)
  const visibleConfigs = isPlatformOwner 
    ? configs 
    : configs.filter(config => !config.is_platform_config)

  const filteredConfigs = selectedType === 'all'
    ? visibleConfigs
    : visibleConfigs.filter(config => config.integration_type === selectedType)

  if (loading || permissionsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    )
  }

  // Check read permission
  if (!canRead) {
    return (
      <DashboardPageShell
        title="Integrations"
        description="Manage third-party service integrations."
        icon={PlugZap}
        badge="Settings"
        backHref="/settings"
        backLabel="Back to Settings"
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Integrations' },
        ]}
      >
        <DashboardPagePanel className="p-10 text-center">
          <Lock className="mx-auto mb-4 h-12 w-12 text-[#9a7a5e]" />
          <h3 className="text-lg font-semibold text-gray-900">Access Denied</h3>
          <p className="mt-2 text-sm text-gray-600">
            You do not have permission to view integration configurations.
          </p>
        </DashboardPagePanel>
      </DashboardPageShell>
    )
  }

  if (error) {
    return (
      <DashboardPageShell
        title="Integrations"
        description="Manage third-party service integrations."
        icon={PlugZap}
        badge="Settings"
        backHref="/settings"
        backLabel="Back to Settings"
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Integrations' },
        ]}
      >
        <ErrorAlert message={error} />
      </DashboardPageShell>
    )
  }

  return (
    <DashboardPageShell
      title="Integrations"
      description="Manage third-party service integrations."
      icon={PlugZap}
      badge="Settings"
      backHref="/settings"
      backLabel="Back to Settings"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Integrations' },
      ]}
      heroOverflowVisible
      actions={
        canCreate ? (
          <div className="relative z-[70] group">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus size={16} />
              Add Integration
            </button>
            <div className="absolute right-0 top-full z-[80] mt-2 hidden w-64 overflow-hidden rounded-[1.25rem] border border-[#e5d9ca] bg-white shadow-[0_24px_70px_-36px_rgba(73,45,23,0.3)] group-hover:block group-focus-within:block">
              {INTEGRATION_TYPES.map((type) => {
                const Icon = type.icon
                return (
                  <button
                    key={type.value}
                    onClick={() => router.push(`/settings/integrations/${type.value}/create`)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[#f7f2e7]"
                  >
                    <div className="rounded-[0.95rem] bg-[#f3ecde] p-2.5">
                      <Icon size={16} className="text-[#171717]" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-gray-900">{type.label}</div>
                      <div className="text-xs text-gray-500">{type.description}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        ) : null
      }
      stats={[
        { label: 'Visible', value: visibleConfigs.length },
        { label: 'Active', value: visibleConfigs.filter((config) => config.is_active).length },
      ]}
    >
      <div className="space-y-5">
        <DashboardPageTabs
          activeId={selectedType}
          onChange={setSelectedType}
          items={[
            { id: 'all', label: 'All' },
            ...INTEGRATION_TYPES.map((type) => ({
              id: type.value,
              label: type.label,
              icon: <type.icon size={14} />,
            })),
          ]}
        />

        {filteredConfigs.length === 0 ? (
          <DashboardPagePanel className="p-12 text-center">
            <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-[#f3ecde]">
              <Plus size={28} className="text-[#171717]" />
            </div>
            <h3 className="text-base font-semibold text-gray-900">No integrations found</h3>
            <p className="mt-2 text-sm text-gray-600">
              {selectedType === 'all'
                ? 'Get started by adding your first integration using the action above.'
                : `No ${selectedType} integrations configured yet.`}
            </p>
          </DashboardPagePanel>
        ) : (
          <div className="space-y-3">
            {filteredConfigs.map((config) => (
              <DashboardPagePanel key={config.id} className="overflow-hidden">
                <IntegrationCard
                  config={config}
                  onTest={handleTest}
                  onActivate={canUpdate ? handleActivate : undefined}
                  onDelete={canDelete ? handleDelete : undefined}
                  isPlatformOwner={isPlatformOwner}
                />
              </DashboardPagePanel>
            ))}
          </div>
        )}
      </div>
    </DashboardPageShell>
  )
}
