import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, LogOut } from 'lucide-react';
import {
  loadAccessToken, loadSynkoraUrl, storeSynkoraUrl,
  buildAuthUrl, exchangeCodeForTokens, storeApiUrl, clearTokens,
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

  // Try running a no-op script to verify scripting permission for the current tab.
  // Sets contextAvailable based on whether it actually works.
  const checkScriptingAccess = useCallback(async (url: string) => {
    if (!url.startsWith('http')) {
      setContextAvailable(false);
      return;
    }
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tabId = tabs[0]?.id;
      if (!tabId) { setContextAvailable(false); return; }
      await chrome.scripting.executeScript({ target: { tabId }, func: () => true });
      setContextAvailable(true);
    } catch {
      setContextAvailable(false);
    }
  }, []);

  const grantPagePermission = useCallback(async (url: string) => {
    if (!url.startsWith('http')) return;
    try {
      const origin = new URL(url).origin + '/*';
      const granted = await chrome.permissions.request({ origins: [origin] });
      if (granted) setContextAvailable(true);
    } catch {
      // ignore — user may have cancelled
    }
  }, []);

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

      // Get current tab URL and verify scripting access
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];
      if (tab?.url) {
        setPageUrl(tab.url);
        await checkScriptingAccess(tab.url);
      }

      setInitializing(false);
    };
    init();
  }, [setConnected, checkScriptingAccess]);

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

  // Listen for tab URL changes — re-check scripting access on navigation
  useEffect(() => {
    const handler = (_: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
      if (!tab.active) return;
      if (changeInfo.url) {
        setPageUrl(changeInfo.url);
        setContextAvailable(false); // reset until verified
      }
      // Re-check once the page is fully loaded (not on every intermediate state)
      if (changeInfo.status === 'complete' && tab.url) {
        checkScriptingAccess(tab.url);
      }
    };
    chrome.tabs.onUpdated.addListener(handler);
    return () => chrome.tabs.onUpdated.removeListener(handler);
  }, [checkScriptingAccess]);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  const handleDisconnect = async () => {
    await clearTokens();
    setConnected(false);
  };

  if (initializing) {
    return (
      <div className="flex flex-col h-screen bg-brand-canvas items-center justify-center">
        <div className="w-5 h-5 border-2 border-synkora-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex flex-col h-screen bg-brand-canvas items-center justify-center px-6 gap-5">
        <div className="w-11 h-11 rounded-2xl bg-synkora-400 flex items-center justify-center shadow-soft">
          <span className="text-brand-ink font-bold text-lg">S</span>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-brand-ink mb-1">Connect to Synkora</p>
          <p className="text-xs text-brand-muted">Enter your Synkora instance URL to get started.</p>
        </div>
        {authError && (
          <div className="w-full flex items-start gap-2 bg-[#fff2ec] border border-[#f2d1bd] rounded-2xl px-3 py-2 text-xs text-[#8b3f1e]">
            <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
            <span>{authError}</span>
          </div>
        )}
        <div className="w-full">
          <label className="block text-xs text-brand-muted mb-1">Synkora instance URL</label>
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
            placeholder="https://your-synkora.com"
            className="w-full border border-brand-line bg-brand-panel rounded-2xl px-3 py-2.5 text-sm text-brand-ink outline-none focus:border-synkora-400 focus:shadow-[0_0_0_3px_rgba(121,223,188,0.18)] mb-3"
          />
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full bg-synkora-400 hover:bg-synkora-300 disabled:opacity-60 text-brand-ink text-sm font-semibold py-2.5 rounded-2xl transition-colors shadow-soft"
          >
            {connecting ? 'Waiting for authorization…' : 'Connect with Synkora'}
          </button>
          <p className="text-[10px] text-brand-muted/80 text-center mt-2">
            Opens your Synkora dashboard to authorize access
          </p>
        </div>
      </div>
    );
  }

  if (agentsLoading) {
    return (
      <div className="flex flex-col h-screen bg-brand-canvas font-sans">
        <div className="border-b border-brand-line px-3 py-2.5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-brand-surface animate-pulse flex-shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-brand-surface rounded-full animate-pulse w-28" />
            <div className="h-2 bg-brand-panel rounded-full animate-pulse w-20" />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="space-y-4 px-4 w-full">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-2.5">
                <div className="w-7 h-7 rounded-full bg-brand-surface animate-pulse flex-shrink-0 mt-1" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 bg-brand-surface rounded-full animate-pulse" style={{ width: `${55 + i * 10}%` }} />
                  <div className="h-3 bg-brand-surface rounded-full animate-pulse" style={{ width: `${35 + i * 8}%` }} />
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
      <div className="flex flex-col h-screen bg-brand-canvas font-sans items-center justify-center px-6 text-center gap-3">
        <div className="w-14 h-14 rounded-[22px] bg-brand-surface flex items-center justify-center mb-1 shadow-soft">
          <span className="text-2xl text-synkora-600">✦</span>
        </div>
        <p className="text-[14px] font-semibold text-brand-ink">No agents found</p>
        <p className="text-[12px] text-brand-muted leading-relaxed">Create an agent in your Synkora dashboard to get started.</p>
        <a
          href={`${synkoraUrl}/agents`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] text-synkora-700 font-medium hover:underline"
        >
          Open Synkora dashboard →
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-brand-canvas font-sans">
      {/* Header */}
      <div className="border-b border-brand-line bg-brand-canvas/95 backdrop-blur-sm px-1 pt-1.5 pb-1 flex-shrink-0">
        <div className="flex items-center gap-1">
          <div className="flex-1 min-w-0">
            <AgentPicker
              agents={agents}
              selectedAgentId={selectedAgentId}
              defaultAgentId={defaultAgentId}
              onSelect={selectAgent}
              onSetDefault={setDefaultAgent}
            />
          </div>
          <button
            onClick={handleDisconnect}
            title="Disconnect"
            className="flex-shrink-0 p-2 rounded-xl text-brand-muted hover:text-[#8b3f1e] hover:bg-[#fff2ec] transition-colors mr-1"
          >
            <LogOut size={14} />
          </button>
        </div>
        <div className="px-3 pb-1.5">
          <ContextBadge
            pageUrl={pageUrl}
            contextAvailable={contextAvailable}
            onGrantPermission={() => grantPagePermission(pageUrl)}
          />
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
