"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, AlertCircle, Users } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { teamsBotsApi } from "@/lib/api/messaging-bots";
import type { CreateTeamsBotRequest } from "@/types/messaging-bots";

export default function CreateTeamsBotPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<CreateTeamsBotRequest>({
    agent_id: "",
    bot_name: "",
    app_id: "",
    app_password: "",
    bot_id: "",
    webhook_url: "",
    welcome_message: "",
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const loadAgent = async () => {
      try {
        const agent = await apiClient.getAgent(agentName);
        setFormData((prev) => ({ ...prev, agent_id: agent.id }));
      } catch (err: any) {
        console.error("Error loading agent:", err);
        setError(err.response?.data?.message || "Failed to load agent");
      } finally {
        setLoading(false);
      }
    };
    loadAgent();
  }, [agentName]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.bot_name.trim()) {
      newErrors.bot_name = "Bot name is required";
    }

    if (!formData.app_id.trim()) {
      newErrors.app_id = "App ID is required";
    }

    if (!formData.app_password.trim()) {
      newErrors.app_password = "App password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await teamsBotsApi.createBot(formData);
      router.push(`/agents/${agentName}/messaging-bots`);
    } catch (err: any) {
      console.error("Error creating Teams bot:", err);
      setError(err.response?.data?.message || "Failed to create Teams bot");
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: keyof CreateTeamsBotRequest, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev: Record<string, string>) => ({ ...prev, [field]: "" }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-danger"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <button
            onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
            className="flex items-center text-leaf hover:text-leaf mb-4 text-sm font-medium"
          >
            <ArrowLeft size={16} className="mr-2" />
            Back to Messaging Bots
          </button>
          <div className="flex items-center gap-3">
            <div className="bg-sky-wash p-2.5 rounded-lg">
              <Users className="text-azure" size={20} />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Create Teams Bot</h1>
              <p className="text-ink-soft mt-0.5 text-sm">Connect your agent to Microsoft Teams</p>
            </div>
          </div>
        </div>

        <div className="bg-sky-wash border border-sky-wash rounded-lg p-4 mb-5">
          <h3 className="text-xs font-medium text-azure mb-2">Before you begin</h3>
          <ul className="text-xs text-azure space-y-1 list-disc list-inside">
            <li>Register your bot in Azure Portal</li>
            <li>Create a Bot Channels Registration</li>
            <li>Get your App ID and generate an App Password</li>
            <li>Configure the messaging endpoint</li>
          </ul>
          <a
            href="https://dev.botframework.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-azure hover:text-azure font-medium mt-2 inline-block"
          >
            View Setup Guide
          </a>
        </div>

        {error && (
          <div className="bg-blush-wash border border-blush rounded-lg p-3 mb-5 flex items-start">
            <AlertCircle className="text-danger mr-2 flex-shrink-0 mt-0.5" size={16} />
            <div>
              <h3 className="text-xs font-medium text-wine">Error</h3>
              <p className="text-xs text-danger mt-1">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-line p-5 space-y-5">
          <div>
            <label htmlFor="bot_name" className="block text-xs font-medium text-ink-soft mb-2">
              Bot Name <span className="text-leaf">*</span>
            </label>
            <input
              type="text"
              id="bot_name"
              value={formData.bot_name}
              onChange={(e) => handleChange("bot_name", e.target.value)}
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent ${
                errors.bot_name ? "border-ink" : "border-taupe"
              }`}
              placeholder="e.g., Support Bot"
            />
            {errors.bot_name && <p className="mt-1 text-xs text-danger">{errors.bot_name}</p>}
          </div>

          <div>
            <label htmlFor="app_id" className="block text-xs font-medium text-ink-soft mb-2">
              App ID <span className="text-leaf">*</span>
            </label>
            <input
              type="text"
              id="app_id"
              value={formData.app_id}
              onChange={(e) => handleChange("app_id", e.target.value)}
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent ${
                errors.app_id ? "border-ink" : "border-taupe"
              }`}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            />
            {errors.app_id && <p className="mt-1 text-xs text-danger">{errors.app_id}</p>}
            <p className="mt-1 text-xs text-ink-mute">
              Find this in your Azure Bot Channels Registration
            </p>
          </div>

          <div>
            <label htmlFor="app_password" className="block text-xs font-medium text-ink-soft mb-2">
              App Password <span className="text-leaf">*</span>
            </label>
            <input
              type="password"
              id="app_password"
              value={formData.app_password}
              onChange={(e) => handleChange("app_password", e.target.value)}
              className={`w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent ${
                errors.app_password ? "border-ink" : "border-taupe"
              }`}
              placeholder="App password"
            />
            {errors.app_password && (
              <p className="mt-1 text-xs text-danger">{errors.app_password}</p>
            )}
            <p className="mt-1 text-xs text-ink-mute">
              Generate from Azure Portal (will be encrypted)
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t">
            <button
              type="button"
              onClick={() => router.push(`/agents/${agentName}/messaging-bots`)}
              className="px-5 py-2 text-sm border border-taupe rounded-lg text-ink-soft hover:bg-white hover:border-blush transition-colors font-medium"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 text-sm bg-azure text-white rounded-lg hover:bg-azure transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium shadow-sm"
            >
              {submitting ? (
                <>
                  <div className="motion-safe:animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Creating...
                </>
              ) : (
                "Create Teams Bot"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
