"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import {
  Plus,
  Trash2,
  Edit,
  Globe,
  CheckCircle,
  XCircle,
  AlertCircle,
  ExternalLink,
  Copy,
  Shield,
  FileText,
  ArrowLeft,
  Globe2,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { getDNSRecords } from "@/lib/api/agent-domains";
import { AgentDomain } from "@/types/agent-domain";
import toast from "react-hot-toast";
import AgentPageShell from '@/components/agents/AgentPageShell'

export default function AgentDomainsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [domains, setDomains] = useState<AgentDomain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platformDomain, setPlatformDomain] = useState<string>("your-platform.com");

  useEffect(() => {
    fetchDomains();
  }, [agentName]);

  const fetchDomains = async () => {
    try {
      setLoading(true);
      setError(null);

      const domains = await apiClient.request(
        "GET",
        `/api/v1/agents/${agentName}/domains`
      );

      const domainsList = Array.isArray(domains) ? domains : [];
      setDomains(domainsList);

      // Fetch platform domain from the first domain's DNS records
      if (domainsList.length > 0) {
        try {
          const dnsRecords = await getDNSRecords(agentName, domainsList[0].id);
          setPlatformDomain(dnsRecords.platform_domain);
        } catch (err) {
          console.error("Failed to fetch DNS records:", err);
          // Keep the default platform domain if fetch fails
        }
      }
    } catch (err: any) {
      console.error("Failed to fetch domains:", err);
      setError(extractErrorMessage(err, "Failed to load domains"))
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDomain = async (domainId: string) => {
    if (!confirm("Are you sure you want to delete this domain?")) {
      return;
    }

    try {
      await apiClient.request("DELETE", `/api/v1/agents/${agentName}/domains/${domainId}`);
      toast.success("Domain deleted successfully");
      await fetchDomains();
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to delete domain"))
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  const handleVerifyDomain = async (domainId: string) => {
    try {
      const result = await apiClient.request(
        "POST",
        `/api/v1/agents/${agentName}/domains/${domainId}/verify`
      );
      
      if (result.is_verified) {
        toast.success("Domain verified successfully!");
        await fetchDomains();
      } else {
        toast.error(result.message || "Domain verification failed. Please check your DNS configuration.");
      }
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to verify domain"))
    }
  };

  const handleViewInstructions = (domainId: string) => {
    router.push(`/agents/${agentName}/domains/${domainId}/instructions`);
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      active: { color: "bg-emerald-100 text-emerald-800", icon: CheckCircle },
      pending: { color: "bg-yellow-100 text-yellow-800", icon: AlertCircle },
      failed: { color: "bg-red-100 text-red-800", icon: XCircle },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
    const Icon = config.icon;

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full flex items-center gap-1 ${config.color}`}>
        <Icon className="w-3 h-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 text-sm">Loading domains...</p>
        </div>
      </div>
    );
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Custom Domains"
      description="Configure custom domains for your agent's chat interface."
      icon={Globe2}
      badge="Branded Access"
      maxWidthClassName="max-w-[90rem]"
      actions={
        <button
          onClick={() => router.push(`/agents/${agentName}/domains/create`)}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus className="w-4 h-4" />
          Add Domain
        </button>
      }
    >

        {/* Error Message */}
        {error && (
          <div className="mb-5 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-900 text-sm">Error</h3>
              <p className="text-red-700 text-xs mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Domains List */}
        {domains.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10 text-center">
            <Globe className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h3 className="text-base font-semibold text-gray-900 mb-2">
              No custom domains yet
            </h3>
            <p className="text-gray-600 text-sm mb-5 max-w-md mx-auto">
              Add a custom domain to provide a branded chat experience for your users
            </p>
            <button
              onClick={() => router.push(`/agents/${agentName}/domains/create`)}
              className="inline-flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all shadow-sm text-xs font-medium"
            >
              <Plus className="w-4 h-4" />
              Add Domain
            </button>
          </div>
        ) : (
          <div className="grid gap-3">
            {domains.map((domain) => (
              <div
                key={domain.id}
                className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md hover:border-red-300 transition-all overflow-hidden"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Globe className="w-4 h-4 text-red-600" />
                        <h3 className="text-base font-semibold text-gray-900">
                          {domain.domain}
                        </h3>
                        {getStatusBadge(domain.status || 'pending')}
                      </div>

                      <div className="space-y-1.5 text-xs text-gray-600">
                        {domain.subdomain && (
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500">Subdomain:</span>
                            <span className="font-medium">{domain.subdomain}</span>
                          </div>
                        )}

                        {domain.is_verified && (
                          <div className="flex items-center gap-2 text-emerald-600">
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span className="font-medium">Domain Verified</span>
                          </div>
                        )}

                        {domain.chat_page_config && (
                          <div className="flex items-center gap-2 text-red-600">
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>Custom chat interface configured</span>
                          </div>
                        )}

                        <div className="flex items-center gap-2 text-xs text-gray-500 mt-2">
                          <span>
                            Created: {new Date(domain.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleViewInstructions(domain.id)}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="View DNS instructions"
                      >
                        <FileText className="w-4 h-4" />
                      </button>

                      {(domain.status === "pending" || domain.status === "failed") && (
                        <button
                          onClick={() => handleVerifyDomain(domain.id)}
                          className="p-2 text-gray-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                          title="Verify domain"
                        >
                          <Shield className="w-4 h-4" />
                        </button>
                      )}

                      {domain.status === "active" && (
                        <a
                          href={`https://${domain.subdomain ? domain.subdomain + "." : ""}${domain.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Visit domain"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}

                      <button
                        onClick={() =>
                          router.push(`/agents/${agentName}/domains/${domain.id}/edit`)
                        }
                          className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Edit domain"
                      >
                        <Edit className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => handleDeleteDomain(domain.id)}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete domain"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* DNS Instructions */}
                  {domain.status === "pending" && (
                    <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <h4 className="font-medium text-yellow-900 text-xs mb-2 flex items-center gap-2">
                        <AlertCircle className="w-3.5 h-3.5" />
                        DNS Configuration Required
                      </h4>
                      <p className="text-yellow-800 text-xs mb-2">
                        Add the following DNS records to your domain:
                      </p>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-xs font-mono bg-white p-2.5 rounded border border-yellow-300">
                          <span className="text-yellow-900 flex-1">
                            CNAME: {domain.subdomain || "@"} → {platformDomain}
                          </span>
                          <button
                            onClick={() =>
                              copyToClipboard(
                                `${domain.subdomain || "@"} CNAME ${platformDomain}`
                              )
                            }
                            className="p-1 hover:bg-yellow-100 rounded transition-colors"
                            title="Copy DNS record"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="mt-5 bg-red-50 border border-red-200 rounded-lg shadow-sm p-5">
          <h3 className="font-semibold text-red-900 text-sm mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            About Custom Domains
          </h3>
          <ul className="space-y-2 text-xs text-red-800">
            <li className="flex items-start gap-2">
              <span className="text-red-600 mt-0.5">•</span>
              <span>Custom domains allow you to host your agent's chat interface on your own domain</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-600 mt-0.5">•</span>
              <span>Configure DNS records to point your domain to our platform</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-600 mt-0.5">•</span>
              <span>SSL certificates are automatically provisioned for secure connections</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-600 mt-0.5">•</span>
              <span>Customize the chat interface with your branding and colors</span>
            </li>
          </ul>
        </div>
    </AgentPageShell>
  );
}
