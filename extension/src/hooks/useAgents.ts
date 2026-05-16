import { useCallback, useEffect } from 'react';
import { fetchAgents } from '@/lib/api';
import { loadAccessToken, loadSynkoraUrl, loadApiUrl } from '@/lib/auth';
import { useExtensionStore } from '@/store/extension';

export function useAgents() {
  const {
    agents, agentsLoading, agentsError,
    setAgents, setAgentsLoading, setAgentsError,
    selectedAgentId, defaultAgentId, selectAgent, setDefaultAgent,
    isConnected, synkoraUrl,
  } = useExtensionStore();

  const load = useCallback(async () => {
    const url = synkoraUrl || await loadSynkoraUrl();
    if (!url) return;

    const tokenData = await loadAccessToken();
    if (!tokenData) return;

    setAgentsLoading(true);
    setAgentsError(null);

    // Use the direct API URL to avoid Next.js proxy redirect stripping the Auth header
    const apiUrl = await loadApiUrl() ?? url;

    try {
      const list = await fetchAgents(apiUrl, tokenData.token);
      setAgents(list);

      // Restore default agent from local storage
      const stored = await chrome.storage.local.get('snkr_default_agent');
      const storedDefault = stored['snkr_default_agent'] as string | undefined;

      if (storedDefault && list.some((a) => a.id === storedDefault)) {
        setDefaultAgent(storedDefault);
        if (!selectedAgentId) selectAgent(storedDefault);
      } else if (list.length > 0 && !selectedAgentId) {
        selectAgent(list[0].id);
      }
    } catch (err) {
      setAgentsError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setAgentsLoading(false);
    }
  }, [synkoraUrl, selectedAgentId, setAgents, setAgentsLoading, setAgentsError, selectAgent, setDefaultAgent]);

  useEffect(() => {
    if (isConnected) load();
  }, [isConnected, load]);

  return {
    agents,
    loading: agentsLoading,
    error: agentsError,
    selectedAgentId,
    defaultAgentId,
    selectAgent,
    setDefaultAgent,
    reload: load,
  };
}
