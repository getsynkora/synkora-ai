'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { apiClient } from '@/lib/api/client'
import { CheckCircle, ExternalLink, Link2, Unlink, ArrowLeft, Settings } from 'lucide-react'
import { toast } from 'react-hot-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface UserOAuthToken {
  id: string
  account_id: string
  oauth_app_id: number
  provider: string
  app_name: string
  provider_user_id: string | null
  provider_email: string | null
  provider_username: string | null
  provider_display_name: string | null
  scopes: string | null
  has_access_token: boolean
  has_refresh_token: boolean
  token_expires_at: string | null
  created_at: string
  updated_at: string
}

const PROVIDER_CONFIG: Record<string, {
  name: string
  icon: React.ReactNode
  color: string
  bgColor: string
  borderColor: string
}> = {
  github: {
    name: 'GitHub',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
        <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
      </svg>
    ),
    color: 'text-ink',
    bgColor: 'bg-sand',
    borderColor: 'border-taupe',
  },
  slack: {
    name: 'Slack',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" viewBox="0 0 24 24" fill="none">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
      </svg>
    ),
    color: 'text-hotpink',
    bgColor: 'bg-blush-wash',
    borderColor: 'border-blush',
  },
  gmail: {
    name: 'Gmail',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" viewBox="0 0 24 24">
        <path fill="#EA4335" d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
      </svg>
    ),
    color: 'text-leaf',
    bgColor: 'bg-blush-wash',
    borderColor: 'border-blush',
  },
  zoom: {
    name: 'Zoom',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" viewBox="0 0 24 24" fill="#2D8CFF">
        <path d="M4.585 8.756C4.585 7.787 5.373 7 6.343 7h7.312c.97 0 1.758.787 1.758 1.756v4.488c0 .97-.788 1.756-1.758 1.756H6.343c-.97 0-1.758-.787-1.758-1.756V8.756zm12.828 1.244v4l3.414 2.4c.445.313.773.2.773-.356V7.956c0-.556-.328-.67-.773-.356l-3.414 2.4z"/>
      </svg>
    ),
    color: 'text-azure',
    bgColor: 'bg-sky-wash',
    borderColor: 'border-sky-wash',
  },
  google_calendar: {
    name: 'Google Calendar',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M18.316 5.684H5.684v12.632h12.632V5.684zM17.263 17.263H6.737V9.79h10.526v7.474z"/>
        <path fill="#EA4335" d="M6.737 5.684h10.526v2.053H6.737z"/>
        <path fill="#34A853" d="M9.842 12.947h4.316v1.579H9.842z"/>
      </svg>
    ),
    color: 'text-azure',
    bgColor: 'bg-sky-wash',
    borderColor: 'border-sky-wash',
  },
  google_drive: {
    name: 'Google Drive',
    icon: (
      <svg aria-hidden="true" className="w-6 h-6" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M7.71 3.5L1.15 15l2.74 4.75 6.56-11.38z"/>
        <path fill="#FFBA00" d="M22.85 15L16.29 3.5H9.71l6.56 11.5z"/>
        <path fill="#34A853" d="M1.15 15l2.74 4.75h16.22l2.74-4.75z"/>
      </svg>
    ),
    color: 'text-leaf',
    bgColor: 'bg-leaf-wash',
    borderColor: 'border-mint',
  },
}

export default function ConnectedAccountsPage() {
  const [tokens, setTokens] = useState<UserOAuthToken[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  useEffect(() => {
    fetchUserTokens()
  }, [])

  const fetchUserTokens = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getUserOAuthTokens()
      setTokens(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = async (tokenId: string, providerName: string) => {
    try {
      setDisconnecting(tokenId)
      await apiClient.deleteUserOAuthToken(tokenId)
      setTokens(tokens.filter(t => t.id !== tokenId))
      toast.success(`Successfully disconnected ${providerName}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect')
      toast.error('Failed to disconnect account')
    } finally {
      setDisconnecting(null)
    }
  }

  const getProviderConfig = (provider: string) => {
    const key = provider.toLowerCase()
    return PROVIDER_CONFIG[key] || {
      name: provider,
      icon: <Link2 className="w-6 h-6" />,
      color: 'text-ink-soft',
      bgColor: 'bg-sand',
      borderColor: 'border-line',
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/settings/profile"
            className="p-2 text-ink-mute hover:text-ink-soft hover:bg-sand rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Connected Accounts</h1>
            <p className="text-ink-soft mt-1 text-sm">
              Manage your personal connections to third-party services
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-5">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* Connected Accounts List */}
        {tokens.length === 0 ? (
          <div className="bg-white rounded-xl border border-line p-8 text-center">
            <Link2 className="w-12 h-12 text-taupe mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">No Connected Accounts</h3>
            <p className="text-ink-soft mb-4">
              You haven't connected any personal accounts yet. Connect your accounts on the OAuth Apps page to use your own credentials with agents.
            </p>
            <Link
              href="/oauth-apps"
              className="inline-flex items-center gap-2 px-4 py-2 bg-ink text-white rounded-lg hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm font-medium"
            >
              <Settings className="w-4 h-4" />
              Go to OAuth Apps
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {tokens.map((token) => {
              const config = getProviderConfig(token.provider)

              return (
                <div
                  key={token.id}
                  className={`bg-white rounded-xl border-2 ${config.borderColor} overflow-hidden`}
                >
                  <div className="p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        {/* Provider Icon */}
                        <div className={`w-12 h-12 ${config.bgColor} rounded-lg flex items-center justify-center`}>
                          {config.icon}
                        </div>

                        {/* Account Info */}
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-ink">{config.name}</h3>
                            <CheckCircle className="w-4 h-4 text-leaf" />
                          </div>
                          <p className="text-sm text-ink-soft mt-0.5">
                            {token.provider_email || token.provider_username || token.provider_display_name || 'Connected'}
                          </p>
                          {token.app_name && (
                            <p className="text-xs text-ash mt-0.5">
                              via {token.app_name}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-3">
                        <div className="text-right text-xs text-ink-mute">
                          <p>Connected {formatDate(token.created_at)}</p>
                        </div>
                        <button
                          onClick={() => handleDisconnect(token.id, config.name)}
                          disabled={disconnecting === token.id}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-danger bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors disabled:opacity-50"
                        >
                          <Unlink className="w-4 h-4" />
                          {disconnecting === token.id ? 'Disconnecting…' : 'Disconnect'}
                        </button>
                      </div>
                    </div>

                    {/* Additional Details */}
                    {(token.provider_username || token.scopes) && (
                      <div className="mt-4 pt-4 border-t border-sand flex items-center gap-6 text-xs text-ink-mute">
                        {token.provider_username && (
                          <div>
                            <span className="font-medium text-ink-soft">Username:</span>{' '}
                            {token.provider_username}
                          </div>
                        )}
                        {token.scopes && (
                          <div>
                            <span className="font-medium text-ink-soft">Scopes:</span>{' '}
                            <span className="truncate max-w-xs inline-block align-middle">
                              {token.scopes.split(',').slice(0, 3).join(', ')}
                              {token.scopes.split(',').length > 3 && '...'}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Help Section */}
        <div className="mt-8 bg-white rounded-xl border border-line p-5">
          <h3 className="font-semibold text-ink mb-3">About Connected Accounts</h3>
          <div className="space-y-2 text-sm text-ink-soft">
            <p>
              Connected accounts allow you to use your personal OAuth credentials with agents. When you connect your account:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Your personal token is used instead of the shared organization token</li>
              <li>Actions are performed on your behalf (e.g., GitHub commits show your name)</li>
              <li>You have control over what data you share with agents</li>
            </ul>
          </div>
          <div className="mt-4 pt-4 border-t border-sand">
            <Link
              href="/oauth-apps"
              className="inline-flex items-center gap-1 text-sm font-medium text-leaf hover:text-leaf"
            >
              <Settings className="w-4 h-4" />
              Manage OAuth Apps
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
