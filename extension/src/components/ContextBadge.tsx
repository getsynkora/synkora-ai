import { Globe, EyeOff, ChevronDown, ShieldAlert } from 'lucide-react';
import { useState } from 'react';
import { useExtensionStore } from '@/store/extension';

interface Props {
  pageUrl: string;
  contextAvailable: boolean;
  onGrantPermission?: () => void;
}

export function ContextBadge({ pageUrl, contextAvailable, onGrantPermission }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const {
    pageContextEnabled, pageContextMode,
    setPageContextEnabled, setPageContextMode,
  } = useExtensionStore();

  const hostname = (() => {
    try { return new URL(pageUrl).hostname; } catch { return pageUrl; }
  })();

  const isOn = pageContextEnabled && contextAvailable;
  const isHttpPage = pageUrl.startsWith('http');
  const needsPermission = isHttpPage && !contextAvailable;

  return (
    <div className="relative flex items-center gap-1.5 text-xs text-brand-muted">
      {needsPermission && onGrantPermission ? (
        <button
          onClick={onGrantPermission}
          title="Grant access to read this page"
          className="flex items-center gap-1 text-[#b35630] hover:text-[#944726] transition-colors"
        >
          <ShieldAlert size={11} />
          <span className="truncate max-w-[120px]">{hostname}</span>
          <span className="underline underline-offset-2">· Grant page access</span>
        </button>
      ) : (
        <button
          onClick={() => contextAvailable && setPageContextEnabled(!pageContextEnabled)}
          title={
            !contextAvailable
              ? 'Page context unavailable on this page'
              : pageContextEnabled
              ? 'Click to disable page context'
              : 'Click to enable page context'
          }
          className={`flex items-center gap-1 transition-colors ${
            contextAvailable ? 'cursor-pointer hover:text-brand-ink' : 'cursor-default opacity-50'
          } ${isOn ? 'text-synkora-700' : ''}`}
        >
          {isOn ? <Globe size={11} /> : <EyeOff size={11} />}
          <span className="truncate max-w-[120px]">{hostname}</span>
          <span className={isOn ? 'text-synkora-600' : ''}>
            · Page context: {isOn ? 'ON' : 'OFF'}
          </span>
        </button>
      )}

      {isOn && (
        <div className="relative">
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="flex items-center gap-0.5 text-brand-muted hover:text-brand-ink transition-colors"
          >
            <span className="text-[10px]">{pageContextMode === 'viewport' ? 'Viewport' : 'Full page'}</span>
            <ChevronDown size={10} className={menuOpen ? 'rotate-180' : ''} />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute bottom-full right-0 mb-1 bg-brand-panel border border-brand-line rounded-xl shadow-soft z-20 py-1 min-w-[120px]">
                {(['viewport', 'full'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => { setPageContextMode(m); setMenuOpen(false); }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-brand-surface transition-colors ${
                      pageContextMode === m ? 'text-synkora-700 font-medium' : 'text-brand-ink'
                    }`}
                  >
                    {m === 'viewport' ? 'Viewport only' : 'Full page'}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
