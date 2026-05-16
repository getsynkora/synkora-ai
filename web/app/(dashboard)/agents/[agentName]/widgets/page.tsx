"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  Trash2,
  Edit,
  Copy,
  RefreshCw,
  Eye,
  BarChart3,
  Globe,
  Key,
  AlertCircle,
  LayoutPanelTop,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import toast from "react-hot-toast";
import AgentPageShell from '@/components/agents/AgentPageShell'

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
  created_at: string;
  updated_at: string;
}

export default function AgentWidgetsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEmbedCode, setShowEmbedCode] = useState(false);
  const [embedCode, setEmbedCode] = useState("");

  useEffect(() => {
    fetchWidgets();
  }, [agentName]);

  const fetchWidgets = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get agent details using agents endpoint
      const agentResponse = await apiClient.request('GET', `/api/v1/agents/${agentName}`);
      
      if (!agentResponse.success || !agentResponse.data) {
        setError("Agent not found");
        return;
      }

      // Fetch widgets for this agent using the agent ID
      const widgets = await apiClient.getWidgets(agentResponse.data.id);
      setWidgets(widgets);
    } catch (err: any) {
      console.error("Failed to fetch widgets:", err);
      setError(extractErrorMessage(err, "Failed to load widgets"))
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWidget = async (widgetId: string) => {
    if (!confirm("Are you sure you want to delete this widget?")) {
      return;
    }

    try {
      await apiClient.deleteWidget(widgetId);
      await fetchWidgets();
      toast.success("Widget deleted");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to delete widget"))
    }
  };

  const handleRegenerateKey = async (widgetId: string) => {
    if (!confirm("Are you sure you want to regenerate the API key? The old key will stop working.")) {
      return;
    }

    try {
      await apiClient.regenerateWidgetKey(widgetId);
      await fetchWidgets();
      toast.success("API key regenerated successfully");
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to regenerate API key"))
    }
  };

  const handleShowEmbedCode = async (widgetId: string) => {
    try {
      const response = await apiClient.getWidgetEmbedCode(widgetId);
      setEmbedCode(response.data?.embed_code || response.embed_code);
      setShowEmbedCode(true);
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to get embed code"))
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600"></div>
      </div>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Agent Widgets"
      description={<>Embed your agent <span className="font-semibold text-gray-900">{agentName}</span> on external websites.</>}
      icon={LayoutPanelTop}
      badge="Embeddable UI"
      actions={
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus className="w-4 h-4" />
          Create Widget
        </button>
      }
    >

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-red-900 text-sm">Error</h3>
            <p className="text-red-700 text-xs mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Widgets List */}
      {widgets.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border-2 border-dashed border-red-300 shadow-sm">
          <Globe className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <h3 className="text-base font-medium text-gray-900 mb-2">
            No widgets yet
          </h3>
          <p className="text-gray-600 text-sm mb-4">
            Create your first widget to embed this agent on external websites
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all text-xs font-medium shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Create Widget
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {widgets.map((widget) => (
            <div
              key={widget.widget_id}
              className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md hover:border-red-300 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-base font-semibold text-gray-900">
                      {widget.widget_name}
                    </h3>
                    <span
                      className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                        widget.is_active
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {widget.is_active ? "Active" : "Inactive"}
                    </span>
                    {widget.identity_verification_required && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800">
                        Identity verified
                      </span>
                    )}
                    {widget.enable_agent_routing && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                        Routing on
                      </span>
                    )}
                  </div>

                  <div className="space-y-1.5 text-xs text-gray-600">
                    <div className="flex items-center gap-2">
                      <Globe className="w-3.5 h-3.5" />
                      <span>
                        Domains:{" "}
                        {widget.allowed_domains && widget.allowed_domains.length > 0
                          ? widget.allowed_domains.join(", ")
                          : "All domains allowed"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <BarChart3 className="w-3.5 h-3.5" />
                      <span>Rate limit: {widget.rate_limit} requests/hour</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Key className="w-3.5 h-3.5" />
                      <span className="font-mono">
                        Created: {new Date(widget.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleShowEmbedCode(widget.widget_id)}
                    className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="View embed code"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleRegenerateKey(widget.widget_id)}
                    className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Regenerate API key"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => router.push(`/agents/${agentName}/widgets/${widget.widget_id}/edit`)}
                    className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Edit widget"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteWidget(widget.widget_id)}
                    className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete widget"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Embed Code Modal */}
      {showEmbedCode && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-[1.9rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_32px_90px_-42px_rgba(73,45,23,0.35)]">
            <div className="p-6 sm:p-7">
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Widget Setup</p>
                  <h2 className="mt-2 text-[2rem] font-semibold tracking-[-0.04em] text-gray-950">Embed Code</h2>
                </div>
                <button
                  onClick={() => setShowEmbedCode(false)}
                  className="rounded-[0.95rem] p-2 text-gray-400 transition-colors hover:bg-[#f3ecde] hover:text-[#171717]"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <p className="mb-4 text-sm leading-6 text-gray-600">
                Copy and paste this code into your website's HTML:
              </p>

              <div className="relative">
                <pre className="overflow-x-auto rounded-[1.25rem] bg-[#171717] p-4 text-xs text-[#f6f1e8] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <code>{embedCode}</code>
                </pre>
                <button
                  onClick={() => copyToClipboard(embedCode)}
                  className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-[0.8rem] bg-white/10 px-2.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-white/20"
                  title="Copy to clipboard"
                >
                  <Copy className="w-4 h-4" />
                  Copy
                </button>
              </div>

              <div className="mt-5 rounded-[1.25rem] border border-[#e5d9ca] bg-[#fcfaf5] p-4">
                <h3 className="mb-2 text-sm font-semibold text-gray-900">Setup Instructions</h3>
                <ol className="list-decimal list-inside space-y-1.5 text-xs leading-6 text-gray-600">
                  <li>Copy the embed code above</li>
                  <li>Paste it into your website's HTML where you want the widget to appear</li>
                  <li>The widget will automatically load and connect to your agent</li>
                  <li>Customize the theme in the widget settings if needed</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Widget Modal */}
      {showCreateModal && (
        <CreateWidgetModal
          agentName={agentName}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            fetchWidgets();
          }}
        />
      )}
    </AgentPageShell>
  );
}

// Create Widget Modal Component
function CreateWidgetModal({
  agentName,
  onClose,
  onSuccess,
}: {
  agentName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState({
    widget_name: "",
    allowed_domains: "",
    rate_limit: 100,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Get agent ID using the agents endpoint
      const agentResponse = await apiClient.request('GET', `/api/v1/agents/${agentName}`);
      
      if (!agentResponse.success || !agentResponse.data) {
        throw new Error("Agent not found");
      }

      // Parse domains
      const domains = formData.allowed_domains
        .split(",")
        .map((d) => d.trim())
        .filter((d) => d.length > 0);

      // Create widget
      await apiClient.createWidget({
        agent_id: agentResponse.data.id,
        widget_name: formData.widget_name,
        allowed_domains: domains.length > 0 ? domains : null,
        rate_limit: formData.rate_limit,
      });

      onSuccess();
    } catch (err: any) {
      console.error("Failed to create widget:", err);
      setError(extractErrorMessage(err, err.message || "Failed to create widget"))
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="w-full max-w-[56rem] rounded-[2rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.985),_rgba(249,245,239,0.965))] shadow-[0_36px_110px_-44px_rgba(73,45,23,0.36)]">
        <div className="p-7 sm:p-8">
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9a7a5e]">Embeddable UI</p>
              <h2 className="mt-2 text-[2rem] font-semibold tracking-[-0.04em] text-gray-950">Create Widget</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-gray-600">
                Configure a website widget for this agent. Keep it narrow and simple so it can be embedded without extra setup.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-[0.95rem] p-2 text-gray-400 transition-colors hover:bg-[#f3ecde] hover:text-[#171717]"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {error && (
            <div className="mb-5 rounded-[1rem] border border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-3 text-xs text-[#8a445c]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid gap-5 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">
                Widget Name *
                </label>
                <input
                  type="text"
                  value={formData.widget_name}
                  onChange={(e) =>
                    setFormData({ ...formData, widget_name: e.target.value })
                  }
                  className="w-full rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3.5 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]"
                  placeholder="My Website Widget"
                  required
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">
                  Allowed Domains
                </label>
                <input
                  type="text"
                  value={formData.allowed_domains}
                  onChange={(e) =>
                    setFormData({ ...formData, allowed_domains: e.target.value })
                  }
                  className="w-full rounded-[1.1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3.5 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]"
                  placeholder="example.com, *.example.com"
                />
                <p className="mt-2 text-xs leading-6 text-gray-500">
                  Comma-separated list. Use <span className="font-semibold text-gray-700">*</span> for wildcards. Leave empty to allow all domains.
                </p>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">
                  Rate Limit
                </label>
                <div className="rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3">
                  <input
                    type="number"
                    value={formData.rate_limit}
                    onChange={(e) =>
                      setFormData({ ...formData, rate_limit: parseInt(e.target.value) })
                    }
                    className="w-full border-0 bg-transparent p-0 text-sm text-gray-900 focus:outline-none focus:ring-0"
                    min="1"
                    max="10000"
                    required
                  />
                  <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9a7a5e]">
                    Requests per hour
                  </p>
                </div>
              </div>

              <div className="rounded-[1.25rem] border border-[#e5d9ca] bg-[#fcfaf5] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#9a7a5e]">Notes</p>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  Widgets are created active by default. You can edit routing, verification, theme, and domain restrictions later.
                </p>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-[#ece2d6] pt-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center justify-center rounded-[1rem] border border-black/10 bg-white/80 px-5 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="inline-flex items-center justify-center rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
                disabled={loading}
              >
                {loading ? "Creating..." : "Create Widget"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
