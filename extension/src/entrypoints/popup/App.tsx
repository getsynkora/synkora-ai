import { useEffect, useState } from 'react';
import { ExternalLink, LogOut, Settings, CheckCircle2, AlertCircle } from 'lucide-react';
import {
  buildAuthUrl, exchangeCodeForTokens, clearTokens,
  loadAccessToken, loadSynkoraUrl, storeSynkoraUrl, storeApiUrl,
} from '@/lib/auth';
import { useExtensionStore } from '@/store/extension';

type Screen = 'loading' | 'setup' | 'connecting' | 'connected' | 'error';

export default function App() {
  const [screen, setScreen] = useState<Screen>('loading');
  const [urlInput, setUrlInput] = useState('http://localhost:3005');
  const [errorMsg, setErrorMsg] = useState('');
  const { isConnected, synkoraUrl, setConnected } = useExtensionStore();

  useEffect(() => {
    // Check existing session
    loadAccessToken().then(async (token) => {
      if (token) {
        const url = await loadSynkoraUrl();
        setConnected(true, url ?? '');
        setScreen('connected');
      } else {
        const savedUrl = await loadSynkoraUrl();
        if (savedUrl) setUrlInput(savedUrl);
        setScreen('setup');
      }
    });
  }, [setConnected]);

  const handleConnect = async () => {
    const url = urlInput.trim().replace(/\/$/, '');
    if (!url) return;

    try {
      await storeSynkoraUrl(url);

      const origin = new URL(url).origin + '/*';
      const granted = await chrome.permissions.request({ origins: [origin] });
      if (!granted) {
        setErrorMsg('Permission denied — cannot connect to Synkora');
        setScreen('error');
        return;
      }

      setScreen('connecting');
      const { url: authUrl, state } = await buildAuthUrl(url);
      chrome.identity.launchWebAuthFlow({ url: authUrl, interactive: true }, async (responseUrl) => {
        if (chrome.runtime.lastError || !responseUrl) {
          setErrorMsg(chrome.runtime.lastError?.message ?? 'Authorization cancelled');
          setScreen('error');
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
          setScreen('connected');
        } catch (err) {
          setErrorMsg(err instanceof Error ? err.message : 'Auth failed');
          setScreen('error');
        }
      });
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to start auth');
      setScreen('error');
    }
  };

  const handleLogout = async () => {
    await clearTokens();
    setConnected(false);
    setScreen('setup');
  };

  if (screen === 'loading') {
    return (
      <div className="w-80 h-40 flex items-center justify-center bg-white">
        <div className="w-5 h-5 border-2 border-synkora-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (screen === 'setup' || screen === 'error') {
    return (
      <div className="w-80 bg-white p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-synkora-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">S</span>
          </div>
          <span className="text-sm font-semibold text-gray-800">Connect to Synkora</span>
        </div>

        {screen === 'error' && (
          <div className="mb-3 flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2 text-xs text-red-600">
            <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <label className="block text-xs text-gray-500 mb-1">Synkora instance URL</label>
        <input
          type="url"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          placeholder="https://your-synkora-instance.com"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 outline-none focus:border-synkora-400 mb-3"
          onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
        />

        <button
          onClick={handleConnect}
          className="w-full bg-synkora-600 hover:bg-synkora-700 text-white text-sm font-medium py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <ExternalLink size={13} />
          Connect with Synkora
        </button>
        <p className="text-[10px] text-gray-400 text-center mt-2">
          Opens your Synkora dashboard to authorize access
        </p>
      </div>
    );
  }

  if (screen === 'connecting') {
    return (
      <div className="w-80 h-40 flex flex-col items-center justify-center bg-white gap-3">
        <div className="w-5 h-5 border-2 border-synkora-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-500">Waiting for authorization…</p>
        <p className="text-xs text-gray-400">Complete sign-in in the browser tab</p>
      </div>
    );
  }

  return (
    <div className="w-80 bg-white p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-6 h-6 rounded-md bg-synkora-600 flex items-center justify-center">
          <span className="text-white text-xs font-bold">S</span>
        </div>
        <span className="text-sm font-semibold text-gray-800">Synkora Agent</span>
        <CheckCircle2 size={14} className="text-green-500 ml-auto" />
      </div>

      <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-500 mb-4 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
        Connected to <span className="font-medium text-gray-700 truncate">{synkoraUrl}</span>
      </div>

      <p className="text-xs text-gray-500 mb-3">
        Click the side panel icon or press <kbd className="bg-gray-100 px-1 rounded text-[10px]">Ctrl+Shift+S</kbd> to open the agent panel.
      </p>

      <div className="flex gap-2">
        <button
          onClick={() => chrome.tabs.create({ url: `${synkoraUrl}/settings` })}
          className="flex-1 flex items-center justify-center gap-1.5 border border-gray-200 text-gray-600 text-xs py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <Settings size={12} />
          Settings
        </button>
        <button
          onClick={handleLogout}
          className="flex-1 flex items-center justify-center gap-1.5 border border-red-100 text-red-500 text-xs py-1.5 rounded-lg hover:bg-red-50 transition-colors"
        >
          <LogOut size={12} />
          Disconnect
        </button>
      </div>
    </div>
  );
}
