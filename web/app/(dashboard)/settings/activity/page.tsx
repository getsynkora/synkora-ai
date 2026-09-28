'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import { ActivityLogTable } from '@/components/team/ActivityLogTable';
import { useActivityLog } from '@/hooks/useActivityLog';
import { usePermissions } from '@/hooks/usePermissions';
import { secureStorage } from '@/lib/auth/secure-storage';
import { ActivityAction, ActivityResourceType } from '@/types/activity';

type ExportFormat = 'csv' | 'json';

export default function ActivityLogPage() {
  const { logs, isLoading, filters, setFilters } = useActivityLog();
  const { hasPermission } = usePermissions();
  const [daysFilter, setDaysFilter] = useState<number>(7);
  const [exportFormat, setExportFormat] = useState<ExportFormat>('csv');
  const [exportLimit, setExportLimit] = useState<number>(1000);
  const [isExporting, setIsExporting] = useState(false);
  const [chainIntegrity, setChainIntegrity] = useState<'valid' | 'warning' | null>(null);

  const canExport = hasPermission('activity_logs', 'manage');

  const handleExport = async () => {
    setIsExporting(true);
    setChainIntegrity(null);
    try {
      const token = secureStorage.getAccessToken();
      const clampedLimit = Math.min(Math.max(1, exportLimit), 10000);
      const response = await fetch(
        `/api/v1/activity-logs/export?format=${exportFormat}&limit=${clampedLimit}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      if (!response.ok) {
        const detail = response.status === 403
          ? 'You do not have permission to export audit logs.'
          : `Export failed (${response.status}).`;
        toast.error(detail);
        return;
      }

      const blob = await response.blob();
      const chainValid = response.headers.get('X-Audit-Chain-Valid');
      setChainIntegrity(chainValid === 'true' ? 'valid' : 'warning');

      const today = new Date().toISOString().split('T')[0];
      const filename = `audit-logs-${today}.${exportFormat}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      toast.success(`Exported ${clampedLimit} records`);
    } catch {
      toast.error('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40">
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Activity Log</h1>
          <p className="mt-1 text-sm text-gray-600">
            View all activity and changes in your workspace
          </p>
        </div>

        {/* Filters */}
        <div className="mb-5 bg-white shadow-sm border border-gray-200 rounded-lg p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Action Type
              </label>
              <select
                value={filters.action || ''}
                onChange={(e) => setFilters({ ...filters, action: (e.target.value as ActivityAction) || undefined })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
              >
                <option value="">All Actions</option>
                <option value="create">Create</option>
                <option value="update">Update</option>
                <option value="delete">Delete</option>
                <option value="login">Login</option>
                <option value="logout">Logout</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Resource Type
              </label>
              <select
                value={filters.resource_type || ''}
                onChange={(e) => setFilters({ ...filters, resource_type: (e.target.value as ActivityResourceType) || undefined })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
              >
                <option value="">All Resources</option>
                <option value="agent">Agent</option>
                <option value="team_member">Team Member</option>
                <option value="profile">Profile</option>
                <option value="permission">Permission</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Date Range
              </label>
              <select
                value={daysFilter}
                onChange={(e) => setDaysFilter(parseInt(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
              >
                <option value="1">Last 24 hours</option>
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
              </select>
            </div>
          </div>
        </div>

        {/* Export Controls — visible to owners and admins only */}
        {canExport && (
          <div className="mb-5 bg-white shadow-sm border border-gray-200 rounded-lg p-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <span className="block text-xs font-medium text-gray-700 mb-1.5">Export Format</span>
                <div className="flex gap-3">
                  {(['csv', 'json'] as ExportFormat[]).map((fmt) => (
                    <label key={fmt} className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        name="exportFormat"
                        value={fmt}
                        checked={exportFormat === fmt}
                        onChange={() => setExportFormat(fmt)}
                        className="accent-red-600"
                      />
                      <span className="text-sm text-gray-700 uppercase">{fmt}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">
                  Record Limit
                </label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={exportLimit}
                  onChange={(e) => setExportLimit(parseInt(e.target.value, 10) || 1000)}
                  className="w-28 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500"
                />
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleExport}
                  disabled={isExporting}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  {isExporting ? (
                    <span className="h-4 w-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  ) : (
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  )}
                  {isExporting ? 'Exporting...' : 'Export'}
                </button>

                {chainIntegrity !== null && (
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                      chainIntegrity === 'valid'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        chainIntegrity === 'valid' ? 'bg-green-500' : 'bg-yellow-500'
                      }`}
                    />
                    Chain integrity: {chainIntegrity === 'valid' ? 'Valid' : 'Warning'}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Activity Log Table */}
        <ActivityLogTable logs={logs} />

        {/* Info Box */}
        <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-4 w-4 text-red-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-xs font-medium text-red-800">About Activity Logs</h3>
              <div className="mt-1.5 text-xs text-red-700">
                <p>
                  Activity logs track all important actions in your workspace for security and compliance.
                  Logs are retained for 90 days and can be exported for audit purposes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
