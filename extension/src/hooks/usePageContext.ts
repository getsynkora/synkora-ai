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

          // --- Page text ---
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

          let pageText = chunks.join(' ').replace(/\s+/g, ' ').trim();
          if (pageText.length > MAX_CHARS) pageText = pageText.slice(0, MAX_CHARS) + '…';

          // --- Form fields ---
          const inputs = Array.from(document.querySelectorAll<HTMLElement>(
            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), select, textarea'
          ));

          const formFields: string[] = [];
          let fieldIndex = 0;
          for (const el of inputs) {
            const inp = el as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
            const st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden') continue;

            // Resolve label: for= → aria-label → aria-labelledby → wrapping <label> → placeholder → name
            let label = '';
            if (inp.id) {
              try { label = document.querySelector(`label[for="${CSS.escape(inp.id)}"]`)?.textContent?.trim() ?? ''; } catch { /* ignore */ }
            }
            if (!label) label = el.getAttribute('aria-label')?.trim() ?? '';
            if (!label) {
              const llby = el.getAttribute('aria-labelledby');
              if (llby) label = document.getElementById(llby)?.textContent?.trim() ?? '';
            }
            if (!label) {
              const wrapLabel = el.closest('label');
              if (wrapLabel) {
                const clone = wrapLabel.cloneNode(true) as HTMLElement;
                clone.querySelector('input, select, textarea')?.remove();
                label = clone.textContent?.trim() ?? '';
              }
            }
            if (!label) label = (inp as HTMLInputElement).placeholder?.trim() ?? '';
            if (!label) label = el.getAttribute('name')?.trim() ?? '';

            const type = el.tagName === 'SELECT' ? 'select'
              : el.tagName === 'TEXTAREA' ? 'textarea'
              : ((inp as HTMLInputElement).type || 'text');
            const value = inp.value?.trim() ?? '';
            const placeholder = (inp as HTMLInputElement).placeholder?.trim() ?? '';
            const req = inp.required ? ' [required]' : '';

            // [N] index prefix is used by the fill-form JSON block to locate this element
            let fieldStr = `  - [${fieldIndex}] ${label || '(field)'}`;
            if (type !== 'text' && type !== 'textarea') fieldStr += ` (${type})`;
            fieldStr += req;
            if (value) fieldStr += `: "${value}"`;
            else if (placeholder && placeholder !== label) fieldStr += ` — e.g. "${placeholder}"`;
            formFields.push(fieldStr);
            fieldIndex++;
          }

          const formSection = formFields.length > 0
            ? `\n\n[Form fields on this page]\n${formFields.join('\n')}`
            : '';

          return pageText + formSection;
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
