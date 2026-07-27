import { apiClient } from './http'

// OAuth Apps
export async function getOAuthApps(provider?: string): Promise<any[]> {
  const params = provider ? { provider } : {}
  const { data } = await apiClient.axios.get('/api/v1/oauth/apps', { params })
  return data
}

export async function getOAuthApp(id: number): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/oauth/apps/${id}`)
  return data
}

export async function createOAuthApp(appData: any): Promise<any> {
  const { data } = await apiClient.axios.post('/api/v1/oauth/apps', appData)
  return data
}

export async function updateOAuthApp(id: number, appData: any): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/oauth/apps/${id}`, appData)
  return data
}

export async function deleteOAuthApp(id: number): Promise<void> {
  await apiClient.axios.delete(`/api/v1/oauth/apps/${id}`)
}

export async function getGitHubRepositories(oauthAppId: number): Promise<any> {
  const { data } = await apiClient.axios.get('/api/v1/oauth/github/repositories', {
    params: { oauth_app_id: oauthAppId }
  })
  return data
}

// User OAuth Tokens (per-user connections)
export async function getUserOAuthTokens(): Promise<any[]> {
  const { data } = await apiClient.axios.get('/api/v1/oauth/user-tokens')
  return data
}

export async function deleteUserOAuthToken(tokenId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/oauth/user-tokens/${tokenId}`)
}

export async function getUserConnectionStatus(oauthAppId: number): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/oauth/apps/${oauthAppId}/connection-status`)
  return data
}

/**
 * Initiate OAuth flow securely via AJAX.
 * This is the industry-standard approach - authentication happens via
 * Authorization header, user context is stored server-side in OAuth state.
 *
 * @param oauthAppId - The OAuth app ID
 * @param redirectUrl - URL to redirect to after OAuth
 * @param userLevel - Whether to store token at user level
 * @returns auth_url to redirect to
 */
export async function initiateOAuth(
  oauthAppId: number,
  redirectUrl: string,
  userLevel: boolean = false
): Promise<{ auth_url: string; state: string; provider: string }> {
  const { data } = await apiClient.axios.post('/api/v1/oauth/initiate', {
    oauth_app_id: oauthAppId,
    redirect_url: redirectUrl,
    user_level: userLevel
  })
  return data
}

/**
 * Save user's personal API token for an API token authentication app.
 */
export async function saveUserApiToken(
  oauthAppId: number,
  apiToken: string
): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.axios.post('/api/v1/oauth/user-tokens/api-token', {
    oauth_app_id: oauthAppId,
    api_token: apiToken
  })
  return data
}

export async function getPlatformOAuthApps(provider?: string): Promise<any[]> {
  const params = provider ? { provider } : {}
  const { data } = await apiClient.axios.get('/api/v1/oauth/platform-apps', { params })
  return Array.isArray(data) ? data : []
}

// Integration Configs
export async function getIntegrationConfigs(integrationType?: string): Promise<any[]> {
  const params = integrationType ? { integration_type: integrationType } : {}
  const { data } = await apiClient.axios.get('/console/api/integration-configs', { params })
  return Array.isArray(data) ? data : []
}
