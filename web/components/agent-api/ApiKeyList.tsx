/**
 * API Key List Component
 * Displays a list of API keys with actions
 */

'use client';

import { useState } from 'react';
import { Copy } from 'lucide-react';
import { AgentApiKey } from '@/types/agent-api';
import { Button } from '@/components/ui/Button';

// Simple time ago formatter
const formatTimeAgo = (date: Date): string => {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
  
  const intervals = {
    year: 31536000,
    month: 2592000,
    week: 604800,
    day: 86400,
    hour: 3600,
    minute: 60
  };
  
  for (const [name, secondsInInterval] of Object.entries(intervals)) {
    const interval = Math.floor(seconds / secondsInInterval);
    if (interval >= 1) {
      return `${interval} ${name}${interval > 1 ? 's' : ''} ago`;
    }
  }
  
  return 'just now';
};

interface ApiKeyListProps {
  apiKeys: AgentApiKey[];
  onEdit: (apiKey: AgentApiKey) => void;
  onDelete: (keyId: string) => void;
  onRegenerate: (keyId: string) => void;
  onToggleStatus: (keyId: string, isActive: boolean) => void;
  onViewUsage: (keyId: string) => void;
}

export function ApiKeyList({
  apiKeys,
  onEdit,
  onDelete,
  onRegenerate,
  onToggleStatus
}: ApiKeyListProps) {
  const [deleteKeyId, setDeleteKeyId] = useState<string | null>(null);
  const [regenerateKeyId, setRegenerateKeyId] = useState<string | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard');
  };

  const handleDelete = () => {
    if (deleteKeyId) {
      onDelete(deleteKeyId);
      setDeleteKeyId(null);
    }
  };

  const handleRegenerate = () => {
    if (regenerateKeyId) {
      onRegenerate(regenerateKeyId);
      setRegenerateKeyId(null);
    }
  };

  const maskApiKey = (key: string) => {
    if (key.length <= 8) return key;
    return `${key.substring(0, 7)}...${key.substring(key.length - 4)}`;
  };

  if (apiKeys.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-ink-soft">No API keys found</p>
        <p className="text-sm text-ink-mute mt-2">
          Create your first API key to get started
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-line">
          <thead className="bg-cream">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Key
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Permissions
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Last Used
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-ink-mute">
                Created
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-ink-mute">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-line">
            {apiKeys.map((apiKey) => (
              <tr key={apiKey.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-ink">
                  {apiKey.key_name}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <code className="text-xs bg-sand px-2 py-1 rounded">
                      {maskApiKey(apiKey.key_prefix)}
                    </code>
                    <button
                      onClick={() => copyToClipboard(apiKey.key_prefix)}
                      className="text-ink-soft hover:text-ink"
                      aria-label="Copy key prefix"
                    >
                      <Copy className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      apiKey.is_active
                        ? 'bg-leaf-wash text-forest'
                        : 'bg-sand text-ink'
                    }`}
                  >
                    {apiKey.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-ink-mute">
                  {apiKey.permissions.slice(0, 2).join(', ')}
                  {apiKey.permissions.length > 2 && ` +${apiKey.permissions.length - 2}`}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-ink-mute">
                  {apiKey.last_used_at
                    ? formatTimeAgo(new Date(apiKey.last_used_at))
                    : 'Never'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-ink-mute">
                  {formatTimeAgo(new Date(apiKey.created_at))}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onEdit(apiKey)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onToggleStatus(apiKey.id, !apiKey.is_active)}
                  >
                    {apiKey.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDeleteKeyId(apiKey.id)}
                  >
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteKeyId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-2">Are you sure?</h3>
            <p className="text-ink-soft mb-4">
              This action cannot be undone. This will permanently delete the API key and
              revoke all access using this key.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteKeyId(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleDelete} className="bg-danger hover:bg-danger">
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate Confirmation Dialog */}
      {regenerateKeyId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-2">Regenerate API Key?</h3>
            <p className="text-ink-soft mb-4">
              This will create a new API key and invalidate the old one. Any applications
              using the old key will stop working immediately.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRegenerateKeyId(null)}>
                Cancel
              </Button>
              <Button onClick={handleRegenerate}>Regenerate</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
