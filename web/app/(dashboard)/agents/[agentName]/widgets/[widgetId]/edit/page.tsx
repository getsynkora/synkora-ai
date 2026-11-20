"use client";

import { useState, useEffect, useCallback } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  GitBranch,
  RefreshCw,
  Copy,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  ChevronDown,
  CheckCircle,
  AlertTriangle,
  Palette,
  Languages,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import {
  TRANSLATION_LANGUAGES,
  normalizeLanguageCode,
  pruneTranslations,
  readTranslations,
  type TranslatedPrompt,
  type WidgetTranslation,
  type WidgetTranslations,
} from "@/lib/widgetTranslations";
import toast from "react-hot-toast";
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface Widget {
  widget_id: string;
  widget_name: string;
  agent_id: string;
  agent_name: string;
  allowed_domains: string[] | null;
  rate_limit: number;
  is_active: boolean;
  identity_verification_required: boolean;
  enable_agent_routing: boolean;
  mobile_allowed: boolean;
  theme_config?: Record<string, any>;
}

interface AgentRoute {
  external_org_id: string;
  agent_id: string;
  agent_name?: string;
}

interface Agent {
  id: string;
  agent_name: string;
}

export default function WidgetEditPage() {
  const params = useParams();
  const agentName = params.agentName as string;
  const widgetId = params.widgetId as string;

  const [widget, setWidget] = useState<Widget | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [routes, setRoutes] = useState<AgentRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Basic settings
  const [widgetName, setWidgetName] = useState("");
  const [allowedDomains, setAllowedDomains] = useState("");
  const [rateLimit, setRateLimit] = useState(100);
  const [isActive, setIsActive] = useState(true);

  // Chat appearance
  const [primaryColor, setPrimaryColor] = useState("#ff444f");
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [chatPlaceholder, setChatPlaceholder] = useState("");

  // Per-language widget text
  const [translations, setTranslations] = useState<WidgetTranslations>({});
  const [newLanguage, setNewLanguage] = useState(TRANSLATION_LANGUAGES[0].code);
  const [customLanguage, setCustomLanguage] = useState("");

  // Identity verification
  const [identityVerificationRequired, setIdentityVerificationRequired] = useState(false);
  const [identitySecret, setIdentitySecret] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [regeneratingSecret, setRegeneratingSecret] = useState(false);

  // Flutter SDK snippet tab
  const [flutterTab, setFlutterTab] = useState<"pubspec" | "basic" | "push">("pubspec");

  // Mobile / push
  const [mobileAllowed, setMobileAllowed] = useState(false);
  const [fcmServerKey, setFcmServerKey] = useState("");
  const [showFcmKey, setShowFcmKey] = useState(false);

  // Pre-chat form
  const [preChatEnabled, setPreChatEnabled] = useState(false);
  const [preChatShowName, setPreChatShowName] = useState(true);
  const [preChatShowEmail, setPreChatShowEmail] = useState(true);
  const [preChatShowPhone, setPreChatShowPhone] = useState(false);
  const [preChatSkippable, setPreChatSkippable] = useState(true);

  // Agent routing
  const [enableAgentRouting, setEnableAgentRouting] = useState(false);
  const [newOrgId, setNewOrgId] = useState("");
  const [newAgentId, setNewAgentId] = useState("");
  const [addingRoute, setAddingRoute] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [widgetData, routesData, agentsData] = await Promise.all([
        apiClient.getWidget(widgetId),
        apiClient.getWidgetRoutes(widgetId),
        apiClient.getAgents(),
      ]);

      setWidget(widgetData);
      setWidgetName(widgetData.widget_name || "");
      setAllowedDomains((widgetData.allowed_domains || []).join(", "));
      setRateLimit(widgetData.rate_limit || 100);
      setIsActive(widgetData.is_active ?? true);
      setIdentityVerificationRequired(widgetData.identity_verification_required ?? false);
      const theme = widgetData.theme_config || {};
      setPrimaryColor(theme.chat_primary_color || "#ff444f");
      setWelcomeMessage(theme.chat_welcome_message || "");
      setChatPlaceholder(theme.chat_placeholder || "");
      setTranslations(readTranslations(theme.translations));
      setEnableAgentRouting(widgetData.enable_agent_routing ?? false);
      setMobileAllowed(widgetData.mobile_allowed ?? false);
      setFcmServerKey("");
      const preChatCfg = (widgetData.theme_config as any)?.pre_chat_form || {};
      setPreChatEnabled(preChatCfg.enabled ?? false);
      setPreChatShowName(preChatCfg.show_name ?? true);
      setPreChatShowEmail(preChatCfg.show_email ?? true);
      setPreChatShowPhone(preChatCfg.show_phone ?? false);
      setPreChatSkippable(preChatCfg.skippable ?? true);

      const agentList: Agent[] = Array.isArray(agentsData) ? agentsData : agentsData?.agents_list || [];
      setAgents(agentList);

      const enriched = routesData.map((r: AgentRoute) => ({
        ...r,
        agent_name: agentList.find((a) => a.id === r.agent_id)?.agent_name || r.agent_id,
      }));
      setRoutes(enriched);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to load widget"))
    } finally {
      setLoading(false);
    }
  }, [widgetId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const domains = allowedDomains
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);
      await apiClient.updateWidget(widgetId, {
        widget_name: widgetName,
        allowed_domains: domains.length > 0 ? domains : null,
        rate_limit: rateLimit,
        is_active: isActive,
        identity_verification_required: identityVerificationRequired,
        enable_agent_routing: enableAgentRouting,
        mobile_allowed: mobileAllowed,
        ...(fcmServerKey.trim() ? { fcm_server_key: fcmServerKey.trim() } : {}),
        theme_config: {
          // Keep settings this page does not edit (title, branding, translations...).
          ...(widget?.theme_config ?? {}),
          chat_primary_color: primaryColor,
          chat_welcome_message: welcomeMessage,
          chat_placeholder: chatPlaceholder,
          pre_chat_form: {
            enabled: preChatEnabled,
            show_name: preChatShowName,
            show_email: preChatShowEmail,
            show_phone: preChatShowPhone,
            skippable: preChatSkippable,
          },
          translations: pruneTranslations(translations),
        },
      });
      toast.success("Widget settings saved");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to save settings"))
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateSecret = async () => {
    if (
      !confirm(
        "Regenerate the identity secret?\n\nAny existing server-side integrations using the old secret will stop working immediately."
      )
    )
      return;
    setRegeneratingSecret(true);
    try {
      const result = await apiClient.regenerateIdentitySecret(widgetId);
      setIdentitySecret(result.data?.identity_secret || null);
      setShowSecret(true);
      toast.success("New secret generated, copy it now, it won't be shown again");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to regenerate secret"))
    } finally {
      setRegeneratingSecret(false);
    }
  };

  const handleAddRoute = async () => {
    if (!newOrgId.trim() || !newAgentId) {
      toast.error("Org ID and agent are required");
      return;
    }
    setAddingRoute(true);
    try {
      const updated = [
        ...routes.map((r) => ({ external_org_id: r.external_org_id, agent_id: r.agent_id })),
        { external_org_id: newOrgId.trim(), agent_id: newAgentId },
      ];
      await apiClient.setWidgetRoutes(widgetId, updated);
      const resolvedAgentName = agents.find((a) => a.id === newAgentId)?.agent_name || newAgentId;
      setRoutes([...routes, { external_org_id: newOrgId.trim(), agent_id: newAgentId, agent_name: resolvedAgentName }]);
      setNewOrgId("");
      setNewAgentId("");
      toast.success("Route added");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to add route"))
    } finally {
      setAddingRoute(false);
    }
  };

  const handleDeleteRoute = async (orgId: string) => {
    try {
      await apiClient.deleteWidgetRoute(widgetId, orgId);
      setRoutes(routes.filter((r) => r.external_org_id !== orgId));
      toast.success("Route removed");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to remove route"))
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => toast.success("Copied to clipboard"));
  };

  const addTranslationLanguage = () => {
    const code = normalizeLanguageCode(customLanguage || newLanguage);
    if (!code) {
      toast.error("Enter a language code such as de, en or pt-BR");
      return;
    }
    if (translations[code]) {
      toast.error(`${code} is already added`);
      return;
    }
    setTranslations((prev) => ({ ...prev, [code]: {} }));
    setCustomLanguage("");
  };

  const removeTranslationLanguage = (code: string) =>
    setTranslations((prev) => {
      const next = { ...prev };
      delete next[code];
      return next;
    });

  const updateTranslation = (code: string, patch: Partial<WidgetTranslation>) =>
    setTranslations((prev) => ({ ...prev, [code]: { ...prev[code], ...patch } }));

  const updateTranslatedPrompt = (code: string, index: number, patch: Partial<TranslatedPrompt>) =>
    setTranslations((prev) => {
      const prompts = [...(prev[code]?.suggestion_prompts ?? [])];
      prompts[index] = { ...prompts[index], ...patch };
      return { ...prev, [code]: { ...prev[code], suggestion_prompts: prompts } };
    });

  const addTranslatedPrompt = (code: string) =>
    setTranslations((prev) => ({
      ...prev,
      [code]: {
        ...prev[code],
        suggestion_prompts: [
          ...(prev[code]?.suggestion_prompts ?? []),
          { title: "", description: "", icon: "", prompt: "" },
        ],
      },
    }));

  const removeTranslatedPrompt = (code: string, index: number) =>
    setTranslations((prev) => ({
      ...prev,
      [code]: {
        ...prev[code],
        suggestion_prompts: (prev[code]?.suggestion_prompts ?? []).filter((_, i) => i !== index),
      },
    }));

  const languageLabel = (code: string) => {
    const known = TRANSLATION_LANGUAGES.find((l) => l.code === code.split("-")[0]);
    return known ? `${known.label} (${code})` : code;
  };

  const sectionClass =
    "rounded-[1.9rem] border border-line bg-white p-6 shadow-soft sm:p-7";
  const inputClass =
    "w-full rounded-[1.1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint";
  const compactInputClass =
    "rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint";
  const codeInlineClass =
    "rounded-md border border-black/5 bg-white/80 px-1.5 py-0.5 font-mono text-[11px] text-ink-soft";

  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 motion-safe:animate-spin rounded-full border-b-2 border-ink" />
      </div>
    );
  }

  if (!widget) {
    return (
      <AgentPageShell
        agentName={agentName}
        title="Edit Widget"
        description="Update settings for this widget."
        icon={Palette}
        backHref={`/agents/${agentName}/widgets`}
        backLabel="Back to Widgets"
        badge="Embeddable UI"
        maxWidthClassName="max-w-[90rem]"
      >
        <AgentPagePanel className="border-blush-wash bg-white p-4">
          <p className="text-sm text-wine">Widget not found.</p>
        </AgentPagePanel>
      </AgentPageShell>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Edit Widget"
      description={<>Update settings for <span className="font-semibold text-ink">{widget.widget_name}</span>.</>}
      icon={Palette}
      backHref={`/agents/${agentName}/widgets`}
      backLabel="Back to Widgets"
      badge="Embeddable UI"
      maxWidthClassName="max-w-[90rem]"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Agents', href: '/agents' },
        { label: decodeURIComponent(agentName), href: `/agents/${encodeURIComponent(agentName)}/view` },
        { label: 'Widgets', href: `/agents/${encodeURIComponent(agentName)}/widgets` },
        { label: widget.widget_name },
      ]}
      actions={
        <div className="flex flex-wrap gap-3">
          <Link
            href={`/agents/${agentName}/widgets`}
            className="inline-flex items-center justify-center rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-ink-soft transition-colors hover:bg-white hover:text-ink"
          >
            Cancel
          </Link>
          <button
            type="submit"
            form="widget-edit-form"
            disabled={saving}
            className="inline-flex items-center justify-center rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      }
    >

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-[1rem] border border-blush-wash bg-white p-3">
            <p className="text-sm text-wine">{error}</p>
          </div>
        )}

        <form
          id="widget-edit-form"
          onSubmit={handleSave}
          className="space-y-6"
        >

          {/* ── Flutter SDK highlight banner ───────────────────────────────────── */}
          <div className="relative overflow-hidden rounded-[1.9rem] border border-sky-wash bg-sky-wash p-6 shadow-soft">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[1rem] border border-white/80 bg-white/90 shadow-sm">
                <svg aria-hidden="true" viewBox="0 0 24 24" className="w-6 h-6" fill="none">
                  <path d="M14.314 0L2.3 12 6 15.7 21.684 0h-7.37zm.014 11.072L7.857 17.53l6.47 6.47H21.7l-6.46-6.468 6.46-6.46h-7.37z" fill="#54C5F8"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-azure">Flutter SDK available</h3>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-sky-wash text-azure">pub.dev</span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-leaf-wash text-forest">Open Source</span>
                </div>
                <p className="text-xs text-azure mb-3">
                  Embed this AI agent natively into any Flutter app, Android, iOS, and beyond. Drop-in chat UI, SSE streaming, local message cache, and optional FCM push notifications.
                </p>
                <div className="flex items-center gap-3 flex-wrap">
                  <code className="rounded-md border border-sky-wash bg-white/90 px-2 py-1 font-mono text-xs text-azure">
                    flutter pub add synkora_chat
                  </code>
                  <span className="text-xs text-azure">·</span>
                  <code className="rounded-md border border-sky-wash bg-white/90 px-2 py-1 font-mono text-xs text-azure">
                    flutter pub add synkora_push
                  </code>
                  <span className="text-xs text-steel">optional, for push notifications</span>
                </div>
              </div>
              {/* Decorative blobs */}
              <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-sky-wash opacity-40 pointer-events-none" />
              <div className="absolute right-8 -bottom-6 w-16 h-16 rounded-full bg-sand-deep opacity-40 pointer-events-none" />
            </div>
          </div>

          {/* ── General ───────────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <h2 className="text-lg font-semibold text-ink mb-4">General</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">
                  Widget name <span className="text-leaf">*</span>
                </label>
                <input
                  type="text"
                  value={widgetName}
                  onChange={(e) => setWidgetName(e.target.value)}
                  required
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">
                  Allowed domains
                  <span className="ml-1 font-normal text-ink-mute">(comma-separated, leave blank to allow all)</span>
                </label>
                <input
                  type="text"
                  value={allowedDomains}
                  onChange={(e) => setAllowedDomains(e.target.value)}
                  placeholder="app.example.com, *.example.com"
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">
                  Rate limit <span className="font-normal text-ink-mute">(requests / hour)</span>
                </label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={rateLimit}
                  onChange={(e) => setRateLimit(Number(e.target.value))}
                  className={`w-40 ${compactInputClass}`}
                />
              </div>

              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="h-4 w-4 rounded border-taupe text-leaf focus:ring-mint"
                  />
                  <span className="text-sm text-ink-soft">Widget is active</span>
                </label>
                <p className="mt-1 text-xs text-ink-mute ml-6">Inactive widgets stop accepting all traffic</p>
              </div>
            </div>
          </div>

          {/* ── Chat Appearance ───────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <Palette className="h-5 w-5 text-leaf" />
              <h2 className="text-lg font-semibold text-ink">Chat Appearance</h2>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Override the default agent appearance for this widget. Leave blank to use the agent&apos;s defaults.
            </p>

            <div className="space-y-4">
              {/* Primary color */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">Brand color</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="h-11 w-16 cursor-pointer rounded-[1rem] border border-black/10 bg-white p-1"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    placeholder="#ff444f"
                    className={`w-32 font-mono ${compactInputClass}`}
                  />
                  <span className="text-xs text-ink-mute">Used for the toggle button, hero, and accents</span>
                </div>
              </div>

              {/* Welcome message */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">
                  Welcome message
                  <span className="ml-1 font-normal text-ink-mute">(shown in the home screen hero)</span>
                </label>
                <textarea
                  value={welcomeMessage}
                  onChange={(e) => setWelcomeMessage(e.target.value)}
                  rows={2}
                  placeholder={"Hi there 👋\nHow can we help?"}
                  className={`${inputClass} resize-none`}
                />
                <p className="mt-1 text-xs text-ash">Use a newline to split into title + subtitle</p>
              </div>

              {/* Placeholder */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-1.5">Input placeholder</label>
                <input
                  type="text"
                  value={chatPlaceholder}
                  onChange={(e) => setChatPlaceholder(e.target.value)}
                  placeholder="Message…"
                  className={inputClass}
                />
              </div>

              {/* Live preview swatch */}
              <div className="rounded-xl overflow-hidden border border-line mt-2">
                <div
                  className="px-5 py-4"
                  style={{ background: `linear-gradient(160deg, ${primaryColor} 0%, ${primaryColor}cc 100%)` }}
                >
                  <div className="text-white font-extrabold text-lg leading-tight">
                    {welcomeMessage ? welcomeMessage.split("\n")[0] : "Hi there 👋"}
                  </div>
                  {(welcomeMessage.includes("\n") ? welcomeMessage.split("\n")[1] : !welcomeMessage ? "How can we help?" : "") && (
                    <div className="text-white/85 font-semibold text-base mt-0.5">
                      {welcomeMessage.includes("\n") ? welcomeMessage.split("\n")[1] : "How can we help?"}
                    </div>
                  )}
                </div>
                <div className="bg-cream px-4 py-3 flex items-center gap-2">
                  <input
                    readOnly
                    value=""
                    placeholder={chatPlaceholder || "Message…"}
                    className="flex-1 text-sm text-ash bg-transparent outline-none"
                  />
                  <div className="w-7 h-7 rounded-full flex items-center justify-center" style={{ background: primaryColor }}>
                    <svg aria-hidden="true" width="11" height="11" viewBox="0 0 24 24" fill="none"><line x1="22" y1="2" x2="11" y2="13" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/><polygon points="22 2 15 22 11 13 2 9 22 2" fill="#fff"/></svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Translations ──────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <Languages className="h-5 w-5 text-leaf" />
              <h2 className="text-lg font-semibold text-ink">Translations</h2>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Text for people who open the chat in another language. Anything left blank uses the default text
              above. The agent itself answers in the language the chat is set to.
            </p>

            <div className="mb-4 flex flex-wrap items-end gap-2">
              <div>
                <label className="block text-xs font-semibold text-ink-soft mb-1">Language</label>
                <select
                  value={newLanguage}
                  onChange={(e) => setNewLanguage(e.target.value)}
                  disabled={customLanguage.trim() !== ""}
                  className={compactInputClass}
                >
                  {TRANSLATION_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label} ({l.code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-soft mb-1">or another code</label>
                <input
                  type="text"
                  value={customLanguage}
                  onChange={(e) => setCustomLanguage(e.target.value)}
                  placeholder="e.g. pt-BR"
                  className={`w-32 ${compactInputClass}`}
                />
              </div>
              <button
                type="button"
                onClick={addTranslationLanguage}
                className="inline-flex items-center gap-1.5 rounded-[1rem] border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-ink-soft hover:bg-cream"
              >
                <Plus className="h-4 w-4" /> Add language
              </button>
            </div>

            {Object.keys(translations).length === 0 ? (
              <p className="text-sm text-ash">No translations yet.</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(translations).map(([code, entry]) => (
                  <div key={code} className="rounded-[1.2rem] border border-black/10 bg-white/70 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-ink">{languageLabel(code)}</h3>
                      <button
                        type="button"
                        onClick={() => removeTranslationLanguage(code)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-danger hover:text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Remove
                      </button>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-ink-soft mb-1">Title</label>
                      <input
                        type="text"
                        value={entry.title ?? ""}
                        onChange={(e) => updateTranslation(code, { title: e.target.value })}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-ink-soft mb-1">
                        Welcome message
                        <span className="ml-1 font-normal text-ink-mute">(newline splits title and subtitle)</span>
                      </label>
                      <textarea
                        value={entry.welcome_message ?? ""}
                        onChange={(e) => updateTranslation(code, { welcome_message: e.target.value })}
                        rows={2}
                        className={`${inputClass} resize-none`}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-ink-soft mb-1">Input placeholder</label>
                      <input
                        type="text"
                        value={entry.placeholder ?? ""}
                        onChange={(e) => updateTranslation(code, { placeholder: e.target.value })}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-ink-soft mb-1">Agent description</label>
                      <textarea
                        value={entry.agent_description ?? ""}
                        onChange={(e) => updateTranslation(code, { agent_description: e.target.value })}
                        rows={2}
                        className={`${inputClass} resize-none`}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-ink-soft mb-1">Privacy policy text</label>
                      <input
                        type="text"
                        value={entry.privacy_policy_text ?? ""}
                        onChange={(e) => updateTranslation(code, { privacy_policy_text: e.target.value })}
                        className={inputClass}
                      />
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-xs font-semibold text-ink-soft">
                          Suggested prompts
                          <span className="ml-1 font-normal text-ink-mute">
                            (replace the agent&apos;s prompts in this language)
                          </span>
                        </label>
                        <button
                          type="button"
                          onClick={() => addTranslatedPrompt(code)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-leaf hover:underline"
                        >
                          <Plus className="h-3.5 w-3.5" /> Add prompt
                        </button>
                      </div>
                      <div className="space-y-2">
                        {(entry.suggestion_prompts ?? []).map((p, i) => (
                          <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_1.4fr_auto]">
                            <input
                              type="text"
                              value={p.title}
                              onChange={(e) => updateTranslatedPrompt(code, i, { title: e.target.value })}
                              placeholder="Title"
                              className={compactInputClass}
                            />
                            <input
                              type="text"
                              value={p.description}
                              onChange={(e) => updateTranslatedPrompt(code, i, { description: e.target.value })}
                              placeholder="Description"
                              className={compactInputClass}
                            />
                            <input
                              type="text"
                              value={p.prompt}
                              onChange={(e) => updateTranslatedPrompt(code, i, { prompt: e.target.value })}
                              placeholder="Message sent when tapped"
                              className={compactInputClass}
                            />
                            <button
                              type="button"
                              onClick={() => removeTranslatedPrompt(code, i)}
                              aria-label="Remove prompt"
                              className="rounded-[1rem] border border-black/10 bg-white px-3 text-ink-mute hover:text-danger"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Pre-chat Form ─────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <svg aria-hidden="true" className="h-5 w-5 text-leaf" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <h2 className="text-lg font-semibold text-ink">Pre-chat Form</h2>
              </div>
              <button
                type="button"
                onClick={() => setPreChatEnabled(!preChatEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${preChatEnabled ? 'bg-leaf' : 'bg-line'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform motion-reduce:transition-none ${preChatEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Show a short form before the first message to collect user info. Applies to anonymous users only, identified users skip it automatically.
            </p>
            {preChatEnabled && (
              <div className="space-y-3">
                {[
                  { label: 'Show Name field', value: preChatShowName, set: setPreChatShowName },
                  { label: 'Show Email field', value: preChatShowEmail, set: setPreChatShowEmail },
                  { label: 'Show Phone field', value: preChatShowPhone, set: setPreChatShowPhone },
                  { label: 'Allow users to skip the form', value: preChatSkippable, set: setPreChatSkippable },
                ].map(({ label, value, set }) => (
                  <label key={label} className="flex items-center justify-between cursor-pointer">
                    <span className="text-sm text-ink-soft">{label}</span>
                    <button
                      type="button"
                      onClick={() => set(!value)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${value ? 'bg-leaf' : 'bg-line'}`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform motion-reduce:transition-none ${value ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* ── Identity Verification ─────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <Shield className="h-5 w-5 text-leaf" />
              <h2 className="text-lg font-semibold text-ink">Identity Verification</h2>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Prevent end-users from impersonating each other using HMAC signatures generated on your server.
            </p>

            {/* Toggle */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={identityVerificationRequired}
                  onChange={(e) => setIdentityVerificationRequired(e.target.checked)}
                  className="h-4 w-4 rounded border-taupe text-leaf focus:ring-mint"
                />
                <span className="text-sm text-ink-soft">Require identity verification on every request</span>
              </label>
              <p className="mt-1 text-xs text-ink-mute ml-6">
                When enabled, requests without a valid{" "}
                <code className={codeInlineClass}>userHash</code> are rejected with HTTP 403.
              </p>
            </div>

            {identityVerificationRequired && (
              <div className="mb-4 flex gap-2 rounded-[1rem] border border-tan bg-paper p-3 text-xs text-gold">
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>
                  Make sure your server is generating the hash before enabling this, otherwise all widget traffic will be blocked.
                </span>
              </div>
            )}

            {/* Secret */}
            <div className="border-t border-line pt-4 space-y-2">
              <h3 className="text-sm font-medium text-ink-soft">Identity secret</h3>
              <p className="text-xs text-ink-mute">
                Compute <code className={codeInlineClass}>HMAC-SHA256(secret, userId)</code> on your server and pass
                it as <code className={codeInlineClass}>userHash</code> in the widget init call.{" "}
                <span className="font-medium text-ink-soft">Never expose this secret in the browser.</span>
              </p>

              {identitySecret ? (
                <div className="flex items-center gap-2 rounded-[1rem] border border-leaf-wash bg-cream px-3 py-2">
                  <CheckCircle className="h-4 w-4 text-leaf flex-shrink-0" />
                  <code className="text-xs text-forest break-all flex-1">
                    {showSecret ? identitySecret : "•".repeat(44)}
                  </code>
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    className="text-leaf hover:text-forest transition-colors"
                  >
                    {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(identitySecret)}
                    className="text-leaf hover:text-forest transition-colors"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <p className="text-xs text-ink-mute italic">
                  The secret was shown when this widget was created. Use the button below to rotate it.
                </p>
              )}

              <button
                type="button"
                onClick={handleRegenerateSecret}
                disabled={regeneratingSecret}
                className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-leaf transition-colors disabled:opacity-50 font-medium"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${regeneratingSecret ? "motion-safe:animate-spin" : ""}`} />
                Regenerate secret
              </button>
            </div>

            {/* Code examples */}
            <details className="mt-4 group">
              <summary className="flex items-center gap-1.5 text-sm font-medium text-ink-soft cursor-pointer select-none list-none">
                <ChevronDown className="h-4 w-4 transition-transform motion-reduce:transition-none group-open:rotate-180" />
                Server-side code examples
              </summary>
              <div className="mt-3 space-y-2">
                {[
                  {
                    lang: "Node.js",
                    code: `const crypto = require("crypto");\nconst hash = crypto\n  .createHmac("sha256", process.env.WIDGET_IDENTITY_SECRET)\n  .update(user.id)\n  .digest("hex");`,
                  },
                  {
                    lang: "Python",
                    code: `import hmac, hashlib\nhash = hmac.new(\n    os.environ["WIDGET_IDENTITY_SECRET"].encode(),\n    user_id.encode(),\n    hashlib.sha256\n).hexdigest()`,
                  },
                  {
                    lang: "PHP",
                    code: `$hash = hash_hmac("sha256", $userId, $_ENV["WIDGET_IDENTITY_SECRET"]);`,
                  },
                  {
                    lang: "Ruby",
                    code: `require "openssl"\nhash = OpenSSL::HMAC.hexdigest("SHA256", ENV["WIDGET_IDENTITY_SECRET"], user_id)`,
                  },
                ].map(({ lang, code }) => (
                  <div key={lang} className="overflow-hidden rounded-[1rem] bg-ink text-xs shadow-soft">
                    <div className="flex items-center justify-between bg-ink px-3 py-1.5">
                      <span className="text-ash text-[11px]">{lang}</span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(code)}
                        className="text-ash hover:text-white transition-colors"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <pre className="overflow-x-auto p-3 leading-relaxed text-leaf-wash">{code}</pre>
                  </div>
                ))}

                <div className="rounded-[1rem] border border-line bg-cream p-3 text-xs text-ink-soft">
                  <p className="font-medium mb-1.5">Widget init with identity verification:</p>
                  <pre className="overflow-x-auto whitespace-pre rounded-[0.9rem] border border-black/5 bg-white/80 p-2 text-[11px]">{`SynkoraWidget.init({
  widgetId:  "your-widget-id",
  apiKey:    "swk_...",
  user:      { id: currentUser.id, name: currentUser.name, orgId: currentOrg.id },
  userHash:  "{{ hash computed on your server }}",
});`}</pre>
                </div>
              </div>
            </details>
          </div>

          {/* ── Mobile & Push Notifications ───────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <svg aria-hidden="true" className="h-5 w-5 text-leaf" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 8.25h3m-3 3h3m-3 3h3" />
              </svg>
              <h2 className="text-lg font-semibold text-ink">Mobile &amp; Push Notifications</h2>
            </div>
            <p className="text-sm text-ink-mute mb-5">
              Enable the Flutter SDK and optionally configure FCM to send push notifications when the agent replies.
            </p>

            {/* Mobile allowed toggle */}
            <div className="flex items-center justify-between py-3 border-b border-sand mb-4">
              <div>
                <p className="text-sm font-medium text-ink">Allow Mobile Apps (Flutter SDK)</p>
                <p className="text-xs text-ink-mute mt-0.5">
                  Skips the browser Origin check so requests from the Flutter SDK are accepted.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileAllowed(!mobileAllowed)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${mobileAllowed ? "bg-ink" : "bg-line"}`}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${mobileAllowed ? "translate-x-5" : "translate-x-0"}`} />
              </button>
            </div>

            {/* FCM Server Key */}
            <div>
              <label className="block text-sm font-medium text-ink-soft mb-1">FCM Server Key (optional)</label>
              <p className="text-xs text-ink-mute mb-2">
                Paste your Firebase service account JSON or FCM server key. Stored encrypted. Leave blank to keep the existing key.
              </p>
              <div className="relative">
                <input
                  type={showFcmKey ? "text" : "password"}
                  value={fcmServerKey}
                  onChange={(e) => setFcmServerKey(e.target.value)}
                  placeholder="Paste FCM server key or service account JSON…"
                  className={`pr-10 ${inputClass}`}
                />
                <button
                  type="button"
                  onClick={() => setShowFcmKey(!showFcmKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-ash hover:text-ink-soft"
                >
                  {showFcmKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* ── Agent Routing ─────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <GitBranch className="h-5 w-5 text-leaf" />
              <h2 className="text-lg font-semibold text-ink">Agent Routing</h2>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Route different customer orgs to different agents, each with their own knowledge base, prompts, and tools.
            </p>

            {/* Toggle */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={enableAgentRouting}
                  onChange={(e) => setEnableAgentRouting(e.target.checked)}
                  className="h-4 w-4 rounded border-taupe text-leaf focus:ring-mint"
                />
                <span className="text-sm text-ink-soft">Enable org-based agent routing</span>
              </label>
              <p className="mt-1 text-xs text-ink-mute ml-6">
                When enabled, requests with a <code className={codeInlineClass}>user.orgId</code> are routed using
                the table below. Unmatched orgs fall back to this widget&apos;s default agent.
              </p>
            </div>

            {enableAgentRouting && (
              <div className="border-t border-line pt-4 space-y-4">
                {/* Routes table */}
                {routes.length > 0 ? (
                  <div className="overflow-hidden rounded-[1rem] border border-line">
                    <table className="w-full text-sm">
                      <thead className="bg-paper">
                        <tr>
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-ink-mute">
                            Org ID
                          </th>
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-ink-mute">
                            Agent
                          </th>
                          <th className="px-4 py-2.5 w-10" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-sand">
                        {routes.map((route) => (
                          <tr key={route.external_org_id} className="hover:bg-cream">
                            <td className="px-4 py-3">
                              <code className={codeInlineClass}>{route.external_org_id}</code>
                            </td>
                            <td className="px-4 py-3 text-sm text-ink-soft">{route.agent_name || route.agent_id}</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => handleDeleteRoute(route.external_org_id)}
                                className="text-ash hover:text-leaf transition-colors"
                                title="Remove route"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-ink-mute italic">
                    No routes yet. All orgs will use this widget&apos;s default agent.
                  </p>
                )}

                {/* Add route */}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-ink-soft mb-1">Org ID</label>
                    <input
                      type="text"
                      value={newOrgId}
                      onChange={(e) => setNewOrgId(e.target.value)}
                      placeholder="e.g. acme, org_123"
                      className={inputClass}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleAddRoute();
                        }
                      }}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-ink-soft mb-1">Route to agent</label>
                    <select
                      value={newAgentId}
                      onChange={(e) => setNewAgentId(e.target.value)}
                      className={inputClass}
                    >
                      <option value="">Select agent…</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.agent_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddRoute}
                    disabled={addingRoute || !newOrgId.trim() || !newAgentId}
                    className="flex items-center gap-1.5 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" />
                    Add
                  </button>
                </div>

                <div className="rounded-[1rem] border border-leaf-wash bg-cream p-3 text-xs text-forest">
                  Pass <code className={codeInlineClass}>user.orgId</code> in{" "}
                  <code className={codeInlineClass}>SynkoraWidget.init()</code> to activate routing. Orgs not
                  listed above fall back to the widget&apos;s default agent.
                </div>
              </div>
            )}
          </div>

          {/* ── Flutter Integration ───────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none">
                <path d="M14.314 0L2.3 12 6 15.7 21.684 0h-7.37zm.014 11.072L7.857 17.53l6.47 6.47H21.7l-6.46-6.468 6.46-6.46h-7.37z" fill="#54C5F8"/>
              </svg>
              <h2 className="text-lg font-semibold text-ink">Flutter Integration</h2>
            </div>
            <p className="text-sm text-ink-mute mb-4">
              Copy the snippet below to integrate this widget into your Flutter app. Enable "Allow Mobile Apps" above first.
            </p>

            {/* Tabs */}
            <div className="mb-3 flex w-fit gap-1 rounded-[1rem] border border-black/10 bg-white/80 p-1.5 shadow-soft">
              {(["pubspec", "basic", "push"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setFlutterTab(tab)}
                  className={`rounded-[0.85rem] px-3 py-2 text-xs font-semibold transition-colors ${
                    flutterTab === tab
                      ? "bg-ink text-white shadow-soft"
                      : "text-ink-mute hover:bg-paper hover:text-ink"
                  }`}
                >
                  {tab === "pubspec" ? "pubspec.yaml" : tab === "basic" ? "Basic usage" : "With push"}
                </button>
              ))}
            </div>

            {/* Code blocks */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  const snippets = {
                    pubspec: `dependencies:\n  synkora_chat: ^1.0.0\n\n# Optional, for push notifications\n  synkora_push: ^1.0.0`,
                    basic: `import 'package:synkora_chat/synkora_chat.dart';\n\n// Drop-in, place anywhere in your widget tree\nSynkoraChatWidget(\n  widgetKey: '${widgetId}',\n  baseUrl: 'https://your-synkora-instance.com',\n  userId: currentUser.id,  // optional\n  onClose: () => Navigator.pop(context),\n)`,
                    push: `// main.dart\nvoid main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n  await Firebase.initializeApp();\n\n  await SynkoraPush.init(\n    widgetKey: '${widgetId}',\n    baseUrl: 'https://your-synkora-instance.com',\n    conversationIdProvider: () => chatController.conversationId,\n  );\n\n  // Optional: handle foreground messages\n  SynkoraPush.onMessage = (message) {\n    // show in-app banner or navigate to chat\n  };\n\n  runApp(MyApp());\n}`,
                  };
                  navigator.clipboard.writeText(snippets[flutterTab]);
                }}
                className="absolute top-3 right-3 z-10 rounded-[0.85rem] bg-white/10 p-2 text-taupe transition-colors hover:bg-white/20 hover:text-white"
                title="Copy to clipboard"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>

              {flutterTab === "pubspec" && (
                <pre className="overflow-x-auto rounded-[1rem] bg-ink p-4 text-xs leading-relaxed text-paper">
{`dependencies:
  synkora_chat: ^1.0.0

  # Optional, for FCM push notifications
  synkora_push: ^1.0.0`}
                </pre>
              )}

              {flutterTab === "basic" && (
                <pre className="overflow-x-auto rounded-[1rem] bg-ink p-4 text-xs leading-relaxed text-paper">
{`import 'package:synkora_chat/synkora_chat.dart';

// Drop-in — place anywhere in your widget tree
SynkoraChatWidget(
  widgetKey: '${widgetId}',
  baseUrl: 'https://your-synkora-instance.com',
  userId: currentUser.id,  // optional, for history continuity
  onClose: () => Navigator.pop(context),
)`}
                </pre>
              )}

              {flutterTab === "push" && (
                <pre className="overflow-x-auto rounded-[1rem] bg-ink p-4 text-xs leading-relaxed text-paper">
{`// main.dart, call once after Firebase.initializeApp()
import 'package:synkora_push/synkora_push.dart';

await SynkoraPush.init(
  widgetKey: '${widgetId}',
  baseUrl: 'https://your-synkora-instance.com',
  conversationIdProvider: () => chatController.conversationId,
);

// Optional: handle foreground messages
SynkoraPush.onMessage = (message) {
  // show in-app banner or navigate to chat
  // message.data['conversation_id'] available for deep-linking
};`}
                </pre>
              )}
            </div>

            {/* Requirements note */}
            <div className="mt-3 flex items-start gap-2 text-xs text-ink-mute">
              <CheckCircle className="h-3.5 w-3.5 text-leaf flex-shrink-0 mt-0.5" />
              <span>
                Make sure <strong className="text-ink-soft">Allow Mobile Apps</strong> is enabled above, and run{" "}
                <code className={codeInlineClass}>flutter pub get</code> then{" "}
                <code className={codeInlineClass}>flutter pub run build_runner build</code> after adding the dependency.
              </span>
            </div>
          </div>

        </form>
    </AgentPageShell>
  );
}
