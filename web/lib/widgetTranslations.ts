/**
 * Per-language text for a chat widget, stored in the widget's
 * `theme_config.translations` as `{ "de": { title: "...", ... } }`.
 *
 * The API serves the entry for the language the chat is opened in and falls
 * back to the widget's default text for anything left out.
 */

export interface TranslatedPrompt {
  title: string;
  description: string;
  icon: string;
  prompt: string;
}

export interface WidgetTranslation {
  title?: string;
  welcome_message?: string;
  placeholder?: string;
  agent_description?: string;
  privacy_policy_text?: string;
  suggestion_prompts?: TranslatedPrompt[];
}

export type WidgetTranslations = Record<string, WidgetTranslation>;

/** Languages offered in the editor. Any other BCP-47 code can be typed in. */
export const TRANSLATION_LANGUAGES: { code: string; label: string }[] = [
  { code: "de", label: "German" },
  { code: "en", label: "English" },
];

const TEXT_FIELDS = [
  "title",
  "welcome_message",
  "placeholder",
  "agent_description",
  "privacy_policy_text",
] as const;

const LANGUAGE_CODE = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$/;

/** "DE" -> "de", "pt_BR" -> "pt-BR"; null when it is not a language code. */
export function normalizeLanguageCode(input: string): string | null {
  const code = input.trim().replace(/_/g, "-");
  if (!code || code.length > 20 || !LANGUAGE_CODE.test(code)) return null;
  const [primary, ...rest] = code.split("-");
  return [primary.toLowerCase(), ...rest].join("-");
}

/** Reads what the API stored, ignoring anything that is not the expected shape. */
export function readTranslations(raw: unknown): WidgetTranslations {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const result: WidgetTranslations = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const code = normalizeLanguageCode(key);
    if (code && value && typeof value === "object" && !Array.isArray(value)) {
      result[code] = value as WidgetTranslation;
    }
  }
  return result;
}

/**
 * What to save: trimmed text, no blank fields, no prompts without a title or
 * prompt text, and no languages left with nothing in them.
 */
export function pruneTranslations(translations: WidgetTranslations): WidgetTranslations {
  const result: WidgetTranslations = {};
  for (const [code, entry] of Object.entries(translations)) {
    const clean: WidgetTranslation = { ...entry };
    for (const field of TEXT_FIELDS) {
      const value = (entry[field] ?? "").trim();
      if (value) clean[field] = value;
      else delete clean[field];
    }
    const prompts = (entry.suggestion_prompts ?? [])
      .map((p) => ({
        title: p.title.trim(),
        description: p.description.trim(),
        icon: p.icon,
        prompt: p.prompt.trim(),
      }))
      .filter((p) => p.title && p.prompt);
    if (prompts.length > 0) clean.suggestion_prompts = prompts;
    else delete clean.suggestion_prompts;

    if (Object.keys(clean).length > 0) result[code] = clean;
  }
  return result;
}
