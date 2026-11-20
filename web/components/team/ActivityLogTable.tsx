'use client';

import { ActivityLog } from '@/types/activity';

interface ActivityLogTableProps {
  logs: ActivityLog[];
  isLoading?: boolean;
}

export function ActivityLogTable({ logs, isLoading = false }: ActivityLogTableProps) {
  const getActionColor = (action: string) => {
    if (action.includes('create') || action.includes('invite')) {
      return 'text-leaf';
    }
    if (action.includes('delete') || action.includes('remove')) {
      return 'text-danger';
    }
    if (action.includes('update') || action.includes('change')) {
      return 'text-azure';
    }
    return 'text-ink-soft';
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  };

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="motion-safe:animate-pulse space-y-4">
          <div className="h-4 bg-line rounded w-1/4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-sand rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-line">
        <h3 className="text-lg font-medium text-ink">Activity Log</h3>
        <p className="mt-1 text-sm text-ink-mute">
          Recent actions performed by team members
        </p>
      </div>

      {logs.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <p className="text-ink-mute">No activity yet</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-line">
            <thead className="bg-cream">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  User
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  Resource
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  Details
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                  IP Address
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-line">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-cream">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-8 w-8 bg-line rounded-full flex items-center justify-center">
                        <span className="text-xs font-medium text-ink-soft">
                          {log.account_name?.charAt(0).toUpperCase() || '?'}
                        </span>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm font-medium text-ink">
                          {log.account_name || 'Unknown'}
                        </p>
                        <p className="text-xs text-ink-mute">{log.account_email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`text-sm font-medium ${getActionColor(log.action)}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm text-ink">{log.resource_type}</span>
                    {log.resource_id && (
                      <p className="text-xs text-ink-mute truncate max-w-xs">
                        ID: {log.resource_id}
                      </p>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {log.details ? (
                      <div className="text-sm text-ink-soft max-w-md">
                        {typeof log.details === 'string' ? (
                          <p className="truncate">{log.details}</p>
                        ) : (
                          <pre className="text-xs overflow-auto max-h-20">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-ash">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-ink">
                      {formatTimestamp(log.created_at)}
                    </div>
                    <div className="text-xs text-ink-mute">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-ink-mute">
                    {log.ip_address || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
