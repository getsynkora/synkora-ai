/**
 * Text shown by the extension, in the browser's language.
 *
 * English and German are built in; any other language gets English. Only what
 * people see is translated: the instructions the extension sends to the agent
 * stay English.
 */

export type Language = 'en' | 'de';

const en = {
  selectAgent: 'Select agent',
  defaultAgent: 'Default agent',
  setAsDefault: 'Set as default',
  dismissSelection: 'Dismiss selection',
  grantAccess: 'Grant access to read this page',
  contextUnavailable: 'Page context unavailable on this page',
  contextDisable: 'Click to disable page context',
  contextEnable: 'Click to enable page context',
  viewportOnly: 'Viewport only',
  fullPage: 'Full page',
  notConnected: 'Not connected to Synkora',
  streamError: 'Stream error',
  errorPrefix: 'Error: {message}',
  agentsFailed: 'Failed to load agents',
  suggestSummarize: 'Summarize this page',
  suggestAbout: 'What is this about?',
  suggestTakeaways: 'Key takeaways',
  suggestDraftReply: 'Draft a reply',
  suggestHelp: 'What can you help me with?',
  suggestCapabilities: 'What are your capabilities?',
  clear: 'Clear',
  messageAgent: 'Message {name}…',
  canSeeBefore: 'I can see ',
  canSeeAfter: '',
  noPageContext: 'No page context on this tab',
  fillFailed: 'Fill failed',
  fieldsFilledOne: '1 field filled',
  fieldsFilledMany: '{count} fields filled',
  fillOne: 'Fill 1 field',
  fillMany: 'Fill {count} fields',
  fillForm: 'Fill Form',
  retry: 'Retry',
  authCancelled: 'Authorization cancelled',
  invalidCallback: 'Invalid callback parameters',
  authFailed: 'Auth failed',
  authStartFailed: 'Failed to start auth',
  connect: 'Connect with Synkora',
  connectHint: 'Opens your Synkora dashboard to authorize access',
  waitingAuth: 'Waiting for authorization…',
  settings: 'Settings',
  disconnect: 'Disconnect',
  askAgent: 'Ask Synkora Agent',
  httpsRequired: 'Synkora URL must use HTTPS outside local development',
  tokenExchangeFailed: 'Token exchange failed',
  insecureUrl: 'Insecure URL rejected: {url}',
  fetchAgentsFailed: 'Failed to fetch agents: {status}',
  chatStreamFailed: 'Chat stream failed: {status}',
  noResponseBody: 'No response body from chat stream',
  noActiveTab: 'No active tab found',
  noElementAt: 'No element at index {index}',
  fieldError: 'Field {index}: {message}',
  scriptNoResult: 'Script returned no result',
};

export type MessageKey = keyof typeof en;

const de: Record<MessageKey, string> = {
  selectAgent: 'Agent auswählen',
  defaultAgent: 'Standard-Agent',
  setAsDefault: 'Als Standard festlegen',
  dismissSelection: 'Auswahl ausblenden',
  grantAccess: 'Zugriff zum Lesen dieser Seite erlauben',
  contextUnavailable: 'Seitenkontext ist auf dieser Seite nicht verfügbar',
  contextDisable: 'Klicken, um den Seitenkontext auszuschalten',
  contextEnable: 'Klicken, um den Seitenkontext einzuschalten',
  viewportOnly: 'Nur sichtbarer Bereich',
  fullPage: 'Ganze Seite',
  notConnected: 'Nicht mit Synkora verbunden',
  streamError: 'Fehler beim Abruf der Antwort',
  errorPrefix: 'Fehler: {message}',
  agentsFailed: 'Agenten konnten nicht geladen werden',
  suggestSummarize: 'Diese Seite zusammenfassen',
  suggestAbout: 'Worum geht es hier?',
  suggestTakeaways: 'Wichtigste Erkenntnisse',
  suggestDraftReply: 'Eine Antwort entwerfen',
  suggestHelp: 'Wobei kannst du mir helfen?',
  suggestCapabilities: 'Was kannst du alles?',
  clear: 'Leeren',
  messageAgent: 'Nachricht an {name} …',
  canSeeBefore: 'Ich kann ',
  canSeeAfter: ' sehen',
  noPageContext: 'Kein Seitenkontext in diesem Tab',
  fillFailed: 'Ausfüllen fehlgeschlagen',
  fieldsFilledOne: '1 Feld ausgefüllt',
  fieldsFilledMany: '{count} Felder ausgefüllt',
  fillOne: '1 Feld ausfüllen',
  fillMany: '{count} Felder ausfüllen',
  fillForm: 'Formular ausfüllen',
  retry: 'Erneut versuchen',
  authCancelled: 'Autorisierung abgebrochen',
  invalidCallback: 'Ungültige Rückgabeparameter',
  authFailed: 'Anmeldung fehlgeschlagen',
  authStartFailed: 'Anmeldung konnte nicht gestartet werden',
  connect: 'Mit Synkora verbinden',
  connectHint: 'Öffnet Ihr Synkora-Dashboard, um den Zugriff zu autorisieren',
  waitingAuth: 'Warten auf Autorisierung …',
  settings: 'Einstellungen',
  disconnect: 'Trennen',
  askAgent: 'Synkora-Agent fragen',
  httpsRequired: 'Die Synkora-URL muss außerhalb der lokalen Entwicklung HTTPS verwenden',
  tokenExchangeFailed: 'Token-Austausch fehlgeschlagen',
  insecureUrl: 'Unsichere URL abgelehnt: {url}',
  fetchAgentsFailed: 'Agenten konnten nicht abgerufen werden: {status}',
  chatStreamFailed: 'Chat-Stream fehlgeschlagen: {status}',
  noResponseBody: 'Keine Antwort vom Chat-Stream erhalten',
  noActiveTab: 'Kein aktiver Tab gefunden',
  noElementAt: 'Kein Element bei Index {index}',
  fieldError: 'Feld {index}: {message}',
  scriptNoResult: 'Das Skript hat kein Ergebnis geliefert',
};

export const messages: Record<Language, Record<MessageKey, string>> = { en, de };

/** "de-AT" -> "de"; null when the extension has no translation for it. */
export function languageFrom(tag: string | null | undefined): Language | null {
  const code = (tag ?? '').toLowerCase().split(/[-_]/)[0];
  return code === 'de' || code === 'en' ? code : null;
}

/** The browser's language tag, e.g. "de-AT"; sent to the API with chat requests. */
export function browserLanguageTag(): string {
  try {
    const chromeLanguage =
      typeof chrome !== 'undefined' ? chrome.i18n?.getUILanguage?.() : undefined;
    return chromeLanguage || (typeof navigator !== 'undefined' ? navigator.language : '') || 'en';
  } catch {
    return 'en';
  }
}

export function currentLanguage(): Language {
  return languageFrom(browserLanguageTag()) ?? 'en';
}

/** The text for [key] in the browser's language, with {name} values filled in. */
export function t(
  key: MessageKey,
  values: Record<string, string | number> = {},
  language: Language = currentLanguage(),
): string {
  const template = messages[language][key] ?? en[key];
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}
