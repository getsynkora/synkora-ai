import { useCallback } from 'react';
import { useExtensionStore } from '@/store/extension';
import type { PageContext } from '@/types';

export function usePageContext() {
  const { pageContextEnabled, pageContextMode } = useExtensionStore();

  const getContext = useCallback(async (): Promise<PageContext | null> => {
    if (!pageContextEnabled) return null;

    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab?.id || !tab.url?.startsWith('http')) return null;

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (mode: string) => {
          const MAX_CHARS = mode === 'full' ? 8000 : 3000;
          const SKIP_TAGS = new Set([
            'SCRIPT', 'STYLE', 'NOSCRIPT', 'HEAD', 'META', 'LINK',
            'SVG', 'CANVAS', 'IFRAME', 'OBJECT', 'EMBED',
          ]);

          const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
            {
              acceptNode(node) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                  const el = node as Element;
                  if (SKIP_TAGS.has(el.tagName)) return NodeFilter.FILTER_REJECT;
                  const style = window.getComputedStyle(el);
                  if (style.display === 'none' || style.visibility === 'hidden') {
                    return NodeFilter.FILTER_REJECT;
                  }
                }
                return NodeFilter.FILTER_ACCEPT;
              },
            }
          );

          const vw = window.innerWidth;
          const vh = window.innerHeight;
          const chunks: string[] = [];
          let charCount = 0;
          let node = walker.nextNode();

          while (node && charCount < MAX_CHARS) {
            if (node.nodeType === Node.TEXT_NODE) {
              const text = node.textContent?.trim();
              if (!text) { node = walker.nextNode(); continue; }

              if (mode === 'full') {
                chunks.push(text);
                charCount += text.length;
              } else {
                const parent = node.parentElement;
                if (parent) {
                  const rect = parent.getBoundingClientRect();
                  if (rect.bottom > 0 && rect.top < vh && rect.right > 0 && rect.left < vw) {
                    chunks.push(text);
                    charCount += text.length;
                  }
                }
              }
            }
            node = walker.nextNode();
          }

          const result = chunks.join(' ').replace(/\s+/g, ' ').trim();
          return result.length > MAX_CHARS ? result.slice(0, MAX_CHARS) + '…' : result;
        },
        args: [pageContextMode],
      });

      const text = results[0]?.result as string | undefined;
      if (!text) return null;

      return {
        text,
        url: tab.url ?? '',
        title: tab.title ?? '',
        mode: pageContextMode,
      };
    } catch {
      return null;
    }
  }, [pageContextEnabled, pageContextMode]);

  return { getContext, pageContextEnabled, pageContextMode };
}
