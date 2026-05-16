import { useCallback } from 'react';
import { useExtensionStore } from '@/store/extension';
import type { PageContext } from '@/types';

export function usePageContext() {
  const { pageContextEnabled, pageContextMode } = useExtensionStore();

  const getContext = useCallback(async (): Promise<PageContext | null> => {
    if (!pageContextEnabled) return null;

    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab?.id) return null;

    try {
      const response = await chrome.tabs.sendMessage(tab.id, {
        type: 'GET_PAGE_CONTEXT',
        mode: pageContextMode,
      }) as PageContext | null;
      return response ?? null;
    } catch {
      // Content script not available on this page (e.g. chrome:// pages)
      return null;
    }
  }, [pageContextEnabled, pageContextMode]);

  return { getContext, pageContextEnabled, pageContextMode };
}
