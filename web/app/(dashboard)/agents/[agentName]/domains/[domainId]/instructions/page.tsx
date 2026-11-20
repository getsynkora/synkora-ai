"use client";

import { useState, useEffect } from "react";
import { extractErrorMessage } from '@/lib/api/error'
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle,
  Copy,
  ExternalLink,
  Shield,
  AlertCircle,
  Globe,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { AgentDomain, DNSRecordsResponse } from "@/types/agent-domain";
import toast from "react-hot-toast";

export default function DomainInstructionsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;
  const domainId = params.domainId as string;

  const [domain, setDomain] = useState<AgentDomain | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    fetchDomain();
  }, [domainId]);

  useEffect(() => {
    if (domain && domain.is_custom_domain && !domain.is_verified) {
      fetchDNSRecords();
    }
  }, [domain]);

  const fetchDomain = async () => {
    try {
      setLoading(true);
      setError(null);

      const domainData = await apiClient.request(
        "GET",
        `/api/v1/agents/${agentName}/domains/${domainId}`
      );

      setDomain(domainData);
    } catch (err: any) {
      console.error("Failed to fetch domain:", err);
      setError(extractErrorMessage(err, "Failed to load domain"))
    } finally {
      setLoading(false);
    }
  };

  const [dnsRecords, setDnsRecords] = useState<any[]>([]);
  
  const fetchDNSRecords = async () => {
    try {
      const dnsData: DNSRecordsResponse = await apiClient.request(
        "GET",
        `/api/v1/agents/${agentName}/domains/${domainId}/dns-records`
      );
      
      setDnsRecords(dnsData.records || []);
    } catch (err: any) {
      console.error("Failed to fetch DNS records:", err);
      // Don't set error - this is not critical, we can fallback to showing placeholder
    }
  };

  const handleVerifyDomain = async () => {
    try {
      setVerifying(true);
      const result = await apiClient.request(
        "POST",
        `/api/v1/agents/${agentName}/domains/${domainId}/verify`
      );

      if (result.is_verified) {
        toast.success("Domain verified successfully!");
        await fetchDomain();
      } else {
        toast.error(
          result.message ||
            "Domain verification failed. Please check your DNS configuration."
        );
      }
    } catch (err: any) {
      toast.error(extractErrorMessage(err, "Failed to verify domain"))
    } finally {
      setVerifying(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-warn mx-auto"></div>
          <p className="mt-4 text-ink-soft">Loading domain…</p>
        </div>
      </div>
    );
  }

  if (error || !domain) {
    return (
      <div className="min-h-screen p-4 md:p-8">
        <div className="max-w-3xl mx-auto">
          <div className="mb-6 p-4 bg-blush-wash border border-blush rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-danger flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-wine">Error</h3>
              <p className="text-danger text-sm mt-1">
                {error || "Domain not found"}
              </p>
            </div>
          </div>
          <button
            onClick={() => router.push(`/agents/${agentName}/domains`)}
            className="flex items-center gap-2 text-warn hover:text-gold transition-colors text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Domains
          </button>
        </div>
      </div>
    );
  }

  // For custom domains: domain.domain is the custom domain (e.g., rajumazumder.com)
  // For platform domains: domain.subdomain + platform domain (e.g., test.synkora.ai)
  const platformSubdomain = domain.subdomain;
  
  // Display domain based on type
  const displayDomain = domain.is_custom_domain 
    ? domain.domain  // Show custom domain: rajumazumder.com
    : (domain.subdomain ? `${domain.subdomain}.synkora.ai` : 'synkora.ai'); // Show platform subdomain
  
  const fullDomain = displayDomain;

  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push(`/agents/${agentName}/domains`)}
            className="flex items-center gap-2 text-warn hover:text-gold mb-4 transition-colors text-sm font-medium"
          >
            <ArrowLeft size={16} />
            Back to Domains
          </button>
          <div className="flex items-center gap-3 mb-4">
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center shadow-sm ${
                domain.is_verified
                  ? "bg-leaf-wash"
                  : "bg-sand-deep"
              }`}
            >
              {domain.is_verified ? (
                <CheckCircle className="w-6 h-6 text-leaf" />
              ) : (
                <AlertCircle className="w-6 h-6 text-warn" />
              )}
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">
                DNS Configuration
              </h1>
              <p className="text-ink-soft mt-0.5 text-sm">
                {domain.is_verified
                  ? "Your domain is verified and active"
                  : "Configure DNS to activate your custom domain"}
              </p>
            </div>
          </div>
        </div>

        {/* Domain Info */}
        <div className="space-y-5">
          <div className="bg-white rounded-xl shadow-sm border border-line p-5">
            <h2 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4 text-warn" />
              Your Domain
            </h2>
            <div className="flex items-center gap-3 p-3 bg-sand-deep border border-honey rounded-lg">
              <div className="flex-1">
                <p className="text-xs text-gold mb-1">Domain</p>
                <p className="text-base font-mono font-semibold text-ink">
                  {fullDomain}
                </p>
              </div>
              <button
                onClick={() => copyToClipboard(fullDomain)}
                className="p-2 hover:bg-sand-deep rounded-lg transition-colors"
                title="Copy domain"
              >
                <Copy className="w-4 h-4 text-warn" />
              </button>
              {domain.is_verified && (
                <a
                  href={`https://${fullDomain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 hover:bg-sand-deep rounded-lg transition-colors"
                  title="Visit domain"
                >
                  <ExternalLink className="w-4 h-4 text-warn" />
                </a>
              )}
            </div>
          </div>

          {/* Domain Mapping Info for Custom Domains */}
          {domain.is_custom_domain && platformSubdomain && (
            <div className="bg-sky-wash border border-sky-wash rounded-xl shadow-sm p-4">
              <h3 className="font-semibold text-azure text-sm mb-2 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                How It Works
              </h3>
              <p className="text-xs text-azure mb-2">
                Your custom domain <span className="font-mono font-semibold">{domain.domain}</span> will point to your agent hosted at <span className="font-mono font-semibold">{platformSubdomain}.synkora.ai</span>.
              </p>
              <p className="text-xs text-azure">
                This means visitors can access your agent through your own domain while it's actually served from our platform infrastructure.
              </p>
            </div>
          )}

          {/* DNS Configuration Steps */}
          {!domain.is_verified && (
            <div className="bg-white rounded-xl shadow-sm border border-line p-5">
              <h2 className="text-base font-semibold text-ink mb-5">Setup Instructions</h2>

              <div className="space-y-5">
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-sand-deep text-gold rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    1
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">
                      Add DNS Records
                    </h3>
                    <p className="text-xs text-ink-soft mb-2">
                      Log in to your domain provider (e.g., GoDaddy, Namecheap,
                      Cloudflare) and add the following TWO DNS records:
                    </p>
                    
                    {dnsRecords.length > 0 ? (
                      <div className="space-y-3">
                        {dnsRecords.map((record, index) => (
                          <div key={index} className="bg-cream border border-line rounded-lg p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <div className="px-2 py-1 bg-sand-deep text-gold text-xs font-semibold rounded">
                                Record {index + 1}
                              </div>
                              <span className="text-xs text-ink-mute">{record.purpose}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-3 text-xs mb-2">
                              <div>
                                <p className="text-ink-mute mb-1 text-xs">Type</p>
                                <p className="font-mono font-semibold text-ink text-sm">{record.type}</p>
                              </div>
                              <div>
                                <p className="text-ink-mute mb-1 text-xs">Name</p>
                                <p className="font-mono font-semibold text-ink text-sm break-all">
                                  {record.name}
                                </p>
                              </div>
                              <div>
                                <p className="text-ink-mute mb-1 text-xs">Value</p>
                                <p className="font-mono font-semibold text-ink text-sm break-all">
                                  {record.value}
                                </p>
                              </div>
                            </div>
                            <button
                              onClick={() => copyToClipboard(`${record.name} ${record.type} ${record.value}`)}
                              className="text-xs text-warn hover:text-gold flex items-center gap-1.5 font-medium"
                            >
                              <Copy className="w-3.5 h-3.5" />
                              Copy record
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="bg-cream border border-line rounded-lg p-4">
                        <p className="text-sm text-ink-mute">Loading DNS records…</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-sand-deep text-gold rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    2
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">
                      Wait for DNS Propagation
                    </h3>
                    <p className="text-xs text-ink-soft">
                      DNS changes typically take 5-10 minutes to propagate, but
                      can take up to 48 hours in some cases.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-sand-deep text-gold rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    3
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">
                      Verify Domain
                    </h3>
                    <p className="text-xs text-ink-soft mb-3">
                      Once DNS propagates, click the verify button below to
                      activate your domain.
                    </p>
                    <button
                      onClick={handleVerifyDomain}
                      disabled={verifying}
                      className="flex items-center gap-2 px-5 py-2 text-sm bg-leaf text-white rounded-lg hover:bg-forest transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm font-medium"
                    >
                      <Shield className="w-4 h-4" />
                      {verifying ? "Verifying…" : "Verify Domain"}
                    </button>
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-sand-deep text-gold rounded-full flex items-center justify-center font-semibold text-sm shadow-sm">
                    4
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-ink mb-1.5 text-sm">
                      Customize Chat Interface
                    </h3>
                    <p className="text-xs text-ink-soft">
                      After verification, you can customize the chat interface
                      with your branding and colors.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Verified Status */}
          {domain.is_verified && (
            <div className="bg-leaf-wash border border-mint rounded-xl shadow-sm p-5">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-leaf flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-semibold text-forest mb-1.5 text-sm">
                    Domain Verified Successfully!
                  </h3>
                  <p className="text-forest text-xs mb-3">
                    Your domain is now active and ready to use. You can customize
                    the chat interface or visit your domain.
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() =>
                        router.push(`/agents/${agentName}/chat-customization`)
                      }
                      className="px-5 py-2 text-sm bg-leaf text-white rounded-lg hover:bg-forest transition-colors shadow-sm font-medium"
                    >
                      Customize Chat Interface
                    </button>
                    <a
                      href={`https://${fullDomain}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-5 py-2 text-sm text-forest bg-white border border-mint rounded-lg hover:bg-leaf-wash transition-colors shadow-sm font-medium"
                    >
                      <ExternalLink className="w-4 h-4" />
                      Visit Domain
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* DNS Configuration Info */}
          {domain.subdomain && (
            <div className="bg-sky-wash border border-sky-wash rounded-xl shadow-sm p-4">
              <h3 className="font-semibold text-azure text-sm mb-2 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Domain Configuration
              </h3>
              <p className="text-xs text-azure mb-2">
                Your agent is currently configured to be served from <span className="font-mono font-semibold">{fullDomain}</span>.
              </p>
              <p className="text-xs text-azure">
                If you want to serve your agent from the root domain (<span className="font-mono font-semibold">{domain.domain}</span>) instead, 
                please <button 
                  onClick={() => router.push(`/agents/${agentName}/domains/${domainId}/edit`)}
                  className="text-azure hover:text-azure underline font-medium"
                >edit the domain settings</button> and leave the subdomain field empty.
              </p>
            </div>
          )}

          {/* Important Notes */}
          <div className="bg-sand-deep border border-honey rounded-xl shadow-sm p-4">
            <h3 className="font-semibold text-gold text-sm mb-2 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Important Notes
            </h3>
            <ul className="space-y-1.5 text-xs text-gold">
              <li className="flex items-start gap-2">
                <span className="text-warn mt-0.5">•</span>
                <span>
                  SSL certificates will be automatically provisioned once the domain
                  is verified
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-warn mt-0.5">•</span>
                <span>
                  Make sure to use the exact DNS record values provided above
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-warn mt-0.5">•</span>
                <span>
                  If using Cloudflare, disable the proxy (orange cloud) for the DNS
                  record
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-warn mt-0.5">•</span>
                <span>
                  Contact support if you encounter any issues with DNS configuration
                </span>
              </li>
            </ul>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => router.push(`/agents/${agentName}/domains`)}
              className="px-5 py-2 text-sm text-ink-soft bg-white border border-taupe rounded-lg hover:bg-white hover:border-honey transition-colors shadow-sm font-medium"
            >
              Back to Domains
            </button>
            {domain.is_verified && (
              <button
                onClick={() =>
                  router.push(`/agents/${agentName}/chat-customization`)
                }
                className="px-5 py-2 text-sm bg-warn text-white rounded-lg hover:from-warn hover:to-warn transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm font-medium"
              >
                Customize Chat Interface
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
