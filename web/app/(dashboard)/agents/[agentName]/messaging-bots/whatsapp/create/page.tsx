"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  MessageCircle,
  CheckCircle,
  Smartphone,
  Cloud,
  ExternalLink,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { whatsappBotsApi } from "@/lib/api/messaging-bots";
import type { CreateWhatsAppBotRequest, WhatsAppQREvent } from "@/types/messaging-bots";
import AgentPageShell, {
  AgentPagePanel,
  AgentPageTabs,
} from "@/components/agents/AgentPageShell";

type ActiveTab = "cloud_api" | "device_link";
type QRStep = 1 | 2 | 3;

const fieldClass =
  "w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]";
const sectionTitleClass =
  "mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]";
const helperTextClass = "mt-1 text-xs text-gray-500";
const secondaryButtonClass =
  "rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]";
const primaryButtonClass =
  "inline-flex items-center justify-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50";

export default function CreateWhatsAppBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("cloud_api");

  // Cloud API form state
  const [formData, setFormData] = useState<CreateWhatsAppBotRequest>({
    agent_id: "",
    bot_name: "",
    phone_number_id: "",
    business_account_id: "",
    access_token: "",
    verify_token: "",
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Device Link (QR) flow state
  const [agentId, setAgentId] = useState("");
  const [qrStep, setQrStep] = useState<QRStep>(1);
  const [qrBotName, setQrBotName] = useState("");
  const [qrBotNameError, setQrBotNameError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [qrData, setQrData] = useState<string | null>(null);
  const [qrStatus, setQrStatus] = useState<string>("Waiting for QR code...");
  const [connectedPhone, setConnectedPhone] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const [startingQR, setStartingQR] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const loadAgent = async () => {
      try {
        const agent = await apiClient.getAgent(agentName);
        setAgentId(agent.id);
        setFormData((prev) => ({ ...prev, agent_id: agent.id }));
      } catch (err: any) {
        setError(err?.response?.data?.message || "Failed to load agent");
      } finally {
        setLoading(false);
      }
    };
    loadAgent();
  }, [agentName]);

  useEffect(() => {
    return () => {
      closeEventSource();
    };
  }, []);

  const validateCloudForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.bot_name.trim()) newErrors.bot_name = "Bot name is required";
    if (!formData.phone_number_id.trim()) newErrors.phone_number_id = "Phone number ID is required";
    if (!formData.business_account_id.trim()) newErrors.business_account_id = "WhatsApp Business Account ID is required";
    if (!formData.access_token.trim()) newErrors.access_token = "Access token is required";
    setFormErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleCloudSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateCloudForm()) return;
    setSubmitting(true);
    setError(null);
    try {
      await whatsappBotsApi.createBot(formData);
      router.push(`/agents/${agentName}/messaging-bots`);
    } catch (err: any) {
      setError(err?.response?.data?.message || "Failed to create WhatsApp bot");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCloudChange = (field: keyof CreateWhatsAppBotRequest, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (formErrors[field]) {
      setFormErrors((prev) => ({ ...prev, [field]: "" }));
    }
  };

  const closeEventSource = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const handleStartQR = async () => {
    if (!qrBotName.trim()) {
      setQrBotNameError("Bot name is required");
      return;
    }
    setQrBotNameError("");
    setStartingQR(true);
    setQrError(null);

    try {
      const { session_id } = await whatsappBotsApi.startQRSession(agentId, qrBotName);
      setSessionId(session_id);
      setQrStep(2);
      setQrStatus("Waiting for QR code...");
      openEventSource(session_id);
    } catch (err: any) {
      setQrError(err?.response?.data?.detail || "Failed to start QR session");
    } finally {
      setStartingQR(false);
    }
  };

  const openEventSource = (sid: string) => {
    closeEventSource();

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";
    const url = `${baseUrl}/api/v1/whatsapp-bots/qr/${sid}/stream`;

    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;

    es.onmessage = async (event) => {
      try {
        const payload: WhatsAppQREvent = JSON.parse(event.data);

        if (payload.type === "qr" && payload.qr_data) {
          setQrData(payload.qr_data);
          setQrStatus("Scan the QR code with WhatsApp on your phone");
        } else if (payload.type === "status" && payload.status === "scanning") {
          setQrStatus("Scanning... keep your phone steady");
        } else if (payload.type === "connected") {
          setQrStatus("Connected!");
          es.close();
          eventSourceRef.current = null;
          try {
            await whatsappBotsApi.saveQRBot(sid, agentId, qrBotName);
            setConnectedPhone(payload.phone_number || "Linked device");
            setQrStep(3);
          } catch (saveErr: any) {
            setQrError(saveErr?.response?.data?.detail || "Connected but failed to save bot");
            setQrStep(1);
          }
        } else if (payload.type === "error") {
          setQrError(payload.message || "An error occurred");
          es.close();
          eventSourceRef.current = null;
          setQrStep(1);
        }
      } catch {
        // Ignore malformed SSE payloads
      }
    };

    es.onerror = () => {
      setQrError("Connection to server lost. Please try again.");
      es.close();
      eventSourceRef.current = null;
      setQrStep(1);
    };
  };

  const handleCancelQR = async () => {
    closeEventSource();
    if (sessionId) {
      try {
        await whatsappBotsApi.cancelQRSession(sessionId);
      } catch {
        // best-effort cancel
      }
      setSessionId(null);
    }
    setQrStep(1);
    setQrData(null);
    setQrStatus("Waiting for QR code...");
    setQrError(null);
  };

  const inputClass = (hasError?: boolean) =>
    `${fieldClass} ${hasError ? "border-[#e4b7c6] focus:ring-[#f0bfd0]" : ""}`.trim();

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]"></div>
      </div>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Create WhatsApp Bot"
      description={
        <>
          Connect your agent <span className="font-semibold text-gray-900">{agentName}</span> to WhatsApp using Cloud API credentials or a QR-based device link.
        </>
      }
      icon={MessageCircle}
      badge="Messaging Setup"
      maxWidthClassName="max-w-5xl"
    >
      <AgentPagePanel className="mb-5 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[1rem] border border-black/10 bg-[#f1eadc]">
            <AlertCircle className="h-4 w-4 text-[#171717]" />
          </div>
          <div className="flex-1">
            <h3 className="mb-2 text-sm font-semibold text-gray-950">
              Choose how you want to connect WhatsApp
            </h3>
            <div className="space-y-2 text-xs leading-6 text-gray-600">
              <p>
                <strong className="text-gray-900">Cloud API</strong> is best for production WhatsApp Business setups with Meta credentials.
              </p>
              <p>
                <strong className="text-gray-900">Device Link</strong> lets you connect a phone by scanning a QR code, which is faster for testing and internal workflows.
              </p>
              <a
                href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-[#171717] transition-colors hover:text-black"
              >
                Open WhatsApp setup guide
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </div>
      </AgentPagePanel>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-[1.25rem] border border-[#ead8e1] bg-[#f8ecef] px-4 py-4">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#8b5a74]" />
          <div>
            <h3 className="text-sm font-semibold text-[#6f435b]">Error</h3>
            <p className="mt-1 text-xs text-[#8b5a74]">{error}</p>
          </div>
        </div>
      )}

      <div className="mb-5">
        <AgentPageTabs
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as ActiveTab)}
          className="inline-flex"
          items={[
            { id: "cloud_api", label: "Cloud API", icon: <Cloud size={15} /> },
            { id: "device_link", label: "Device Link (QR)", icon: <Smartphone size={15} /> },
          ]}
        />
      </div>

      {activeTab === "cloud_api" && (
        <>
          <div className="mb-5 rounded-[1.35rem] border border-[#d7e6ea] bg-[#edf4f6] p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#486c77]">Before you begin</h3>
            <ul className="list-inside list-disc space-y-1 text-xs text-[#486c77]">
              <li>Create a Facebook Developer account at developers.facebook.com</li>
              <li>Set up WhatsApp Business API in your Facebook app</li>
              <li>Get your Phone Number ID and Access Token</li>
              <li>Configure webhook URL in Facebook dashboard</li>
            </ul>
            <a
              href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[#171717] hover:text-black"
            >
              View setup guide
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          <AgentPagePanel className="overflow-hidden">
            <form onSubmit={handleCloudSubmit}>
              <div className="space-y-5 p-6">
                <div>
                  <label htmlFor="bot_name" className={sectionTitleClass}>
                    Bot Name <span className="text-[#8b5a74]">*</span>
                  </label>
                  <input
                    type="text"
                    id="bot_name"
                    value={formData.bot_name}
                    onChange={(e) => handleCloudChange("bot_name", e.target.value)}
                    className={inputClass(!!formErrors.bot_name)}
                    placeholder="e.g., Customer Support Bot"
                  />
                  {formErrors.bot_name && <p className="mt-1 text-xs text-[#8b5a74]">{formErrors.bot_name}</p>}
                </div>

                <div>
                  <label htmlFor="phone_number_id" className={sectionTitleClass}>
                    Phone Number ID <span className="text-[#8b5a74]">*</span>
                  </label>
                  <input
                    type="text"
                    id="phone_number_id"
                    value={formData.phone_number_id}
                    onChange={(e) => handleCloudChange("phone_number_id", e.target.value)}
                    className={inputClass(!!formErrors.phone_number_id)}
                    placeholder="123456789012345"
                  />
                  {formErrors.phone_number_id && (
                    <p className="mt-1 text-xs text-[#8b5a74]">{formErrors.phone_number_id}</p>
                  )}
                  <p className={helperTextClass}>Find this in your WhatsApp Business API settings.</p>
                </div>

                <div>
                  <label htmlFor="business_account_id" className={sectionTitleClass}>
                    WhatsApp Business Account ID <span className="text-[#8b5a74]">*</span>
                  </label>
                  <input
                    type="text"
                    id="business_account_id"
                    value={formData.business_account_id}
                    onChange={(e) => handleCloudChange("business_account_id", e.target.value)}
                    className={inputClass(!!formErrors.business_account_id)}
                    placeholder="123456789012345"
                  />
                  {formErrors.business_account_id && (
                    <p className="mt-1 text-xs text-[#8b5a74]">{formErrors.business_account_id}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="access_token" className={sectionTitleClass}>
                    Access Token <span className="text-[#8b5a74]">*</span>
                  </label>
                  <input
                    type="password"
                    id="access_token"
                    value={formData.access_token}
                    onChange={(e) => handleCloudChange("access_token", e.target.value)}
                    className={`${inputClass(!!formErrors.access_token)} font-mono`}
                    placeholder="EAAxxxxxxxxxx..."
                  />
                  {formErrors.access_token && (
                    <p className="mt-1 text-xs text-[#8b5a74]">{formErrors.access_token}</p>
                  )}
                  <p className={helperTextClass}>
                    Generate from your Facebook app settings. It will be stored securely.
                  </p>
                </div>

                <div>
                  <label htmlFor="verify_token" className={sectionTitleClass}>
                    Webhook Verify Token
                  </label>
                  <input
                    type="text"
                    id="verify_token"
                    value={formData.verify_token}
                    onChange={(e) => handleCloudChange("verify_token", e.target.value)}
                    className={fieldClass}
                    placeholder="your_verify_token"
                  />
                  <p className={helperTextClass}>
                    Optional. Use this for webhook verification in the Facebook dashboard.
                  </p>
                </div>

                <div className="rounded-[1.35rem] border border-[#d7e6ea] bg-[#edf4f6] p-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#486c77]">Webhook Configuration</h3>
                  <p className="mb-2 text-xs text-[#486c77]">Configure this webhook URL in your Facebook app:</p>
                  <code className="block overflow-x-auto rounded-[1rem] border border-[#bfd6dc] bg-white px-3 py-3 text-xs text-gray-800">
                    {typeof window !== "undefined" ? window.location.origin : ""}/api/v1/whatsapp/webhook
                  </code>
                </div>

                <div className="flex flex-col-reverse gap-3 border-t border-black/10 pt-4 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
                    className={secondaryButtonClass}
                    disabled={submitting}
                  >
                    Cancel
                  </button>
                  <button type="submit" disabled={submitting} className={primaryButtonClass}>
                    {submitting ? (
                      <>
                        <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-white"></div>
                        Creating...
                      </>
                    ) : (
                      "Create WhatsApp Bot"
                    )}
                  </button>
                </div>
              </div>
            </form>
          </AgentPagePanel>
        </>
      )}

      {activeTab === "device_link" && (
        <AgentPagePanel className="overflow-hidden p-6">
          {qrStep === 1 && (
            <div className="space-y-5">
              <div className="rounded-[1.35rem] border border-[#ead8aa] bg-[linear-gradient(180deg,_rgba(255,251,237,0.98),_rgba(251,244,217,0.96))] p-4">
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#8b6615]">Link a device via QR code</h3>
                <p className="text-xs text-[#8b6615]">
                  This links a personal or business WhatsApp number by scanning a QR code, without needing Meta Business API credentials.
                </p>
              </div>

              {qrError && (
                <div className="flex items-start gap-3 rounded-[1.25rem] border border-[#ead8e1] bg-[#f8ecef] px-4 py-4">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#8b5a74]" />
                  <p className="text-xs text-[#8b5a74]">{qrError}</p>
                </div>
              )}

              <div>
                <label htmlFor="qr_bot_name" className={sectionTitleClass}>
                  Bot Name <span className="text-[#8b5a74]">*</span>
                </label>
                <input
                  type="text"
                  id="qr_bot_name"
                  value={qrBotName}
                  onChange={(e) => {
                    setQrBotName(e.target.value);
                    if (qrBotNameError) setQrBotNameError("");
                  }}
                  className={inputClass(!!qrBotNameError)}
                  placeholder="e.g., Support Bot"
                />
                {qrBotNameError && <p className="mt-1 text-xs text-[#8b5a74]">{qrBotNameError}</p>}
              </div>

              <div className="flex flex-col-reverse gap-3 border-t border-black/10 pt-4 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
                  className={secondaryButtonClass}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleStartQR}
                  disabled={startingQR}
                  className={primaryButtonClass}
                >
                  {startingQR ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-white"></div>
                      Starting...
                    </>
                  ) : (
                    <>
                      <Smartphone size={15} />
                      Generate QR Code
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {qrStep === 2 && (
            <div className="space-y-5">
              <div className="rounded-[1.35rem] border border-[#d7e6ea] bg-[#edf4f6] p-4">
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#486c77]">How to link your device</h3>
                <ol className="list-inside list-decimal space-y-1 text-xs text-[#486c77]">
                  <li>Open WhatsApp on your phone</li>
                  <li>Tap Menu (⋮) or Settings → Linked Devices</li>
                  <li>Tap “Link a Device” and scan the QR code below</li>
                </ol>
              </div>

              {qrError && (
                <div className="flex items-start gap-3 rounded-[1.25rem] border border-[#ead8e1] bg-[#f8ecef] px-4 py-4">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#8b5a74]" />
                  <p className="text-xs text-[#8b5a74]">{qrError}</p>
                </div>
              )}

              <div className="flex flex-col items-center rounded-[1.5rem] border border-black/10 bg-[#fcfaf5] py-8">
                {qrData ? (
                  <img
                    src={`data:image/png;base64,${qrData}`}
                    alt="WhatsApp QR Code"
                    className="h-56 w-56 rounded-[1.25rem] border border-black/10 bg-white p-2 shadow-[0_18px_40px_rgba(0,0,0,0.05)]"
                  />
                ) : (
                  <div className="flex h-56 w-56 items-center justify-center rounded-[1.25rem] border-2 border-dashed border-black/15 bg-white">
                    <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#171717]"></div>
                  </div>
                )}

                <div className="mt-4 flex items-center gap-2">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-[#ff5f8f]"></div>
                  <span className="text-xs text-gray-600">{qrStatus}</span>
                </div>
              </div>

              <div className="flex justify-center border-t border-black/10 pt-4">
                <button type="button" onClick={handleCancelQR} className={secondaryButtonClass}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {qrStep === 3 && (
            <div className="flex flex-col items-center space-y-4 py-8">
              <div className="rounded-full bg-[#e8f4ee] p-4">
                <CheckCircle className="text-[#2d8b69]" size={40} />
              </div>
              <h2 className="text-lg font-semibold text-gray-900">Device Linked!</h2>
              <p className="text-sm text-gray-600">
                Connected as <span className="font-medium text-gray-900">{connectedPhone}</span>
              </p>
              <button
                type="button"
                onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
                className={primaryButtonClass}
              >
                Go to Messaging Bots
              </button>
            </div>
          )}
        </AgentPagePanel>
      )}
    </AgentPageShell>
  );
}
