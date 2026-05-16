import { extractViewportText, extractFullPageText } from '@/lib/page-extractor';
import type { PageContextMode } from '@/types';

export default defineContentScript({
  matches: ['<all_urls>'],
  main() {
    // Respond to page context requests from the side panel (pull model)
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      // Validate sender is our extension
      if (sender.id !== chrome.runtime.id) return;

      if (message.type === 'GET_PAGE_CONTEXT') {
        const mode = (message.mode ?? 'viewport') as PageContextMode;
        try {
          const text = mode === 'full' ? extractFullPageText() : extractViewportText();
          sendResponse({
            text,
            url: window.location.href,
            title: document.title,
            mode,
          });
        } catch {
          sendResponse(null);
        }
        return true; // async response
      }
    });
  },
});
