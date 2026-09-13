/**
 * API Key Form Component
 * Form for creating/editing API keys
 */

'use client';

import { useState } from 'react';
import { CreateApiKeyRequest } from '@/types/agent-api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface ApiKeyFormProps {
  agentId: string;
  onSubmit: (data: CreateApiKeyRequest) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const AVAILABLE_PERMISSIONS = [
  { value: 'handoff:read', label: 'Read handoffs', description: 'Read this agent’s handoffs and conversation history' },
  { value: 'handoff:write', label: 'Manage handoffs', description: 'Reply, assign, resolve and reopen this agent’s handoffs' },
  { value: 'chat', label: 'Chat', description: 'Send messages to the agent' },
  { value: 'stream', label: 'Stream', description: 'Stream responses from the agent' },
  { value: 'history', label: 'History', description: 'Access conversation history' },
  { value: 'files', label: 'Files', description: 'Upload and manage files' },
  { value: 'tools', label: 'Tools', description: 'Execute agent tools' },
];

export function ApiKeyForm({ agentId, onSubmit, onCancel, isLoading }: ApiKeyFormProps) {
  const [formData, setFormData] = useState<CreateApiKeyRequest>({
    agent_id: agentId,
    key_name: '',
    permissions: ['chat'],
    rate_limit_per_minute: 60,
    rate_limit_per_hour: 1000,
    rate_limit_per_day: 10000,
    allowed_origins: [],
    allowed_ips: [],
    expires_at: undefined,
  });

  const [originInput, setOriginInput] = useState('');
  const [ipInput, setIpInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const togglePermission = (permission: string) => {
    setFormData((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter((p) => p !== permission)
        : [...prev.permissions, permission],
    }));
  };

  const addOrigin = () => {
    if (originInput && !formData.allowed_origins?.includes(originInput)) {
      setFormData((prev) => ({
        ...prev,
        allowed_origins: [...(prev.allowed_origins || []), originInput],
      }));
      setOriginInput('');
    }
  };

  const removeOrigin = (origin: string) => {
    setFormData((prev) => ({
      ...prev,
      allowed_origins: prev.allowed_origins?.filter((o) => o !== origin) || [],
    }));
  };

  const addIp = () => {
    if (ipInput && !formData.allowed_ips?.includes(ipInput)) {
      setFormData((prev) => ({
        ...prev,
        allowed_ips: [...(prev.allowed_ips || []), ipInput],
      }));
      setIpInput('');
    }
  };

  const removeIp = (ip: string) => {
    setFormData((prev) => ({
      ...prev,
      allowed_ips: prev.allowed_ips?.filter((i) => i !== ip) || [],
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Information */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-1">Basic Information</h3>
        <p className="text-sm text-gray-600 mb-4">Provide a name and description for your API key</p>
        
        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="key_name" className="block text-sm font-medium">Name *</label>
            <Input
              id="key_name"
              value={formData.key_name}
              onChange={(e) => setFormData({ ...formData, key_name: e.target.value })}
              placeholder="Production API Key"
              required
            />
          </div>

        </div>
      </div>

      {/* Permissions */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-1">Permissions</h3>
        <p className="text-sm text-gray-600 mb-4">Select which operations this API key can perform</p>
        
        <div className="space-y-3">
          {AVAILABLE_PERMISSIONS.map((permission) => (
            <div key={permission.value} className="flex items-start space-x-3">
              <input
                type="checkbox"
                id={permission.value}
                checked={formData.permissions.includes(permission.value)}
                onChange={() => togglePermission(permission.value)}
                className="mt-1"
              />
              <div className="space-y-1">
                <label htmlFor={permission.value} className="text-sm font-medium">
                  {permission.label}
                </label>
                <p className="text-sm text-gray-500">{permission.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rate Limits */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-1">Rate Limits</h3>
        <p className="text-sm text-gray-600 mb-4">Set rate limits to control API usage (leave empty for unlimited)</p>
        
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <label htmlFor="rate_limit_per_minute" className="block text-sm font-medium">Per Minute</label>
            <Input
              id="rate_limit_per_minute"
              type="number"
              value={formData.rate_limit_per_minute || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  rate_limit_per_minute: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              placeholder="60"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="rate_limit_per_hour" className="block text-sm font-medium">Per Hour</label>
            <Input
              id="rate_limit_per_hour"
              type="number"
              value={formData.rate_limit_per_hour || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  rate_limit_per_hour: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              placeholder="1000"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="rate_limit_per_day" className="block text-sm font-medium">Per Day</label>
            <Input
              id="rate_limit_per_day"
              type="number"
              value={formData.rate_limit_per_day || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  rate_limit_per_day: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              placeholder="10000"
            />
          </div>
        </div>
      </div>

      {/* Security */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-1">Security</h3>
        <p className="text-sm text-gray-600 mb-4">Configure security restrictions for this API key</p>
        
        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="allowed_origins" className="block text-sm font-medium">Allowed Origins (CORS)</label>
            <div className="flex gap-2">
              <Input
                id="allowed_origins"
                value={originInput}
                onChange={(e) => setOriginInput(e.target.value)}
                placeholder="https://example.com"
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addOrigin())}
              />
              <Button type="button" onClick={addOrigin} variant="outline">
                Add
              </Button>
            </div>
            {formData.allowed_origins && formData.allowed_origins.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.allowed_origins.map((origin) => (
                  <span
                    key={origin}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100"
                  >
                    {origin}
                    <button
                      type="button"
                      onClick={() => removeOrigin(origin)}
                      className="ml-2 text-gray-600 hover:text-gray-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="allowed_ips" className="block text-sm font-medium">Allowed IP Addresses</label>
            <div className="flex gap-2">
              <Input
                id="allowed_ips"
                value={ipInput}
                onChange={(e) => setIpInput(e.target.value)}
                placeholder="192.168.1.1"
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addIp())}
              />
              <Button type="button" onClick={addIp} variant="outline">
                Add
              </Button>
            </div>
            {formData.allowed_ips && formData.allowed_ips.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.allowed_ips.map((ip) => (
                  <span
                    key={ip}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100"
                  >
                    {ip}
                    <button
                      type="button"
                      onClick={() => removeIp(ip)}
                      className="ml-2 text-gray-600 hover:text-gray-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="expires_at" className="block text-sm font-medium">Expiration Date (Optional)</label>
            <Input
              id="expires_at"
              type="datetime-local"
              value={formData.expires_at || ''}
              onChange={(e) =>
                setFormData({ ...formData, expires_at: e.target.value || undefined })
              }
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-4">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading || !formData.key_name}>
          {isLoading ? 'Creating...' : 'Create API Key'}
        </Button>
      </div>
    </form>
  );
}
