/**
 * Page text extraction utilities for content script.
 * Supports viewport-only (default) and full-page modes.
 */

const FULL_PAGE_MAX_CHARS = 8_000;
const VIEWPORT_MAX_CHARS = 3_000;

// Tags whose text content is not useful for context
const SKIP_TAGS = new Set([
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'HEAD', 'META', 'LINK',
  'SVG', 'CANVAS', 'IFRAME', 'OBJECT', 'EMBED',
]);

/**
 * Extract text from elements visible in the current viewport using IntersectionObserver snapshot.
 * Falls back to a simpler heuristic when IntersectionObserver is not available.
 */
export function extractViewportText(): string {
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
  while (node && charCount < VIEWPORT_MAX_CHARS) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.trim();
      if (!text) { node = walker.nextNode(); continue; }

      // Check if the parent element is in the viewport
      const parent = node.parentElement;
      if (parent) {
        const rect = parent.getBoundingClientRect();
        const inViewport =
          rect.bottom > 0 && rect.top < vh &&
          rect.right > 0 && rect.left < vw;
        if (inViewport) {
          chunks.push(text);
          charCount += text.length;
        }
      }
    }
    node = walker.nextNode();
  }

  return chunks.join(' ').replace(/\s+/g, ' ').trim();
}

/**
 * Extract all visible text from the page (full-page mode).
 * Truncates to FULL_PAGE_MAX_CHARS.
 */
export function extractFullPageText(): string {
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

  const chunks: string[] = [];
  let charCount = 0;

  let node = walker.nextNode();
  while (node && charCount < FULL_PAGE_MAX_CHARS) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.trim();
      if (text) {
        chunks.push(text);
        charCount += text.length;
      }
    }
    node = walker.nextNode();
  }

  const result = chunks.join(' ').replace(/\s+/g, ' ').trim();
  return result.length > FULL_PAGE_MAX_CHARS
    ? result.slice(0, FULL_PAGE_MAX_CHARS) + '…'
    : result;
}
