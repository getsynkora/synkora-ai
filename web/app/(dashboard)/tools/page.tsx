'use client';

import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { 
  Settings, 
  Key, 
  Globe, 
  Github, 
  Mail, 
  Youtube,
  Save,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';

interface ToolConfig {
  name: string;
  displayName: string;
  description: string;
  icon: any;
  requiredKeys?: {
    key: string;
    label: string;
    description: string;
    placeholder: string;
    type: 'text' | 'password';
  }[];
  optionalKeys?: {
    key: string;
    label: string;
    description: string;
    placeholder: string;
    type: 'text' | 'password';
  }[];
}

const TOOL_CONFIGS: ToolConfig[] = [
  {
    name: 'web_search',
    displayName: 'Web Search',
    description: 'Search the web using Google Search via SerpAPI',
    icon: Globe,
    requiredKeys: [
      {
        key: 'SERPAPI_KEY',
        label: 'SerpAPI Key',
        description: 'Get your free API key from serpapi.com (100 searches/month free)',
        placeholder: 'Enter your SerpAPI key',
        type: 'password'
      }
    ]
  },
  {
    name: 'github',
    displayName: 'GitHub',
    description: 'Search repositories, get repo info, and list issues',
    icon: Github,
    optionalKeys: [
      {
        key: 'GITHUB_TOKEN',
        label: 'GitHub Token',
        description: 'Optional: Increases rate limits. Generate at github.com/settings/tokens',
        placeholder: 'ghp_xxxxxxxxxxxx',
        type: 'password'
      }
    ]
  },
  {
    name: 'GMAIL',
    displayName: 'Gmail',
    description: 'List and send emails via Gmail',
    icon: Mail,
    requiredKeys: [
      {
        key: 'GMAIL_CREDENTIALS_PATH',
        label: 'Gmail Credentials Path',
        description: 'Path to your Gmail OAuth credentials JSON file',
        placeholder: '/path/to/credentials.json',
        type: 'text'
      }
    ]
  },
  {
    name: 'youtube',
    displayName: 'YouTube',
    description: 'Search videos and get video information',
    icon: Youtube,
    requiredKeys: [
      {
        key: 'YOUTUBE_API_KEY',
        label: 'YouTube API Key',
        description: 'Get your API key from Google Cloud Console',
        placeholder: 'AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx',
        type: 'password'
      }
    ]
  }
];

export default function ToolsPage() {
  const [configs, setConfigs] = useState<Record<string, Record<string, string>>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<Record<string, 'success' | 'error' | null>>({});

  useEffect(() => {
    loadConfigurations();
  }, []);

  const loadConfigurations = async () => {
    try {
      const response = await fetch('/api/v1/tools/config');
      if (response.ok) {
        const data = await response.json();
        setConfigs(data);
      }
    } catch (error) {
      console.error('Failed to load configurations:', error);
    }
  };

  const handleConfigChange = (toolName: string, key: string, value: string) => {
    setConfigs(prev => ({
      ...prev,
      [toolName]: {
        ...prev[toolName],
        [key]: value
      }
    }));
  };

  const toggleShowKey = (key: string) => {
    setShowKeys(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const saveConfiguration = async (toolName: string) => {
    setSaving(toolName);
    setSaveStatus(prev => ({ ...prev, [toolName]: null }));

    try {
      const response = await fetch('/api/v1/tools/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tool: toolName,
          config: configs[toolName] || {}
        })
      });

      if (response.ok) {
        setSaveStatus(prev => ({ ...prev, [toolName]: 'success' }));
        setTimeout(() => {
          setSaveStatus(prev => ({ ...prev, [toolName]: null }));
        }, 3000);
      } else {
        setSaveStatus(prev => ({ ...prev, [toolName]: 'error' }));
      }
    } catch (error) {
      console.error('Failed to save configuration:', error);
      setSaveStatus(prev => ({ ...prev, [toolName]: 'error' }));
    } finally {
      setSaving(null);
    }
  };

  const testConfiguration = async (toolName: string) => {
    try {
      const response = await fetch(`/api/v1/tools/test/${toolName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configs[toolName] || {})
      });

      const result = await response.json();
      
      if (result.success) {
        toast.success('Configuration test successful!');
      } else {
        toast.error(`Configuration test failed: ${result.error}`);
      }
    } catch (error) {
      toast.error(`Configuration test failed: ${error}`);
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Settings className="w-8 h-8 text-leaf" />
            <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Tool Configuration</h1>
          </div>
          <p className="text-ink-soft">
            Configure API keys and settings for agent tools. These configurations are stored securely
            and used by your agents when they need to access external services.
          </p>
        </div>

        <div className="space-y-6">
          {TOOL_CONFIGS.map((tool) => {
            const Icon = tool.icon;
            const toolConfig = configs[tool.name] || {};
            const status = saveStatus[tool.name];
            const allRequiredFilled = tool.requiredKeys?.every(
              key => toolConfig[key.key]?.trim()
            ) ?? true;

            return (
              <div
                key={tool.name}
                className="bg-white rounded-lg shadow-sm border border-line overflow-hidden"
              >
                <div className="bg-leaf-wash p-6 border-b border-line">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="p-3 bg-white rounded-lg shadow-sm">
                        <Icon className="w-6 h-6 text-leaf" />
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold text-ink mb-1">
                          {tool.displayName}
                        </h2>
                        <p className="text-ink-soft">{tool.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {allRequiredFilled ? (
                        <div className="flex items-center gap-1 text-leaf text-sm">
                          <CheckCircle className="w-4 h-4" />
                          <span>Configured</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-warn text-sm">
                          <AlertCircle className="w-4 h-4" />
                          <span>Not Configured</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {tool.requiredKeys && tool.requiredKeys.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink mb-4 flex items-center gap-2">
                        <Key className="w-4 h-4" />
                        Required Configuration
                      </h3>
                      <div className="space-y-4">
                        {tool.requiredKeys.map((keyConfig) => (
                          <div key={keyConfig.key}>
                            <label className="block text-sm font-medium text-ink-soft mb-1">
                              {keyConfig.label}
                            </label>
                            <p className="text-xs text-ink-mute mb-2">
                              {keyConfig.description}
                            </p>
                            <div className="relative">
                              <input
                                type={showKeys[keyConfig.key] ? 'text' : keyConfig.type}
                                value={toolConfig[keyConfig.key] || ''}
                                onChange={(e) =>
                                  handleConfigChange(tool.name, keyConfig.key, e.target.value)
                                }
                                placeholder={keyConfig.placeholder}
                                className="w-full px-4 py-2 pr-10 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                              />
                              {keyConfig.type === 'password' && (
                                <button
                                  type="button"
                                  onClick={() => toggleShowKey(keyConfig.key)}
                                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ash hover:text-ink-soft"
                                >
                                  {showKeys[keyConfig.key] ? (
                                    <EyeOff className="w-4 h-4" />
                                  ) : (
                                    <Eye className="w-4 h-4" />
                                  )}
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {tool.optionalKeys && tool.optionalKeys.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-ink mb-4">
                        Optional Configuration
                      </h3>
                      <div className="space-y-4">
                        {tool.optionalKeys.map((keyConfig) => (
                          <div key={keyConfig.key}>
                            <label className="block text-sm font-medium text-ink-soft mb-1">
                              {keyConfig.label}
                            </label>
                            <p className="text-xs text-ink-mute mb-2">
                              {keyConfig.description}
                            </p>
                            <div className="relative">
                              <input
                                type={showKeys[keyConfig.key] ? 'text' : keyConfig.type}
                                value={toolConfig[keyConfig.key] || ''}
                                onChange={(e) =>
                                  handleConfigChange(tool.name, keyConfig.key, e.target.value)
                                }
                                placeholder={keyConfig.placeholder}
                                className="w-full px-4 py-2 pr-10 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                              />
                              {keyConfig.type === 'password' && (
                                <button
                                  type="button"
                                  onClick={() => toggleShowKey(keyConfig.key)}
                                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ash hover:text-ink-soft"
                                >
                                  {showKeys[keyConfig.key] ? (
                                    <EyeOff className="w-4 h-4" />
                                  ) : (
                                    <Eye className="w-4 h-4" />
                                  )}
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-3 pt-4 border-t border-line">
                    <button
                      onClick={() => saveConfiguration(tool.name)}
                      disabled={saving === tool.name}
                      className="flex items-center gap-2 px-4 py-2 bg-leaf text-white rounded-lg hover:bg-forest disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <Save className="w-4 h-4" />
                      {saving === tool.name ? 'Saving…' : 'Save Configuration'}
                    </button>

                    {allRequiredFilled && (
                      <button
                        onClick={() => testConfiguration(tool.name)}
                        className="flex items-center gap-2 px-4 py-2 border border-taupe text-ink-soft rounded-lg hover:bg-cream transition-colors"
                      >
                        <CheckCircle className="w-4 h-4" />
                        Test Configuration
                      </button>
                    )}

                    {status === 'success' && (
                      <div className="flex items-center gap-2 text-leaf text-sm">
                        <CheckCircle className="w-4 h-4" />
                        <span>Saved successfully!</span>
                      </div>
                    )}

                    {status === 'error' && (
                      <div className="flex items-center gap-2 text-danger text-sm">
                        <XCircle className="w-4 h-4" />
                        <span>Failed to save</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-8 bg-sky-wash border border-sky-wash rounded-lg p-6">
          <h3 className="text-lg font-semibold text-azure mb-2">Need Help?</h3>
          <ul className="space-y-2 text-sm text-azure">
            <li>• <strong>SerpAPI:</strong> Sign up at <a href="https://serpapi.com" target="_blank" rel="noopener noreferrer" className="underline">serpapi.com</a> for free web search (100 searches/month)</li>
            <li>• <strong>GitHub:</strong> Generate a token at <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer" className="underline">github.com/settings/tokens</a></li>
            <li>• <strong>YouTube:</strong> Create an API key in <a href="https://console.cloud.google.com" target="_blank" rel="noopener noreferrer" className="underline">Google Cloud Console</a></li>
            <li>• <strong>Gmail:</strong> Set up OAuth credentials following <a href="https://developers.google.com/gmail/api/quickstart" target="_blank" rel="noopener noreferrer" className="underline">Gmail API Quickstart</a></li>
          </ul>
        </div>
      </div>
    </div>
  );
}
