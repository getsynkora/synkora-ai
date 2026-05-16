import { loadAccessToken, loadSynkoraUrl, refreshAccessToken, isTokenExpiringSoon } from '@/lib/auth';
import { useExtensionStore } from '@/store/extension';

export default defineBackground(() => {
  // ── Side panel: open on toolbar icon click ───────────────────────────────
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

  // ── Keepalive alarm — fires every 20s to prevent service worker termination ──
  chrome.alarms.create('snkr_keepalive', { periodInMinutes: 1 / 3 });

  // ── Token refresh alarm — fires every 5 minutes ──────────────────────────
  chrome.alarms.create('snkr_token_refresh', { periodInMinutes: 5 });

  chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === 'snkr_token_refresh') {
      const tokenData = await loadAccessToken();
      if (tokenData && isTokenExpiringSoon(tokenData.expiresAt)) {
        const url = await loadSynkoraUrl();
        if (url) await refreshAccessToken(url);
      }
    }
    // snkr_keepalive: no-op — just keeps service worker alive
  });

  // ── Right-click context menu ──────────────────────────────────────────────
  chrome.contextMenus.create({
    id: 'snkr_ask_agent',
    title: 'Ask Synkora Agent',
    contexts: ['selection'],
  });

  chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId !== 'snkr_ask_agent') return;
    if (!tab?.id) return;

    const selectedText = info.selectionText ?? '';
    if (!selectedText.trim()) return;

    // Store selected text for the side panel to pick up
    await chrome.storage.session.set({
      [`snkr_selection_${tab.id}`]: {
        text: selectedText,
        tabId: tab.id,
        timestamp: Date.now(),
      },
    });

    // Open the side panel
    await chrome.sidePanel.open({ tabId: tab.id });
  });

  // ── Message routing (from side panel / popup) ─────────────────────────────
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Only accept messages from our own extension pages (not content scripts)
    if (sender.id !== chrome.runtime.id) return;
    if (sender.tab) return; // content script sender — ignore auth messages

    if (message.type === 'GET_AUTH_STATUS') {
      loadAccessToken().then((token) => {
        sendResponse({ connected: !!token });
      });
      return true; // async response
    }

    if (message.type === 'LOGOUT') {
      import('@/lib/auth').then(({ clearTokens }) => clearTokens()).then(() => {
        sendResponse({ ok: true });
      });
      return true;
    }
  });
});
