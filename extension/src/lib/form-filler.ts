export interface FillField {
  index: number;
  value: string;
}

export interface FillBlock {
  fields: FillField[];
}

/**
 * Inject a fill script into the active tab.
 * Uses the native HTMLInputElement value setter so React/Vue/Angular
 * state management picks up the change via the synthetic events we fire.
 */
export async function fillFormOnPage(fields: FillField[]): Promise<{ filled: number; errors: string[] }> {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabId = tabs[0]?.id;
  if (!tabId) throw new Error('No active tab found');

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (fillFields: FillField[]) => {
      const inputs = Array.from(
        document.querySelectorAll<HTMLElement>(
          'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), select, textarea'
        )
      );

      let filled = 0;
      const errors: string[] = [];

      for (const field of fillFields) {
        const el = inputs[field.index] as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | undefined;
        if (!el) {
          errors.push(`No element at index ${field.index}`);
          continue;
        }

        try {
          if (el.tagName === 'SELECT') {
            const select = el as HTMLSelectElement;
            const target = field.value.toLowerCase();
            let matched = false;
            for (const opt of Array.from(select.options)) {
              if (opt.value.toLowerCase() === target || opt.text.toLowerCase() === target) {
                select.value = opt.value;
                matched = true;
                break;
              }
            }
            if (!matched) select.value = field.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            filled++;
          } else {
            // Use native setter to bypass React/Vue synthetic event wrappers
            const proto = el.tagName === 'TEXTAREA'
              ? window.HTMLTextAreaElement.prototype
              : window.HTMLInputElement.prototype;
            const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;

            if (nativeSetter) {
              nativeSetter.call(el, field.value);
            } else {
              (el as HTMLInputElement).value = field.value;
            }

            // Fire both events — React uses 'input', Angular uses 'change'
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            filled++;
          }
        } catch (e) {
          errors.push(`Field ${field.index}: ${e instanceof Error ? e.message : String(e)}`);
        }
      }

      return { filled, errors };
    },
    args: [fields],
  });

  return (results[0]?.result as { filled: number; errors: string[] }) ?? { filled: 0, errors: ['Script returned no result'] };
}

/**
 * Parse a fill-form JSON block from agent response text.
 * Expects: ```fill-form\n{"fields":[...]}\n```
 */
export function parseFillBlock(content: string): FillBlock | null {
  const match = content.match(/```fill-form\s*([\s\S]*?)```/);
  if (!match) return null;
  try {
    const parsed = JSON.parse(match[1].trim()) as { fields?: unknown };
    if (!Array.isArray(parsed.fields)) return null;
    const fields = (parsed.fields as unknown[]).filter(
      (f): f is FillField =>
        typeof f === 'object' && f !== null &&
        typeof (f as FillField).index === 'number' &&
        typeof (f as FillField).value === 'string'
    );
    return fields.length > 0 ? { fields } : null;
  } catch {
    return null;
  }
}

/**
 * Split agent response into text segments and fill-form block segments.
 */
export type ContentSegment =
  | { type: 'text'; content: string }
  | { type: 'fill'; fields: FillField[]; raw: string };

export function splitContentSegments(content: string): ContentSegment[] {
  const regex = /```fill-form\s*[\s\S]*?```/g;
  const segments: ContentSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: content.slice(lastIndex, match.index) });
    }
    const block = parseFillBlock(match[0]);
    if (block) {
      segments.push({ type: 'fill', fields: block.fields, raw: match[0] });
    } else {
      segments.push({ type: 'text', content: match[0] });
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    segments.push({ type: 'text', content: content.slice(lastIndex) });
  }

  return segments.length > 0 ? segments : [{ type: 'text', content }];
}
