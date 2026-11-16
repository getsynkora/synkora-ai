// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Runs the real embeddable widget (public/widget.js) in jsdom with fetch mocked,
 * and checks that it speaks the language it is given.
 */

const SOURCE = readFileSync(path.join(__dirname, "../../public/widget.js"), "utf8");

type FetchCall = { url: string; body: Record<string, unknown> | null };

let calls: FetchCall[];
let config: Record<string, unknown>;

const win = window as any;

function loadWidget() {
  delete win.SynkoraWidget;
  (0, eval)(SOURCE);
}

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: { body?: string }) => {
      calls.push({ url: String(url), body: init?.body ? JSON.parse(init.body) : null });
      if (String(url).includes("/widgets/config")) {
        return { ok: true, json: async () => config };
      }
      return { ok: false, json: async () => ({}) };
    }),
  );
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function init(options: Record<string, unknown> = {}) {
  const widget = win.SynkoraWidget.init({
    widgetId: "w1",
    apiKey: "wk_test",
    apiUrl: "https://api.test/api/v1",
    ...options,
  });
  const shadow = (document.getElementById("snkr-w1") as HTMLElement).shadowRoot as ShadowRoot;
  return { widget, shadow };
}

const text = (shadow: ShadowRoot, id: string) => shadow.getElementById(id)?.textContent?.trim();
const label = (shadow: ShadowRoot, id: string) => shadow.getElementById(id)?.getAttribute("aria-label");

beforeEach(() => {
  calls = [];
  config = { agent_name: "Muse", theme: {}, suggestion_prompts: [] };
  document.body.innerHTML = "";
  document.documentElement.lang = "";
  localStorage.clear();
  stubFetch();
  loadWidget();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("embedded widget language", () => {
  it("speaks English by default", async () => {
    const { shadow } = init();
    await settle();

    expect(label(shadow, "snkr-toggle")).toBe("Open chat");
    expect(text(shadow, "snkr-start-btn")).toBe("Send us a message");
    expect(text(shadow, "snkr-newchat-btn")).toBe("New chat");
    expect(label(shadow, "snkr-send")).toBe("Send");
  });

  it("speaks German when locale is de", async () => {
    const { shadow } = init({ locale: "de" });
    await settle();

    expect(label(shadow, "snkr-toggle")).toBe("Chat öffnen");
    expect(text(shadow, "snkr-start-btn")).toBe("Schreiben Sie uns");
    expect(text(shadow, "snkr-newchat-btn")).toBe("Neuer Chat");
    expect(text(shadow, "snkr-endchat-btn")).toBe("Chat beenden");
    expect(label(shadow, "snkr-send")).toBe("Senden");
    expect(label(shadow, "snkr-close")).toBe("Schließen");
    expect(text(shadow, "snkr-hdr-status")).toBe("Online");
  });

  it("falls back to <html lang> when no locale is given", async () => {
    document.documentElement.lang = "de-AT";
    const { shadow } = init();
    await settle();

    expect(text(shadow, "snkr-newchat-btn")).toBe("Neuer Chat");
    expect(calls.find((c) => c.url.includes("/widgets/config"))?.url).toContain("lang=de-AT");
  });

  it("ignores a locale that is not a language code", async () => {
    const { shadow } = init({ locale: "de; drop table" });
    await settle();

    expect(text(shadow, "snkr-newchat-btn")).toBe("New chat");
    expect(calls.find((c) => c.url.includes("/widgets/config"))?.url).not.toContain("drop");
  });

  it("uses English for a language it does not have", async () => {
    const { shadow } = init({ locale: "fr" });
    await settle();

    expect(text(shadow, "snkr-newchat-btn")).toBe("New chat");
  });

  it("lets the host add a language and reword text; the rest stays English", async () => {
    const { shadow } = init({
      locale: "fr",
      strings: { fr: { send: "Envoyer", new_chat: "Nouvelle discussion" } },
    });
    await settle();

    expect(label(shadow, "snkr-send")).toBe("Envoyer");
    expect(text(shadow, "snkr-newchat-btn")).toBe("Nouvelle discussion");
    expect(text(shadow, "snkr-endchat-btn")).toBe("End chat");
  });

  it("lets the host reword a built-in language", async () => {
    const { shadow } = init({ locale: "de", strings: { de: { send: "Abschicken" } } });
    await settle();

    expect(label(shadow, "snkr-send")).toBe("Abschicken");
    expect(text(shadow, "snkr-newchat-btn")).toBe("Neuer Chat");
  });
});

describe("embedded widget and the API", () => {
  it("asks the server for text in its language", async () => {
    init({ locale: "de" });
    await settle();

    const call = calls.find((c) => c.url.includes("/widgets/config"));
    expect(call?.url).toBe("https://api.test/api/v1/widgets/config?lang=de");
  });

  it("shows the server's translated welcome message and placeholder", async () => {
    config = {
      agent_name: "Muse",
      theme: { welcome_message: "Willkommen!\nWomit können wir helfen?", placeholder: "Frage stellen" },
      suggestion_prompts: [],
    };
    const { shadow } = init({ locale: "de" });
    await settle();

    expect(text(shadow, "snkr-home-greeting")).toContain("Willkommen!");
    expect((shadow.getElementById("snkr-input") as HTMLTextAreaElement).placeholder).toBe("Frage stellen");
  });

  it("falls back to its own German text when the server sends none", async () => {
    const { shadow } = init({ locale: "de" });
    await settle();

    expect(text(shadow, "snkr-home-greeting")).toContain("Hallo");
    expect(text(shadow, "snkr-home-greeting")).toContain("Wie können wir helfen?");
    expect((shadow.getElementById("snkr-input") as HTMLTextAreaElement).placeholder).toBe("Nachricht …");
  });

  it("sends the language with each message", async () => {
    const { widget } = init({ locale: "de" });
    await settle();

    widget._input.value = "Hallo";
    widget._send();
    await settle();

    const chat = calls.find((c) => c.url.endsWith("/widgets/chat"));
    expect(chat?.body?.language).toBe("de");
    expect(chat?.body?.message).toBe("Hallo");
  });

  it("localizes the 'Powered by' link", async () => {
    config = { agent_name: "Muse", theme: { branding_url: "https://example.com" }, suggestion_prompts: [] };
    const { shadow } = init({ locale: "de" });
    await settle();

    const branding = shadow.getElementById("snkr-branding");
    expect(branding?.textContent).toBe("Bereitgestellt von KI");
    expect(branding?.querySelector("a")?.getAttribute("href")).toBe("https://example.com");
  });

  it("keeps an admin-set branding text as written", async () => {
    config = { agent_name: "Muse", theme: { branding_text: "Powered by Acme" }, suggestion_prompts: [] };
    const { shadow } = init({ locale: "de" });
    await settle();

    expect(text(shadow, "snkr-branding")).toBe("Powered by Acme");
  });

  it("shows German error text when sending fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("/widgets/config")) return { ok: true, json: async () => config };
        throw new Error("offline");
      }),
    );
    const { widget, shadow } = init({ locale: "de" });
    await settle();

    widget._input.value = "Hallo";
    widget._send();
    await settle();

    expect(shadow.getElementById("snkr-messages")?.textContent).toContain("Entschuldigung, etwas ist schiefgelaufen");
  });
});
