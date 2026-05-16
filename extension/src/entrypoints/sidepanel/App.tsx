import { useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import {
  loadAccessToken, loadSynkoraUrl, storeSynkoraUrl,
  buildAuthUrl, exchangeCodeForTokens, storeApiUrl,
} from '@/lib/auth';
import { useExtensionStore } from '@/store/extension';
import { useAgents } from '@/hooks/useAgents';
import { AgentPicker, AgentAvatar } from '@/components/AgentPicker';
import { ChatPanel } from '@/components/ChatPanel';
import { ContextBadge } from '@/components/ContextBadge';

export default function App() {
  const [pageUrl, setPageUrl] = useState('');
  const [contextAvailable, setContextAvailable] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [urlInput, setUrlInput] = useState('http://localhost:3005');
  const [connecting, setConnecting] = useState(false);
  const [authError, setAuthError] = useState('');

  const {
    isConnected, synkoraUrl, setConnected,
    selectedAgentId, agents,
    pendingSelectionText,
  } = useExtensionStore();

  const { selectAgent, setDefaultAgent, defaultAgentId, loading: agentsLoading } = useAgents();

  const handleConnect = async () => {
    const url = urlInput.trim().replace(/\/$/, '');
    if (!url) return;
    setAuthError('');
    try {
      await storeSynkoraUrl(url);
      const origin = new URL(url).origin + '/*';
      const granted = await chrome.permissions.request({ origins: [origin] });
      if (!granted) { setAuthError('Permission denied — cannot connect to Synkora'); return; }
      setConnecting(true);
      const { url: authUrl, state } = await buildAuthUrl(url);
      chrome.identity.launchWebAuthFlow({ url: authUrl, interactive: true }, async (responseUrl) => {
        if (chrome.runtime.lastError || !responseUrl) {
          setAuthError(chrome.runtime.lastError?.message ?? 'Authorization cancelled');
          setConnecting(false);
          return;
        }
        try {
          const params = new URLSearchParams(new URL(responseUrl).search);
          const code = params.get('code');
          const returnedState = params.get('state');
          const apiUrl = params.get('api_url');
          if (!code || returnedState !== state) throw new Error('Invalid callback parameters');
          if (apiUrl) await storeApiUrl(apiUrl);
          await exchangeCodeForTokens(url, code, returnedState, apiUrl ?? undefined);
          setConnected(true, url);
        } catch (err) {
          setAuthError(err instanceof Error ? err.message : 'Auth failed');
          setConnecting(false);
        }
      });
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Failed to start auth');
      setConnecting(false);
    }
  };

  // Initialize: check auth + get current tab URL
  useEffect(() => {
    const init = async () => {
      const [tokenData, url] = await Promise.all([loadAccessToken(), loadSynkoraUrl()]);
      if (tokenData && url) {
        setConnected(true, url);
      } else if (url) {
        setUrlInput(url);
      }

      // Get current tab URL
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (tab?.url) {
        setPageUrl(tab.url);
        // Check if content script is available
        try {
          await chrome.tabs.sendMessage(tab.id!, { type: 'GET_PAGE_CONTEXT', mode: 'viewport' });
          setContextAvailable(true);
        } catch {
          setContextAvailable(false);
        }
      }

      setInitializing(false);
    };
    init();
  }, [setConnected]);

  // Check for pending selection text from right-click
  useEffect(() => {
    const checkSelection = async () => {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (!tabId) return;
      const key = `snkr_selection_${tabId}`;
      const stored = await chrome.storage.session.get(key);
      const selection = stored[key] as { text: string; timestamp: number } | undefined;
      if (selection && Date.now() - selection.timestamp < 30_000) {
        useExtensionStore.getState().setPendingSelectionText(selection.text);
        await chrome.storage.session.remove(key);
      }
    };
    checkSelection();
  }, []);

  // Listen for tab URL changes
  useEffect(() => {
    const handler = (_: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
      if (changeInfo.url && tab.active) {
        setPageUrl(changeInfo.url);
      }
    };
    chrome.tabs.onUpdated.addListener(handler);
    return () => chrome.tabs.onUpdated.removeListener(handler);
  }, []);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  if (initializing) {
    return (
      <div className="flex flex-col h-screen bg-white items-center justify-center">
        <div className="w-5 h-5 border-2 border-synkora-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex flex-col h-screen bg-white items-center justify-center px-6 gap-5">
        <div className="w-10 h-10 rounded-xl bg-synkora-600 flex items-center justify-center">
          <span className="text-white font-bold text-lg">S</span>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-gray-800 mb-1">Connect to Synkora</p>
          <p className="text-xs text-gray-500">Enter your Synkora instance URL to get started.</p>
        </div>
        {authError && (
          <div className="w-full flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-xs text-red-600">
            <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
            <span>{authError}</span>
          </div>
        )}
        <div className="w-full">
          <label className="block text-xs text-gray-500 mb-1">Synkora instance URL</label>
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
            placeholder="https://your-synkora.com"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 outline-none focus:border-synkora-400 mb-3"
          />
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full bg-synkora-600 hover:bg-synkora-700 disabled:opacity-60 text-white text-sm font-medium py-2 rounded-lg transition-colors"
          >
            {connecting ? 'Waiting for authorization…' : 'Connect with Synkora'}
          </button>
          <p className="text-[10px] text-gray-400 text-center mt-2">
            Opens your Synkora dashboard to authorize access
          </p>
        </div>
      </div>
    );
  }

  if (agentsLoading) {
    return (
      <div className="flex flex-col h-screen bg-white font-sans">
        <div className="border-b border-gray-100 px-3 py-2.5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gray-200 animate-pulse flex-shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-gray-200 rounded-full animate-pulse w-28" />
            <div className="h-2 bg-gray-100 rounded-full animate-pulse w-20" />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="space-y-4 px-4 w-full">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-2.5">
                <div className="w-7 h-7 rounded-full bg-gray-100 animate-pulse flex-shrink-0 mt-1" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 bg-gray-100 rounded-full animate-pulse" style={{ width: `${55 + i * 10}%` }} />
                  <div className="h-3 bg-gray-100 rounded-full animate-pulse" style={{ width: `${35 + i * 8}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!selectedAgent) {
    return (
      <div className="flex flex-col h-screen bg-white font-sans items-center justify-center px-6 text-center gap-3">
        <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mb-1">
          <span className="text-2xl text-gray-400">✦</span>
        </div>
        <p className="text-[14px] font-semibold text-gray-700">No agents found</p>
        <p className="text-[12px] text-gray-400 leading-relaxed">Create an agent in your Synkora dashboard to get started.</p>
        <a
          href={`${synkoraUrl}/agents`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] text-synkora-600 font-medium hover:underline"
        >
          Open Synkora dashboard →
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-white font-sans">
      {/* Header */}
      <div className="border-b border-gray-100 bg-white/95 backdrop-blur-sm px-1 pt-1.5 pb-0 flex-shrink-0">
        <AgentPicker
          agents={agents}
          selectedAgentId={selectedAgentId}
          defaultAgentId={defaultAgentId}
          onSelect={selectAgent}
          onSetDefault={setDefaultAgent}
        />
        <div className="px-3 pb-1.5">
          <ContextBadge pageUrl={pageUrl} contextAvailable={contextAvailable} />
        </div>
      </div>

      {/* Chat */}
      <ChatPanel
        agent={selectedAgent}
        pageUrl={pageUrl}
        contextAvailable={contextAvailable}
      />
    </div>
  );
}
