"use client";

import { useState } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import { Save, AlertCircle, CheckCircle, Copy, Globe } from "lucide-react";
import { createAgentDomain, getDNSRecords } from "@/lib/api/agent-domains";
import { AgentDomainCreate, AgentDomain, DNSRecordsResponse } from "@/types/agent-domain";
import toast from "react-hot-toast";
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

export default function CreateDomainPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdDomain, setCreatedDomain] = useState<AgentDomain | null>(null);
  const [dnsRecords, setDnsRecords] = useState<DNSRecordsResponse | null>(null);
  const [formData, setFormData] = useState<AgentDomainCreate>({
    is_custom_domain: true,
    subdomain: "",
    domain: "",
  });

  const fieldClass =
    "w-full rounded-[1.1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint";
  const panelClass =
    "rounded-[1.9rem] border border-line bg-white p-6 shadow-soft sm:p-7";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const domain = await createAgentDomain(agentName, formData);
      setCreatedDomain(domain);
      
      // Fetch DNS records to get the actual platform domain
      const records = await getDNSRecords(agentName, domain.id);
      setDnsRecords(records);
      
      toast.success("Domain created successfully!");
    } catch (err: any) {
      console.error("Failed to create domain:", err);
      setError(extractErrorMessage(err, err.message || "Failed to create domain"))
      toast.error("Failed to create domain");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  // Show DNS instructions after successful creation
  if (createdDomain && dnsRecords) {
    const fullDomain = createdDomain.subdomain 
      ? `${createdDomain.subdomain}.${createdDomain.domain}`
      : createdDomain.domain;

    // Find the CNAME record from the DNS records
    const cnameRecord = dnsRecords.records.find(record => record.type === 'CNAME');
    const platformDomain = dnsRecords.platform_domain;

    return (
      <AgentPageShell
        agentName={agentName}
        title="Domain Created Successfully"
        description="Configure DNS to activate your custom domain."
        icon={CheckCircle}
        badge="Custom Domain"
        maxWidthClassName="max-w-5xl"
        actions={
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => router.push(`/agents/${agentName}/domains`)}
              className="rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              Go to Domains
            </button>
            <button
              onClick={() => router.push(`/agents/${agentName}/domains/${createdDomain.id}/edit`)}
              className="rounded-[1rem] border border-black/10 bg-white/85 px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:bg-white hover:text-ink"
            >
              Customize Chat Interface
            </button>
          </div>
        }
      >
          <div className="space-y-5">
            {/* Domain Info */}
            <div className={panelClass}>
              <h2 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
                <Globe className="w-4 h-4 text-leaf" />
                Your Domain
              </h2>
              <div className="flex items-center gap-3 rounded-[1rem] border border-leaf-wash bg-cream p-3">
                <div className="flex-1">
                  <p className="mb-1 text-xs text-forest">Domain</p>
                  <p className="text-base font-mono font-semibold text-ink">{fullDomain}</p>
                </div>
                <button
                  onClick={() => copyToClipboard(fullDomain)}
                  className="rounded-[0.9rem] p-2 transition-colors hover:bg-leaf-wash"
                  title="Copy domain"
                >
                  <Copy className="w-4 h-4 text-forest" />
                </button>
              </div>
            </div>

            {/* DNS Configuration Steps */}
            <div className={panelClass}>
              <h2 className="text-base font-semibold text-ink mb-5">Setup Instructions</h2>
              
              <div className="space-y-5">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blush-wash text-leaf rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    1
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">Add DNS Record</h3>
                    <p className="text-xs text-ink-soft mb-2">
                      Log in to your domain provider (e.g., GoDaddy, Namecheap, Cloudflare) and add the following DNS record:
                    </p>
                    <div className="rounded-[1rem] border border-line bg-cream p-3">
                      <div className="grid grid-cols-3 gap-3 text-xs mb-2">
                        <div>
                          <p className="text-ink-mute mb-1 text-xs">Type</p>
                          <p className="font-mono font-semibold text-ink text-sm">CNAME</p>
                        </div>
                        <div>
                          <p className="text-ink-mute mb-1 text-xs">Name</p>
                          <p className="font-mono font-semibold text-ink text-sm">{cnameRecord?.name || createdDomain.subdomain || "@"}</p>
                        </div>
                        <div>
                          <p className="text-ink-mute mb-1 text-xs">Value</p>
                          <p className="font-mono font-semibold text-ink text-sm">{cnameRecord?.value || platformDomain}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(`${cnameRecord?.name || createdDomain.subdomain || "@"} CNAME ${cnameRecord?.value || platformDomain}`)}
                        className="flex items-center gap-1.5 text-xs font-medium text-forest hover:text-forest"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        Copy DNS record
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blush-wash text-leaf rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    2
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">Wait for DNS Propagation</h3>
                    <p className="text-xs text-ink-soft">
                      DNS changes typically take 5-10 minutes to propagate, but can take up to 48 hours in some cases.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blush-wash text-leaf rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    3
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">Verify Domain</h3>
                    <p className="text-xs text-ink-soft">
                      Once DNS propagates, return to the domains page and click "Verify" to activate your domain.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-blush-wash text-leaf rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    4
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">Customize Chat Interface</h3>
                    <p className="text-xs text-ink-soft">
                      After verification, you can customize the chat interface with your branding and colors.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Important Notes */}
            <div className="rounded-[1rem] border border-tan bg-paper p-4 shadow-sm">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gold">
                <AlertCircle className="w-4 h-4" />
                Important Notes
              </h3>
              <ul className="space-y-1.5 text-xs text-gold">
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 text-gold">•</span>
                  <span>SSL certificates will be automatically provisioned once the domain is verified</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 text-gold">•</span>
                  <span>Make sure to use the exact DNS record values provided above</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 text-gold">•</span>
                  <span>If using Cloudflare, disable the proxy (orange cloud) for the DNS record</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5 text-gold">•</span>
                  <span>Contact support if you encounter any issues with DNS configuration</span>
                </li>
              </ul>
            </div>
          </div>
      </AgentPageShell>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Add Custom Domain"
      description="Configure a custom domain for your agent's chat interface."
      icon={Globe}
      badge="Custom Domain"
      maxWidthClassName="max-w-5xl"
      actions={
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            form="create-domain-form"
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {loading ? "Creating…" : "Create Domain"}
          </button>
          <button
            type="button"
            onClick={() => router.push(`/agents/${agentName}/domains`)}
            className="rounded-[1rem] border border-black/10 bg-white/85 px-5 py-3 text-sm font-semibold text-ink-soft transition-colors hover:bg-white hover:text-ink"
          >
            Cancel
          </button>
        </div>
      }
    >

        {/* Error Message */}
        {error && (
          <div className="mb-5 flex items-start gap-2 rounded-[1rem] border border-blush-wash bg-white p-3">
            <AlertCircle className="w-4 h-4 text-wine flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-wine text-sm">Error</h3>
              <p className="text-wine text-xs mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Form */}
        <form id="create-domain-form" onSubmit={handleSubmit}>
          <div className={panelClass + " space-y-5"}>
            {/* Domain Type */}
            <div>
              <label className="block text-sm font-semibold text-ink-soft mb-2">
                Domain Type
              </label>
              <div className="space-y-2">
                <label className="flex items-start gap-3 rounded-[1rem] border-2 border-line bg-white/70 p-4 cursor-pointer transition-colors hover:border-tan hover:bg-paper">
                  <input
                    type="radio"
                    checked={formData.is_custom_domain}
                    onChange={() =>
                      setFormData({ ...formData, is_custom_domain: true })
                    }
                    className="mt-0.5 h-4 w-4 text-leaf focus:ring-mint"
                  />
                  <div className="flex-1">
                    <span className="font-medium text-ink block mb-0.5 text-sm">
                      Custom Domain
                    </span>
                    <span className="text-xs text-ink-soft">
                      Use your own domain (e.g., chat.yourdomain.com)
                    </span>
                  </div>
                </label>
                <label className="flex items-start gap-3 rounded-[1rem] border-2 border-line bg-white/70 p-4 cursor-pointer transition-colors hover:border-tan hover:bg-paper">
                  <input
                    type="radio"
                    checked={!formData.is_custom_domain}
                    onChange={() =>
                      setFormData({ ...formData, is_custom_domain: false })
                    }
                    className="mt-0.5 h-4 w-4 text-leaf focus:ring-mint"
                  />
                  <div className="flex-1">
                    <span className="font-medium text-ink block mb-0.5 text-sm">
                      Platform Subdomain
                    </span>
                    <span className="text-xs text-ink-soft">
                      Use a subdomain on our platform (e.g., yourname.platform.com)
                    </span>
                  </div>
                </label>
              </div>
            </div>

            {/* Custom Domain Fields */}
            {formData.is_custom_domain ? (
              <>
                <div>
                  <label
                    htmlFor="domain"
                    className="block text-xs font-medium text-ink-soft mb-2"
                  >
                    Domain Name *
                  </label>
                  <input
                    type="text"
                    id="domain"
                    value={formData.domain || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, domain: e.target.value })
                    }
                    placeholder="yourdomain.com"
                    className={fieldClass}
                    required
                  />
                  <p className="text-xs text-ink-mute mt-1">
                    Enter your root domain (e.g., yourdomain.com)
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="subdomain"
                    className="block text-xs font-medium text-ink-soft mb-2"
                  >
                    Platform Subdomain *
                  </label>
                  <input
                    type="text"
                    id="subdomain"
                    value={formData.subdomain || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, subdomain: e.target.value })
                    }
                    placeholder="myagent"
                    className={fieldClass}
                    required
                  />
                  <p className="text-xs text-ink-mute mt-1">
                    Required: A platform subdomain is always needed for fallback access and DNS mapping (e.g., myagent.synkora.ai)
                  </p>
                </div>
              </>
            ) : (
              <div>
                <label
                  htmlFor="subdomain"
                  className="block text-xs font-medium text-ink-soft mb-2"
                >
                  Subdomain *
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    id="subdomain"
                    value={formData.subdomain || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, subdomain: e.target.value })
                    }
                    placeholder="yourname"
                    className={`flex-1 ${fieldClass}`}
                    required
                  />
                  <span className="text-ink-soft text-sm font-medium">.platform.com</span>
                </div>
                <p className="text-xs text-ink-mute mt-1">
                  Choose a unique subdomain for your agent
                </p>
              </div>
            )}

            {/* Info Box */}
            <div className="rounded-[1rem] border border-tan bg-paper p-4">
              <h3 className="mb-2 text-xs font-semibold text-gold">Next Steps</h3>
              <ul className="space-y-1 text-xs text-gold">
                <li className="flex items-start gap-2">
                  <span className="mt-0.5">•</span>
                  <span>After creating the domain, you'll receive DNS configuration instructions</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5">•</span>
                  <span>Add the required DNS records to your domain provider</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5">•</span>
                  <span>DNS verification typically takes 5-10 minutes</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-0.5">•</span>
                  <span>Once verified, you can customize the chat interface</span>
                </li>
              </ul>
            </div>
          </div>
        </form>
    </AgentPageShell>
  );
}
