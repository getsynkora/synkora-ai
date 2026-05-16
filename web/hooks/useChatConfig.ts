import { useState, useEffect } from 'react';
import { getChatConfig, updateChatConfig, ChatPageConfig, ChatConfigResponse } from '@/lib/api/chat-config';

export function useChatConfig(agentId: string) {
  const [config, setConfig] = useState<ChatConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (agentId) {
      fetchConfig();
    }
  }, [agentId]);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getChatConfig(agentId);
      setConfig(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch chat configuration');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async (newConfig: ChatPageConfig) => {
    if (!config) return;
    
    try {
      setSaving(true);
      setError(null);
      // Update uses agent_id
      const updated = await updateChatConfig(config.agent_id, newConfig);
      setConfig(updated);
      return updated;
    } catch (err: any) {
      setError(err.message || 'Failed to save chat configuration');
      throw err;
    } finally {
      setSaving(false);
    }
  };

  return {
    config,
    loading,
    error,
    saving,
    saveConfig,
    refetch: fetchConfig,
  };
}
