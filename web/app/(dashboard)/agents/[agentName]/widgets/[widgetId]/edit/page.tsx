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
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
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
  theme_config?: Record<string, string>;
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
      toast.success("New secret generated — copy it now, it won't be shown again");
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

  const sectionClass =
    "rounded-[1.9rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] sm:p-7";
  const inputClass =
    "w-full rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]";
  const compactInputClass =
    "rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]";
  const codeInlineClass =
    "rounded-md border border-black/5 bg-white/80 px-1.5 py-0.5 font-mono text-[11px] text-gray-700";

  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]" />
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
        <AgentPagePanel className="border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-4">
          <p className="text-sm text-[#8a445c]">Widget not found.</p>
        </AgentPagePanel>
      </AgentPageShell>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Edit Widget"
      description={<>Update settings for <span className="font-semibold text-gray-900">{widget.widget_name}</span>.</>}
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
            className="inline-flex items-center justify-center rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
          >
            Cancel
          </Link>
          <button
            type="submit"
            form="widget-edit-form"
            disabled={saving}
            className="inline-flex items-center justify-center rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      }
    >

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-[1rem] border border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-3">
            <p className="text-sm text-[#8a445c]">{error}</p>
          </div>
        )}

        <form
          id="widget-edit-form"
          onSubmit={handleSave}
          className="space-y-6"
        >

          {/* ── Flutter SDK highlight banner ───────────────────────────────────── */}
          <div className="relative overflow-hidden rounded-[1.9rem] border border-[#d7dcee] bg-[linear-gradient(135deg,_rgba(240,244,253,0.98),_rgba(247,241,251,0.96)_55%,_rgba(252,243,246,0.95)_100%)] p-6 shadow-[0_24px_60px_-46px_rgba(57,75,120,0.24)]">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[1rem] border border-white/80 bg-white/90 shadow-sm">
                <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none">
                  <path d="M14.314 0L2.3 12 6 15.7 21.684 0h-7.37zm.014 11.072L7.857 17.53l6.47 6.47H21.7l-6.46-6.468 6.46-6.46h-7.37z" fill="#54C5F8"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-indigo-900">Flutter SDK available</h3>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">pub.dev</span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">Open Source</span>
                </div>
                <p className="text-xs text-indigo-700 mb-3">
                  Embed this AI agent natively into any Flutter app — Android, iOS, and beyond. Drop-in chat UI, SSE streaming, local message cache, and optional FCM push notifications.
                </p>
                <div className="flex items-center gap-3 flex-wrap">
                  <code className="rounded-md border border-indigo-200 bg-white/90 px-2 py-1 font-mono text-xs text-indigo-800">
                    flutter pub add synkora_chat
                  </code>
                  <span className="text-xs text-indigo-500">·</span>
                  <code className="rounded-md border border-indigo-200 bg-white/90 px-2 py-1 font-mono text-xs text-indigo-800">
                    flutter pub add synkora_push
                  </code>
                  <span className="text-xs text-indigo-400">optional, for push notifications</span>
                </div>
              </div>
              {/* Decorative blobs */}
              <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-indigo-100 opacity-40 pointer-events-none" />
              <div className="absolute right-8 -bottom-6 w-16 h-16 rounded-full bg-purple-100 opacity-40 pointer-events-none" />
            </div>
          </div>

          {/* ── General ───────────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">General</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Widget name <span className="text-red-500">*</span>
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
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Allowed domains
                  <span className="ml-1 font-normal text-gray-500">(comma-separated, leave blank to allow all)</span>
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
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Rate limit <span className="font-normal text-gray-500">(requests / hour)</span>
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
                    className="h-4 w-4 rounded border-gray-300 text-[#2d8b69] focus:ring-[#79dfbc]"
                  />
                  <span className="text-sm text-gray-700">Widget is active</span>
                </label>
                <p className="mt-1 text-xs text-gray-500 ml-6">Inactive widgets stop accepting all traffic</p>
              </div>
            </div>
          </div>

          {/* ── Chat Appearance ───────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <Palette className="h-5 w-5 text-[#2d8b69]" />
              <h2 className="text-lg font-semibold text-gray-900">Chat Appearance</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Override the default agent appearance for this widget. Leave blank to use the agent&apos;s defaults.
            </p>

            <div className="space-y-4">
              {/* Primary color */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Brand color</label>
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
                  <span className="text-xs text-gray-500">Used for the toggle button, hero, and accents</span>
                </div>
              </div>

              {/* Welcome message */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">
                  Welcome message
                  <span className="ml-1 font-normal text-gray-500">(shown in the home screen hero)</span>
                </label>
                <textarea
                  value={welcomeMessage}
                  onChange={(e) => setWelcomeMessage(e.target.value)}
                  rows={2}
                  placeholder={"Hi there 👋\nHow can we help?"}
                  className={`${inputClass} resize-none`}
                />
                <p className="mt-1 text-xs text-gray-400">Use a newline to split into title + subtitle</p>
              </div>

              {/* Placeholder */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Input placeholder</label>
                <input
                  type="text"
                  value={chatPlaceholder}
                  onChange={(e) => setChatPlaceholder(e.target.value)}
                  placeholder="Message…"
                  className={inputClass}
                />
              </div>

              {/* Live preview swatch */}
              <div className="rounded-xl overflow-hidden border border-gray-200 mt-2">
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
                <div className="bg-gray-50 px-4 py-3 flex items-center gap-2">
                  <input
                    readOnly
                    value=""
                    placeholder={chatPlaceholder || "Message…"}
                    className="flex-1 text-sm text-gray-400 bg-transparent outline-none"
                  />
                  <div className="w-7 h-7 rounded-full flex items-center justify-center" style={{ background: primaryColor }}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><line x1="22" y1="2" x2="11" y2="13" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/><polygon points="22 2 15 22 11 13 2 9 22 2" fill="#fff"/></svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Pre-chat Form ─────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-[#2d8b69]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <h2 className="text-lg font-semibold text-gray-900">Pre-chat Form</h2>
              </div>
              <button
                type="button"
                onClick={() => setPreChatEnabled(!preChatEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${preChatEnabled ? 'bg-[#2d8b69]' : 'bg-gray-200'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${preChatEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Show a short form before the first message to collect user info. Applies to anonymous users only — identified users skip it automatically.
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
                    <span className="text-sm text-gray-700">{label}</span>
                    <button
                      type="button"
                      onClick={() => set(!value)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${value ? 'bg-[#2d8b69]' : 'bg-gray-200'}`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${value ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* ── Identity Verification ─────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <Shield className="h-5 w-5 text-[#2d8b69]" />
              <h2 className="text-lg font-semibold text-gray-900">Identity Verification</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Prevent end-users from impersonating each other using HMAC signatures generated on your server.
            </p>

            {/* Toggle */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={identityVerificationRequired}
                  onChange={(e) => setIdentityVerificationRequired(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#2d8b69] focus:ring-[#79dfbc]"
                />
                <span className="text-sm text-gray-700">Require identity verification on every request</span>
              </label>
              <p className="mt-1 text-xs text-gray-500 ml-6">
                When enabled, requests without a valid{" "}
                <code className={codeInlineClass}>userHash</code> are rejected with HTTP 403.
              </p>
            </div>

            {identityVerificationRequired && (
              <div className="mb-4 flex gap-2 rounded-[1rem] border border-[#ead8aa] bg-[linear-gradient(180deg,_rgba(255,251,237,0.98),_rgba(251,244,217,0.96))] p-3 text-xs text-[#8b6615]">
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span>
                  Make sure your server is generating the hash before enabling this, otherwise all widget traffic will be blocked.
                </span>
              </div>
            )}

            {/* Secret */}
            <div className="border-t border-gray-200 pt-4 space-y-2">
              <h3 className="text-sm font-medium text-gray-700">Identity secret</h3>
              <p className="text-xs text-gray-500">
                Compute <code className={codeInlineClass}>HMAC-SHA256(secret, userId)</code> on your server and pass
                it as <code className={codeInlineClass}>userHash</code> in the widget init call.{" "}
                <span className="font-medium text-gray-700">Never expose this secret in the browser.</span>
              </p>

              {identitySecret ? (
                <div className="flex items-center gap-2 rounded-[1rem] border border-[#d8e5d9] bg-[linear-gradient(180deg,_rgba(244,249,245,0.98),_rgba(235,245,238,0.95))] px-3 py-2">
                  <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                  <code className="text-xs text-green-800 break-all flex-1">
                    {showSecret ? identitySecret : "•".repeat(44)}
                  </code>
                  <button
                    type="button"
                    onClick={() => setShowSecret(!showSecret)}
                    className="text-green-600 hover:text-green-800 transition-colors"
                  >
                    {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(identitySecret)}
                    className="text-green-600 hover:text-green-800 transition-colors"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <p className="text-xs text-gray-500 italic">
                  The secret was shown when this widget was created. Use the button below to rotate it.
                </p>
              )}

              <button
                type="button"
                onClick={handleRegenerateSecret}
                disabled={regeneratingSecret}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-red-600 transition-colors disabled:opacity-50 font-medium"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${regeneratingSecret ? "animate-spin" : ""}`} />
                Regenerate secret
              </button>
            </div>

            {/* Code examples */}
            <details className="mt-4 group">
              <summary className="flex items-center gap-1.5 text-sm font-medium text-gray-600 cursor-pointer select-none list-none">
                <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
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
                  <div key={lang} className="overflow-hidden rounded-[1rem] bg-[#171717] text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                    <div className="flex items-center justify-between bg-gray-800 px-3 py-1.5">
                      <span className="text-gray-400 text-[11px] uppercase tracking-wide">{lang}</span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(code)}
                        className="text-gray-400 hover:text-white transition-colors"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <pre className="overflow-x-auto p-3 leading-relaxed text-[#d4f4da]">{code}</pre>
                  </div>
                ))}

                <div className="rounded-[1rem] border border-[#e5d9ca] bg-[#fcfaf5] p-3 text-xs text-gray-600">
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
              <svg className="h-5 w-5 text-[#2d8b69]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 8.25h3m-3 3h3m-3 3h3" />
              </svg>
              <h2 className="text-lg font-semibold text-gray-900">Mobile &amp; Push Notifications</h2>
            </div>
            <p className="text-sm text-gray-500 mb-5">
              Enable the Flutter SDK and optionally configure FCM to send push notifications when the agent replies.
            </p>

            {/* Mobile allowed toggle */}
            <div className="flex items-center justify-between py-3 border-b border-gray-100 mb-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Allow Mobile Apps (Flutter SDK)</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Skips the browser Origin check so requests from the Flutter SDK are accepted.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMobileAllowed(!mobileAllowed)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${mobileAllowed ? "bg-[#171717]" : "bg-gray-200"}`}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${mobileAllowed ? "translate-x-5" : "translate-x-0"}`} />
              </button>
            </div>

            {/* FCM Server Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">FCM Server Key (optional)</label>
              <p className="text-xs text-gray-500 mb-2">
                Paste your Firebase service account JSON or FCM server key. Stored encrypted. Leave blank to keep the existing key.
              </p>
              <div className="relative">
                <input
                  type={showFcmKey ? "text" : "password"}
                  value={fcmServerKey}
                  onChange={(e) => setFcmServerKey(e.target.value)}
                  placeholder="Paste FCM server key or service account JSON..."
                  className={`pr-10 ${inputClass}`}
                />
                <button
                  type="button"
                  onClick={() => setShowFcmKey(!showFcmKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showFcmKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* ── Agent Routing ─────────────────────────────────────────────────── */}
          <div className={sectionClass}>
            <div className="flex items-center gap-2 mb-1">
              <GitBranch className="h-5 w-5 text-[#2d8b69]" />
              <h2 className="text-lg font-semibold text-gray-900">Agent Routing</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Route different customer orgs to different agents — each with their own knowledge base, prompts, and tools.
            </p>

            {/* Toggle */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={enableAgentRouting}
                  onChange={(e) => setEnableAgentRouting(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#2d8b69] focus:ring-[#79dfbc]"
                />
                <span className="text-sm text-gray-700">Enable org-based agent routing</span>
              </label>
              <p className="mt-1 text-xs text-gray-500 ml-6">
                When enabled, requests with a <code className={codeInlineClass}>user.orgId</code> are routed using
                the table below. Unmatched orgs fall back to this widget&apos;s default agent.
              </p>
            </div>

            {enableAgentRouting && (
              <div className="border-t border-gray-200 pt-4 space-y-4">
                {/* Routes table */}
                {routes.length > 0 ? (
                  <div className="overflow-hidden rounded-[1rem] border border-[#e5d9ca]">
                    <table className="w-full text-sm">
                      <thead className="bg-[#f7f2e7]">
                        <tr>
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                            Org ID
                          </th>
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                            Agent
                          </th>
                          <th className="px-4 py-2.5 w-10" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {routes.map((route) => (
                          <tr key={route.external_org_id} className="hover:bg-gray-50">
                            <td className="px-4 py-3">
                              <code className={codeInlineClass}>{route.external_org_id}</code>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-700">{route.agent_name || route.agent_id}</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => handleDeleteRoute(route.external_org_id)}
                                className="text-gray-400 hover:text-red-500 transition-colors"
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
                  <p className="text-sm text-gray-500 italic">
                    No routes yet. All orgs will use this widget&apos;s default agent.
                  </p>
                )}

                {/* Add route */}
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Org ID</label>
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
                    <label className="block text-xs font-medium text-gray-600 mb-1">Route to agent</label>
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
                    className="flex items-center gap-1.5 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" />
                    Add
                  </button>
                </div>

                <div className="rounded-[1rem] border border-[#d8e5d9] bg-[linear-gradient(180deg,_rgba(244,249,245,0.98),_rgba(235,245,238,0.95))] p-3 text-xs text-[#24543b]">
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
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none">
                <path d="M14.314 0L2.3 12 6 15.7 21.684 0h-7.37zm.014 11.072L7.857 17.53l6.47 6.47H21.7l-6.46-6.468 6.46-6.46h-7.37z" fill="#54C5F8"/>
              </svg>
              <h2 className="text-lg font-semibold text-gray-900">Flutter Integration</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Copy the snippet below to integrate this widget into your Flutter app. Enable "Allow Mobile Apps" above first.
            </p>

            {/* Tabs */}
            <div className="mb-3 flex w-fit gap-1 rounded-[1rem] border border-black/10 bg-white/80 p-1.5 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
              {(["pubspec", "basic", "push"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setFlutterTab(tab)}
                  className={`rounded-[0.85rem] px-3 py-2 text-xs font-semibold transition-colors ${
                    flutterTab === tab
                      ? "bg-[#171717] text-white shadow-[0_10px_22px_rgba(0,0,0,0.12)]"
                      : "text-gray-500 hover:bg-[#f7f2e7] hover:text-[#171717]"
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
                    pubspec: `dependencies:\n  synkora_chat: ^1.0.0\n\n# Optional — for push notifications\n  synkora_push: ^1.0.0`,
                    basic: `import 'package:synkora_chat/synkora_chat.dart';\n\n// Drop-in — place anywhere in your widget tree\nSynkoraChatWidget(\n  widgetKey: '${widgetId}',\n  baseUrl: 'https://your-synkora-instance.com',\n  userId: currentUser.id,  // optional\n  onClose: () => Navigator.pop(context),\n)`,
                    push: `// main.dart\nvoid main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n  await Firebase.initializeApp();\n\n  await SynkoraPush.init(\n    widgetKey: '${widgetId}',\n    baseUrl: 'https://your-synkora-instance.com',\n    conversationIdProvider: () => chatController.conversationId,\n  );\n\n  // Optional: handle foreground messages\n  SynkoraPush.onMessage = (message) {\n    // show in-app banner or navigate to chat\n  };\n\n  runApp(MyApp());\n}`,
                  };
                  navigator.clipboard.writeText(snippets[flutterTab]);
                }}
                className="absolute top-3 right-3 z-10 rounded-[0.85rem] bg-white/10 p-2 text-gray-300 transition-colors hover:bg-white/20 hover:text-white"
                title="Copy to clipboard"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>

              {flutterTab === "pubspec" && (
                <pre className="overflow-x-auto rounded-[1rem] bg-[#171717] p-4 text-xs leading-relaxed text-[#f6f1e8]">
{`dependencies:
  synkora_chat: ^1.0.0

  # Optional — for FCM push notifications
  synkora_push: ^1.0.0`}
                </pre>
              )}

              {flutterTab === "basic" && (
                <pre className="overflow-x-auto rounded-[1rem] bg-[#171717] p-4 text-xs leading-relaxed text-[#f6f1e8]">
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
                <pre className="overflow-x-auto rounded-[1rem] bg-[#171717] p-4 text-xs leading-relaxed text-[#f6f1e8]">
{`// main.dart — call once after Firebase.initializeApp()
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
            <div className="mt-3 flex items-start gap-2 text-xs text-gray-500">
              <CheckCircle className="h-3.5 w-3.5 text-green-500 flex-shrink-0 mt-0.5" />
              <span>
                Make sure <strong className="text-gray-700">Allow Mobile Apps</strong> is enabled above, and run{" "}
                <code className={codeInlineClass}>flutter pub get</code> then{" "}
                <code className={codeInlineClass}>flutter pub run build_runner build</code> after adding the dependency.
              </span>
            </div>
          </div>

        </form>
    </AgentPageShell>
  );
}
