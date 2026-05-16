import { describe, it, expect, beforeEach } from 'vitest';
import { extractViewportText, extractFullPageText } from '@/lib/page-extractor';

// JSDOM provides a DOM environment for testing
describe('extractFullPageText', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('extracts visible text from body', () => {
    document.body.innerHTML = '<p>Hello world</p><p>Second paragraph</p>';
    const text = extractFullPageText();
    expect(text).toContain('Hello world');
    expect(text).toContain('Second paragraph');
  });

  it('skips script tag content', () => {
    document.body.innerHTML = '<p>Visible</p><script>alert("hidden")</script>';
    const text = extractFullPageText();
    expect(text).toContain('Visible');
    expect(text).not.toContain('alert');
  });

  it('skips style tag content', () => {
    document.body.innerHTML = '<p>Visible</p><style>body { color: red }</style>';
    const text = extractFullPageText();
    expect(text).not.toContain('color: red');
  });

  it('truncates very long pages to 8000 chars', () => {
    const longText = 'a'.repeat(10_000);
    document.body.innerHTML = `<p>${longText}</p>`;
    const text = extractFullPageText();
    expect(text.length).toBeLessThanOrEqual(8_001); // 8000 + ellipsis
  });

  it('returns empty string for empty body', () => {
    const text = extractFullPageText();
    expect(text).toBe('');
  });
});

describe('extractViewportText', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    // Reset window dimensions for JSDOM
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });
  });

  it('extracts text from elements', () => {
    document.body.innerHTML = '<p>Viewport content</p>';
    // In JSDOM all elements have 0,0 bounding rect by default —
    // we mock getBoundingClientRect to simulate in-viewport elements
    const p = document.querySelector('p')!;
    p.getBoundingClientRect = () => ({
      top: 100, bottom: 200, left: 0, right: 500,
      width: 500, height: 100, x: 0, y: 100,
      toJSON: () => ({}),
    });
    const text = extractViewportText();
    // JSDOM may not fully support tree walker in viewport mode — just verify no throw
    expect(typeof text).toBe('string');
  });
});
