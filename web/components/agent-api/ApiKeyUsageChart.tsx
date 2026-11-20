/**
 * API Key Usage Chart Component
 * Displays usage analytics for API keys
 */

'use client';

import { useMemo } from 'react';
import { AgentApiUsage } from '@/types/agent-api';

// Simple date formatter
const formatDate = (date: Date, formatStr: string): string => {
  if (formatStr === 'MMM dd') {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[date.getMonth()]} ${date.getDate().toString().padStart(2, '0')}`;
  }
  if (formatStr === 'MMM dd, yyyy HH:mm') {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${months[date.getMonth()]} ${date.getDate().toString().padStart(2, '0')}, ${date.getFullYear()} ${hours}:${minutes}`;
  }
  return date.toISOString();
};

interface ApiKeyUsageChartProps {
  usage: AgentApiUsage[];
}

export function ApiKeyUsageChart({ usage }: ApiKeyUsageChartProps) {
  const stats = useMemo(() => {
    const totalRequests = usage.reduce((sum, u) => sum + u.request_count, 0);
    const successfulRequests = usage.reduce(
      (sum, u) => sum + (u.success_count || 0),
      0
    );
    const failedRequests = usage.reduce((sum, u) => sum + (u.error_count || 0), 0);
    const avgResponseTime =
      usage.length > 0
        ? usage.reduce((sum, u) => sum + (u.avg_response_time || 0), 0) / usage.length
        : 0;

    return {
      totalRequests,
      successfulRequests,
      failedRequests,
      successRate:
        totalRequests > 0 ? ((successfulRequests / totalRequests) * 100).toFixed(2) : '0',
      avgResponseTime: avgResponseTime.toFixed(2),
    };
  }, [usage]);

  const chartData = useMemo(() => {
    // Group usage by date
    const grouped = usage.reduce((acc, u) => {
      const date = formatDate(new Date(u.timestamp), 'MMM dd');
      if (!acc[date]) {
        acc[date] = { date, requests: 0, errors: 0 };
      }
      acc[date].requests += u.request_count;
      acc[date].errors += u.error_count || 0;
      return acc;
    }, {} as Record<string, { date: string; requests: number; errors: number }>);

    return Object.values(grouped).slice(-30); // Last 30 days
  }, [usage]);

  if (usage.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-2">Usage Analytics</h3>
        <p className="text-ink-mute text-center py-8">
          No usage data available yet
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm font-medium text-ink-mute mb-2">
            Total Requests
          </div>
          <div className="text-2xl font-bold">{stats.totalRequests.toLocaleString()}</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm font-medium text-ink-mute mb-2">
            Success Rate
          </div>
          <div className="text-2xl font-bold">{stats.successRate}%</div>
          <p className="text-xs text-ink-mute mt-1">
            {stats.successfulRequests.toLocaleString()} successful
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm font-medium text-ink-mute mb-2">
            Failed Requests
          </div>
          <div className="text-2xl font-bold text-danger">
            {stats.failedRequests.toLocaleString()}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm font-medium text-ink-mute mb-2">
            Avg Response Time
          </div>
          <div className="text-2xl font-bold">{stats.avgResponseTime}ms</div>
        </div>
      </div>

      {/* Simple Bar Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Request History (Last 30 Days)</h3>
        <div className="space-y-2">
          {chartData.map((data) => (
            <div key={data.date} className="flex items-center gap-4">
              <div className="w-20 text-sm text-ink-mute">{data.date}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div
                    className="bg-azure h-8 rounded"
                    style={{
                      width: `${Math.min((data.requests / Math.max(...chartData.map((d) => d.requests))) * 100, 100)}%`,
                    }}
                  />
                  <span className="text-sm font-medium">{data.requests}</span>
                </div>
                {data.errors > 0 && (
                  <div className="flex items-center gap-2 mt-1">
                    <div
                      className="bg-danger h-2 rounded"
                      style={{
                        width: `${Math.min((data.errors / data.requests) * 100, 100)}%`,
                      }}
                    />
                    <span className="text-xs text-danger">{data.errors} errors</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Usage Table */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
        <div className="space-y-2">
          {usage.slice(0, 10).map((u, index) => (
            <div
              key={index}
              className="flex items-center justify-between py-2 border-b last:border-0"
            >
              <div>
                <div className="text-sm font-medium">
                  {formatDate(new Date(u.timestamp), 'MMM dd, yyyy HH:mm')}
                </div>
                <div className="text-xs text-ink-mute">
                  Endpoint: {u.endpoint || 'N/A'}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium">{u.request_count} requests</div>
                {u.error_count && u.error_count > 0 && (
                  <div className="text-xs text-danger">{u.error_count} errors</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
