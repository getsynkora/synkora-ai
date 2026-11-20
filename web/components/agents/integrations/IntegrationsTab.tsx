'use client'

import { useState } from 'react'
import { Check, Copy, ExternalLink, Plus, X } from 'lucide-react'

interface A2ASkill {
  id: string
  name: string
  description: string
}

interface IntegrationsConfig {
  mcp_server_enabled: boolean
  mcp_server_name: string
  mcp_server_description: string
  mcp_server_public: boolean
  a2a_enabled: boolean
  a2a_public: boolean
  a2a_name: string
  a2a_skills: A2ASkill[]
}

interface IntegrationsTabProps {
  agentId: string
  agentName: string
  agentDescription: string
  config: IntegrationsConfig
  setConfig: (config: IntegrationsConfig) => void
}

const DEFAULT_CONFIG: IntegrationsConfig = {
  mcp_server_enabled: false,
  mcp_server_name: '',
  mcp_server_description: '',
  mcp_server_public: false,
  a2a_enabled: false,
  a2a_public: false,
  a2a_name: '',
  a2a_skills: [],
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="ml-2 p-1.5 rounded-md hover:bg-sand transition-colors text-ink-mute hover:text-ink-soft flex-shrink-0"
      title="Copy to clipboard"
    >
      {copied ? <Check size={14} className="text-leaf" /> : <Copy size={14} />}
    </button>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  description?: string
}) {
  return (
    <div className="flex items-center justify-between p-4 bg-cream rounded-lg border border-line">
      <div>
        <p className="text-sm font-medium text-ink">{label}</p>
        {description && <p className="text-xs text-ink-mute mt-0.5">{description}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
          checked ? 'bg-primary-600' : 'bg-line'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform motion-reduce:transition-none ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )
}

function CodeBlock({ code, language = 'json' }: { code: string; language?: string }) {
  return (
    <div className="relative">
      <pre className={`bg-ink text-sand rounded-lg p-4 text-xs overflow-x-auto font-mono language-${language}`}>
        {code}
      </pre>
      <div className="absolute top-2 right-2">
        <CopyButton value={code} />
      </div>
    </div>
  )
}

function EndpointRow({ label, url }: { label: string; url: string }) {
  return (
    <div className="flex items-center gap-2 p-3 bg-cream rounded-lg border border-line">
      <span className="text-xs font-medium text-ink-mute w-28 flex-shrink-0">{label}</span>
      <code className="text-xs text-ink font-mono flex-1 truncate">{url}</code>
      <CopyButton value={url} />
    </div>
  )
}

export default function IntegrationsTab({
  agentId,
  agentName,
  agentDescription,
  config,
  setConfig,
}: IntegrationsTabProps) {
  const cfg = { ...DEFAULT_CONFIG, ...config }
  const appUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

  const mcpEndpoint = `${appUrl}/api/mcp/${agentId}`
  const a2aEndpoint = `${appUrl}/api/a2a/agents/${agentId}`
  const agentCardUrl = `${a2aEndpoint}/.well-known/agent.json`

  const mcpCliConfig = JSON.stringify(
    {
      mcpServers: {
        [agentName]: {
          type: 'http',
          url: mcpEndpoint,
          headers: { Authorization: 'Bearer YOUR_API_KEY' },
        },
      },
    },
    null,
    2
  )

  const a2aPythonSnippet = `import httpx

# Get Agent Card
card = httpx.get("${agentCardUrl}").json()
print(card["name"], card["skills"])

# Send a message
resp = httpx.post(
    "${a2aEndpoint}",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Hello, agent!"}]
            }
        }
    }
)
result = resp.json()["result"]
print(result["artifacts"][0]["parts"][0]["text"])`

  // Skills management
  const [newSkillId, setNewSkillId] = useState('')
  const [newSkillName, setNewSkillName] = useState('')
  const [newSkillDesc, setNewSkillDesc] = useState('')

  const addSkill = () => {
    if (!newSkillId.trim() || !newSkillName.trim()) return
    const skill: A2ASkill = {
      id: newSkillId.trim().toLowerCase().replace(/\s+/g, '_'),
      name: newSkillName.trim(),
      description: newSkillDesc.trim(),
    }
    setConfig({ ...cfg, a2a_skills: [...cfg.a2a_skills, skill] })
    setNewSkillId('')
    setNewSkillName('')
    setNewSkillDesc('')
  }

  const removeSkill = (idx: number) => {
    setConfig({ ...cfg, a2a_skills: cfg.a2a_skills.filter((_, i) => i !== idx) })
  }

  return (
    <div className="space-y-10 max-w-3xl">

      {/* MCP Server Section */}
      <section>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-ink">MCP Server</h3>
          <p className="text-sm text-ink-soft mt-1">
            Expose this agent as an MCP server. Compatible with Claude Code CLI, Cursor, and any MCP client.
          </p>
        </div>

        <div className="space-y-4">
          <Toggle
            checked={cfg.mcp_server_enabled}
            onChange={(v) => setConfig({ ...cfg, mcp_server_enabled: v })}
            label="Enable MCP Server"
            description="Expose this agent via MCP Streamable HTTP (spec 2025-06-18)"
          />

          {cfg.mcp_server_enabled && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">
                    Display Name (optional)
                  </label>
                  <input
                    type="text"
                    value={cfg.mcp_server_name}
                    onChange={(e) => setConfig({ ...cfg, mcp_server_name: e.target.value })}
                    placeholder={agentName}
                    className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">
                    Description (optional)
                  </label>
                  <input
                    type="text"
                    value={cfg.mcp_server_description}
                    onChange={(e) => setConfig({ ...cfg, mcp_server_description: e.target.value })}
                    placeholder={agentDescription}
                    className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <EndpointRow label="MCP Endpoint" url={mcpEndpoint} />
              </div>

              <div className="bg-sky-wash border border-sky-wash rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-azure">Claude Code CLI config</h4>
                  <span className="text-xs text-azure">Add to ~/.claude.json</span>
                </div>
                <CodeBlock code={mcpCliConfig} />
              </div>

              <div className="bg-sand-deep border border-honey rounded-lg p-3">
                <p className="text-xs text-gold">
                  Generate an API key with <strong>mcp_server</strong> permission from
                  the <strong>API Keys</strong> section, then replace{' '}
                  <code className="bg-white px-1 rounded">YOUR_API_KEY</code> above.
                </p>
              </div>
            </>
          )}
        </div>
      </section>

      <hr className="border-line" />

      {/* A2A Protocol Section */}
      <section>
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-ink">A2A Protocol</h3>
          <p className="text-sm text-ink-soft mt-1">
            Expose this agent via the Google Agent-to-Agent (A2A) protocol for cross-framework agent communication.
          </p>
        </div>

        <div className="space-y-4">
          <Toggle
            checked={cfg.a2a_enabled}
            onChange={(v) => setConfig({ ...cfg, a2a_enabled: v })}
            label="Enable A2A Protocol"
            description="Allow other agents (LangGraph, AutoGen, remote Synkora) to call this agent"
          />

          {cfg.a2a_enabled && (
            <>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">
                  Display Name (optional)
                </label>
                <input
                  type="text"
                  value={cfg.a2a_name}
                  onChange={(e) => setConfig({ ...cfg, a2a_name: e.target.value })}
                  placeholder={agentName}
                  className="w-full px-3 py-2 text-sm border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <Toggle
                checked={cfg.a2a_public}
                onChange={(v) => setConfig({ ...cfg, a2a_public: v })}
                label="Public Agent Card"
                description="Allow the Agent Card to be fetched without authentication (recommended for discoverability)"
              />

              <div className="space-y-2">
                <EndpointRow label="Agent Card" url={agentCardUrl} />
                <EndpointRow label="A2A Endpoint" url={a2aEndpoint} />
              </div>

              {/* Skills */}
              <div>
                <h4 className="text-sm font-semibold text-ink mb-2">
                  Skills
                  <span className="ml-2 text-xs font-normal text-ink-mute">
                    Declare what this agent can do (appears in Agent Card)
                  </span>
                </h4>

                <div className="space-y-2 mb-3">
                  {cfg.a2a_skills.map((skill, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 p-3 bg-cream rounded-lg border border-line"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-ink">{skill.name}</p>
                        <p className="text-xs text-ink-mute font-mono">{skill.id}</p>
                        {skill.description && (
                          <p className="text-xs text-ink-soft mt-0.5">{skill.description}</p>
                        )}
                      </div>
                      <button
                        onClick={() => removeSkill(idx)}
                        className="text-ash hover:text-leaf transition-colors"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <input
                    type="text"
                    value={newSkillId}
                    onChange={(e) => setNewSkillId(e.target.value)}
                    placeholder="skill_id"
                    className="px-3 py-2 text-xs border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono"
                  />
                  <input
                    type="text"
                    value={newSkillName}
                    onChange={(e) => setNewSkillName(e.target.value)}
                    placeholder="Skill Name"
                    className="px-3 py-2 text-xs border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <input
                    type="text"
                    value={newSkillDesc}
                    onChange={(e) => setNewSkillDesc(e.target.value)}
                    placeholder="Description (optional)"
                    className="px-3 py-2 text-xs border border-taupe rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={addSkill}
                  disabled={!newSkillId.trim() || !newSkillName.trim()}
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Plus size={12} />
                  Add Skill
                </button>
              </div>

              {/* Python snippet */}
              <div className="bg-sky-wash border border-sky-wash rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-azure">Python client example</h4>
                  <a
                    href="https://google.github.io/A2A/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-azure hover:text-azure"
                  >
                    A2A spec <ExternalLink size={10} />
                  </a>
                </div>
                <CodeBlock code={a2aPythonSnippet} language="python" />
              </div>

              <div className="bg-sand-deep border border-honey rounded-lg p-3">
                <p className="text-xs text-gold">
                  Generate an API key with <strong>a2a</strong> permission from the{' '}
                  <strong>API Keys</strong> section, then replace{' '}
                  <code className="bg-white px-1 rounded">YOUR_API_KEY</code> above.
                </p>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  )
}
