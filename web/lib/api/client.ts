/**
 * API Client Barrel Export
 *

 * This file provides backwards-compatible exports for the refactored API client.
 * The monolithic APIClient has been split into domain-specific modules.
 *
 * Existing imports continue to work:
 *   import { apiClient } from '@/lib/api/client'
 *   apiClient.getAgents()
 *
 * New code can import from domain modules directly:
 *   import { getAgents } from '@/lib/api/agents'
 */

import type { User, App, Conversation, Message } from '../types'

// Import core infrastructure
import { APIClient, apiClient as _apiClient } from './http'

// Import all domain modules
import * as auth from './auth'
import * as legacy from './legacy'
import * as agents from './agents'
import * as conversations from './conversations'
import * as knowledgeBases from './knowledge-bases'
import * as dataSources from './data-sources'
import * as oauth from './oauth'
import * as customTools from './custom-tools'
import * as widgets from './widgets'
import * as slackBots from './slack-bots'
import * as telegramBots from './telegram-bots'
import * as appStore from './app-store'
import * as databaseConnections from './database-connections'
import * as scheduledTasks from './scheduled-tasks'
import * as projects from './projects'
import * as roles from './roles'
import * as chatConfig from './chat-config'
import * as agentLens from './agent-lens'

// Backwards-compatible wrappers for chat config (original signatures differ from typed module)
async function _getChatConfig(agentId: string): Promise<any> {
  const response = await _apiClient.request('GET', `/api/v1/agents/${agentId}/chat-config`)
  return response?.data || response
}

async function _updateChatConfig(agentId: string, configData: any): Promise<any> {
  const response = await _apiClient.request('PUT', `/api/v1/agents/${agentId}/chat-config`, configData)
  return response?.data || response
}

// Define the extended APIClient interface for backwards compatibility
interface ExtendedAPIClient extends APIClient {
  // Auth
  login: typeof auth.login
  signup: typeof auth.signup
  logout: typeof auth.logout
  getCurrentUser: typeof auth.getCurrentUser

  // Apps & Files
  getApps: typeof legacy.getApps
  getApp: typeof legacy.getApp
  createApp: typeof legacy.createApp
  updateApp: typeof legacy.updateApp
  deleteApp: typeof legacy.deleteApp
  uploadFile: typeof legacy.uploadFile
  uploadAgentAvatar: typeof legacy.uploadAgentAvatar

  // Agents
  getAgents: typeof agents.getAgents
  getAgent: typeof agents.getAgent
  createAgent: typeof agents.createAgent
  updateAgent: typeof agents.updateAgent
  deleteAgent: typeof agents.deleteAgent
  cloneAgent: typeof agents.cloneAgent
  resetAgent: typeof agents.resetAgent
  getAgentStats: typeof agents.getAgentStats
  getAgentLLMConfigs: typeof agents.getAgentLLMConfigs
  getAgentTools: typeof agents.getAgentTools
  getAgentToolsForAgent: typeof agents.getAgentToolsForAgent
  addToolToAgent: typeof agents.addToolToAgent
  deleteAgentTool: typeof agents.deleteAgentTool
  testAgentTool: typeof agents.testAgentTool
  getCapabilities: typeof agents.getCapabilities
  enableCapability: typeof agents.enableCapability
  enableCapabilitiesBulk: typeof agents.enableCapabilitiesBulk
  disableCapability: typeof agents.disableCapability
  getAgentMCPServers: typeof agents.getAgentMCPServers
  getMCPServerTools: typeof agents.getMCPServerTools
  addMCPServerToAgent: typeof agents.addMCPServerToAgent
  removeMCPServerFromAgent: typeof agents.removeMCPServerFromAgent
  updateMCPServerConfig: typeof agents.updateMCPServerConfig
  getMCPServers: typeof agents.getMCPServers
  getAgentKnowledgeBases: typeof agents.getAgentKnowledgeBases
  addKnowledgeBaseToAgent: typeof agents.addKnowledgeBaseToAgent
  removeKnowledgeBaseFromAgent: typeof agents.removeKnowledgeBaseFromAgent
  getAgentContextFiles: typeof agents.getAgentContextFiles
  uploadAgentContextFile: typeof agents.uploadAgentContextFile
  deleteAgentContextFile: typeof agents.deleteAgentContextFile
  downloadAgentContextFile: typeof agents.downloadAgentContextFile

  // Chat Config (kept as any for backwards compat with original signatures)
  getChatConfig: (agentName: string) => Promise<any>
  updateChatConfig: (agentName: string, configData: any) => Promise<any>

  // Conversations
  getConversations: typeof conversations.getConversations
  createConversation: typeof conversations.createConversation
  deleteConversation: typeof conversations.deleteConversation
  getAgentConversations: typeof conversations.getAgentConversations
  createAgentConversation: typeof conversations.createAgentConversation
  getConversationById: typeof conversations.getConversationById
  updateConversationName: typeof conversations.updateConversationName
  deleteAgentConversation: typeof conversations.deleteAgentConversation
  getConversationMessages: typeof conversations.getConversationMessages
  sendMessage: typeof conversations.sendMessage
  getMessages: typeof conversations.getMessages
  uploadChatAttachment: typeof conversations.uploadChatAttachment
  getAnalysisUploadUrl: typeof conversations.getAnalysisUploadUrl
  createConversationShare: typeof conversations.createConversationShare
  listConversationShares: typeof conversations.listConversationShares
  revokeConversationShare: typeof conversations.revokeConversationShare
  getSharedConversation: typeof conversations.getSharedConversation

  // Knowledge Bases
  getKnowledgeBases: typeof knowledgeBases.getKnowledgeBases
  getKnowledgeBase: typeof knowledgeBases.getKnowledgeBase
  createKnowledgeBase: typeof knowledgeBases.createKnowledgeBase
  updateKnowledgeBase: typeof knowledgeBases.updateKnowledgeBase
  deleteKnowledgeBase: typeof knowledgeBases.deleteKnowledgeBase
  searchKnowledgeBase: typeof knowledgeBases.searchKnowledgeBase
  uploadDocuments: typeof knowledgeBases.uploadDocuments
  getKnowledgeBaseDocuments: typeof knowledgeBases.getKnowledgeBaseDocuments
  getKnowledgeBaseDocument: typeof knowledgeBases.getKnowledgeBaseDocument
  deleteKnowledgeBaseDocument: typeof knowledgeBases.deleteKnowledgeBaseDocument
  bulkDeleteKnowledgeBaseDocuments: typeof knowledgeBases.bulkDeleteKnowledgeBaseDocuments
  reprocessKnowledgeBaseDocument: typeof knowledgeBases.reprocessKnowledgeBaseDocument
  cancelKnowledgeBaseDocument: typeof knowledgeBases.cancelKnowledgeBaseDocument
  downloadKnowledgeBaseDocument: typeof knowledgeBases.downloadKnowledgeBaseDocument
  addTextContent: typeof knowledgeBases.addTextContent
  crawlWebsite: typeof knowledgeBases.crawlWebsite

  // Data Sources
  getDataSources: typeof dataSources.getDataSources
  getDataSource: typeof dataSources.getDataSource
  createDataSource: typeof dataSources.createDataSource
  deleteDataSource: typeof dataSources.deleteDataSource
  syncDataSource: typeof dataSources.syncDataSource
  getDataSourceSyncHistory: typeof dataSources.getDataSourceSyncHistory
  getStreamHealth: typeof dataSources.getStreamHealth
  updateDataSourceConfig: typeof dataSources.updateDataSourceConfig
  updateDataSource: typeof dataSources.updateDataSource
  activateDataSource: typeof dataSources.activateDataSource
  deactivateDataSource: typeof dataSources.deactivateDataSource

  // OAuth
  getOAuthApps: typeof oauth.getOAuthApps
  getOAuthApp: typeof oauth.getOAuthApp
  createOAuthApp: typeof oauth.createOAuthApp
  updateOAuthApp: typeof oauth.updateOAuthApp
  deleteOAuthApp: typeof oauth.deleteOAuthApp
  getGitHubRepositories: typeof oauth.getGitHubRepositories
  getUserOAuthTokens: typeof oauth.getUserOAuthTokens
  deleteUserOAuthToken: typeof oauth.deleteUserOAuthToken
  getUserConnectionStatus: typeof oauth.getUserConnectionStatus
  initiateOAuth: typeof oauth.initiateOAuth
  saveUserApiToken: typeof oauth.saveUserApiToken
  getPlatformOAuthApps: typeof oauth.getPlatformOAuthApps
  getIntegrationConfigs: typeof oauth.getIntegrationConfigs

  // Custom Tools
  getCustomTools: typeof customTools.getCustomTools
  getCustomTool: typeof customTools.getCustomTool
  createCustomTool: typeof customTools.createCustomTool
  updateCustomTool: typeof customTools.updateCustomTool
  deleteCustomTool: typeof customTools.deleteCustomTool
  importCustomToolFromUrl: typeof customTools.importCustomToolFromUrl
  getCustomToolOperations: typeof customTools.getCustomToolOperations
  testCustomTool: typeof customTools.testCustomTool
  executeCustomTool: typeof customTools.executeCustomTool

  // Widgets
  getWidgets: typeof widgets.getWidgets
  getWidget: typeof widgets.getWidget
  createWidget: typeof widgets.createWidget
  updateWidget: typeof widgets.updateWidget
  deleteWidget: typeof widgets.deleteWidget
  regenerateWidgetKey: typeof widgets.regenerateWidgetKey
  getWidgetEmbedCode: typeof widgets.getWidgetEmbedCode
  regenerateIdentitySecret: typeof widgets.regenerateIdentitySecret
  getWidgetRoutes: typeof widgets.getWidgetRoutes
  setWidgetRoutes: typeof widgets.setWidgetRoutes
  deleteWidgetRoute: typeof widgets.deleteWidgetRoute

  // Slack Bots
  getSlackBots: typeof slackBots.getSlackBots
  getSlackBot: typeof slackBots.getSlackBot
  createSlackBot: typeof slackBots.createSlackBot
  updateSlackBot: typeof slackBots.updateSlackBot
  deleteSlackBot: typeof slackBots.deleteSlackBot
  startSlackBot: typeof slackBots.startSlackBot
  stopSlackBot: typeof slackBots.stopSlackBot
  restartSlackBot: typeof slackBots.restartSlackBot
  getSlackBotStatus: typeof slackBots.getSlackBotStatus
  downloadSlackManifest: typeof slackBots.downloadSlackManifest

  // Telegram Bots
  getTelegramBots: typeof telegramBots.getTelegramBots
  getTelegramBot: typeof telegramBots.getTelegramBot
  createTelegramBot: typeof telegramBots.createTelegramBot
  updateTelegramBot: typeof telegramBots.updateTelegramBot
  deleteTelegramBot: typeof telegramBots.deleteTelegramBot
  startTelegramBot: typeof telegramBots.startTelegramBot
  stopTelegramBot: typeof telegramBots.stopTelegramBot
  restartTelegramBot: typeof telegramBots.restartTelegramBot
  getTelegramBotStatus: typeof telegramBots.getTelegramBotStatus
  validateTelegramToken: typeof telegramBots.validateTelegramToken

  // App Store
  getAppStoreSources: typeof appStore.getAppStoreSources
  getAppStoreSource: typeof appStore.getAppStoreSource
  createAppStoreSource: typeof appStore.createAppStoreSource
  updateAppStoreSource: typeof appStore.updateAppStoreSource
  deleteAppStoreSource: typeof appStore.deleteAppStoreSource
  syncAppStoreReviews: typeof appStore.syncAppStoreReviews
  analyzeAppStoreReviews: typeof appStore.analyzeAppStoreReviews
  getAppStoreInsights: typeof appStore.getAppStoreInsights
  getAppStoreReviews: typeof appStore.getAppStoreReviews

  // Database Connections
  getDatabaseConnections: typeof databaseConnections.getDatabaseConnections
  getDatabaseConnection: typeof databaseConnections.getDatabaseConnection
  createDatabaseConnection: typeof databaseConnections.createDatabaseConnection
  updateDatabaseConnection: typeof databaseConnections.updateDatabaseConnection
  deleteDatabaseConnection: typeof databaseConnections.deleteDatabaseConnection
  testDatabaseConnection: typeof databaseConnections.testDatabaseConnection
  testDatabaseConnectionDetails: typeof databaseConnections.testDatabaseConnectionDetails

  // Scheduled Tasks
  getScheduledTasks: typeof scheduledTasks.getScheduledTasks
  getScheduledTask: typeof scheduledTasks.getScheduledTask
  createScheduledTask: typeof scheduledTasks.createScheduledTask
  updateScheduledTask: typeof scheduledTasks.updateScheduledTask
  deleteScheduledTask: typeof scheduledTasks.deleteScheduledTask
  executeScheduledTask: typeof scheduledTasks.executeScheduledTask
  toggleScheduledTask: typeof scheduledTasks.toggleScheduledTask
  getTaskExecutions: typeof scheduledTasks.getTaskExecutions
  validateCronExpression: typeof scheduledTasks.validateCronExpression

  // Projects
  getProjects: typeof projects.getProjects
  getProject: typeof projects.getProject
  createProject: typeof projects.createProject
  updateProject: typeof projects.updateProject
  deleteProject: typeof projects.deleteProject
  getProjectContext: typeof projects.getProjectContext
  updateProjectContext: typeof projects.updateProjectContext
  addAgentToProject: typeof projects.addAgentToProject
  removeAgentFromProject: typeof projects.removeAgentFromProject
  getEscalations: typeof projects.getEscalations
  getEscalation: typeof projects.getEscalation
  resolveEscalation: typeof projects.resolveEscalation

  // Roles
  getAgentRoles: typeof roles.getAgentRoles
  getAgentRole: typeof roles.getAgentRole
  createAgentRole: typeof roles.createAgentRole
  updateAgentRole: typeof roles.updateAgentRole
  deleteAgentRole: typeof roles.deleteAgentRole
  getHumanContacts: typeof roles.getHumanContacts
  getHumanContact: typeof roles.getHumanContact
  createHumanContact: typeof roles.createHumanContact
  updateHumanContact: typeof roles.updateHumanContact
  deleteHumanContact: typeof roles.deleteHumanContact

  // Agent Lens
  getLensOverview: typeof agentLens.getLensOverview
  getLensTokenDistribution: typeof agentLens.getLensTokenDistribution
  getLensSessions: typeof agentLens.getLensSessions
  getLensSessionDetail: typeof agentLens.getLensSessionDetail
  getLensAlerts: typeof agentLens.getLensAlerts
  createLensAlert: typeof agentLens.createLensAlert
  updateLensAlert: typeof agentLens.updateLensAlert
  deleteLensAlert: typeof agentLens.deleteLensAlert
}

// Compose the extended apiClient with all domain methods
export const apiClient: ExtendedAPIClient = Object.assign(_apiClient, {
  // Auth
  login: auth.login,
  signup: auth.signup,
  logout: auth.logout,
  getCurrentUser: auth.getCurrentUser,

  // Apps & Files
  getApps: legacy.getApps,
  getApp: legacy.getApp,
  createApp: legacy.createApp,
  updateApp: legacy.updateApp,
  deleteApp: legacy.deleteApp,
  uploadFile: legacy.uploadFile,
  uploadAgentAvatar: legacy.uploadAgentAvatar,

  // Agents
  getAgents: agents.getAgents,
  getAgent: agents.getAgent,
  createAgent: agents.createAgent,
  updateAgent: agents.updateAgent,
  deleteAgent: agents.deleteAgent,
  cloneAgent: agents.cloneAgent,
  resetAgent: agents.resetAgent,
  getAgentStats: agents.getAgentStats,
  getAgentLLMConfigs: agents.getAgentLLMConfigs,
  getAgentTools: agents.getAgentTools,
  getAgentToolsForAgent: agents.getAgentToolsForAgent,
  addToolToAgent: agents.addToolToAgent,
  deleteAgentTool: agents.deleteAgentTool,
  testAgentTool: agents.testAgentTool,
  getCapabilities: agents.getCapabilities,
  enableCapability: agents.enableCapability,
  enableCapabilitiesBulk: agents.enableCapabilitiesBulk,
  disableCapability: agents.disableCapability,
  getAgentMCPServers: agents.getAgentMCPServers,
  getMCPServerTools: agents.getMCPServerTools,
  addMCPServerToAgent: agents.addMCPServerToAgent,
  removeMCPServerFromAgent: agents.removeMCPServerFromAgent,
  updateMCPServerConfig: agents.updateMCPServerConfig,
  getMCPServers: agents.getMCPServers,
  getAgentKnowledgeBases: agents.getAgentKnowledgeBases,
  addKnowledgeBaseToAgent: agents.addKnowledgeBaseToAgent,
  removeKnowledgeBaseFromAgent: agents.removeKnowledgeBaseFromAgent,
  getAgentContextFiles: agents.getAgentContextFiles,
  uploadAgentContextFile: agents.uploadAgentContextFile,
  deleteAgentContextFile: agents.deleteAgentContextFile,
  downloadAgentContextFile: agents.downloadAgentContextFile,

  // Chat Config
  getChatConfig: _getChatConfig,
  updateChatConfig: _updateChatConfig,

  // Conversations
  getConversations: conversations.getConversations,
  createConversation: conversations.createConversation,
  deleteConversation: conversations.deleteConversation,
  getAgentConversations: conversations.getAgentConversations,
  createAgentConversation: conversations.createAgentConversation,
  getConversationById: conversations.getConversationById,
  updateConversationName: conversations.updateConversationName,
  deleteAgentConversation: conversations.deleteAgentConversation,
  getConversationMessages: conversations.getConversationMessages,
  sendMessage: conversations.sendMessage,
  getMessages: conversations.getMessages,
  uploadChatAttachment: conversations.uploadChatAttachment,
  getAnalysisUploadUrl: conversations.getAnalysisUploadUrl,
  createConversationShare: conversations.createConversationShare,
  listConversationShares: conversations.listConversationShares,
  revokeConversationShare: conversations.revokeConversationShare,
  getSharedConversation: conversations.getSharedConversation,

  // Knowledge Bases
  getKnowledgeBases: knowledgeBases.getKnowledgeBases,
  getKnowledgeBase: knowledgeBases.getKnowledgeBase,
  createKnowledgeBase: knowledgeBases.createKnowledgeBase,
  updateKnowledgeBase: knowledgeBases.updateKnowledgeBase,
  deleteKnowledgeBase: knowledgeBases.deleteKnowledgeBase,
  searchKnowledgeBase: knowledgeBases.searchKnowledgeBase,
  uploadDocuments: knowledgeBases.uploadDocuments,
  getKnowledgeBaseDocuments: knowledgeBases.getKnowledgeBaseDocuments,
  getKnowledgeBaseDocument: knowledgeBases.getKnowledgeBaseDocument,
  deleteKnowledgeBaseDocument: knowledgeBases.deleteKnowledgeBaseDocument,
  bulkDeleteKnowledgeBaseDocuments: knowledgeBases.bulkDeleteKnowledgeBaseDocuments,
  reprocessKnowledgeBaseDocument: knowledgeBases.reprocessKnowledgeBaseDocument,
  cancelKnowledgeBaseDocument: knowledgeBases.cancelKnowledgeBaseDocument,
  downloadKnowledgeBaseDocument: knowledgeBases.downloadKnowledgeBaseDocument,
  addTextContent: knowledgeBases.addTextContent,
  crawlWebsite: knowledgeBases.crawlWebsite,

  // Data Sources
  getDataSources: dataSources.getDataSources,
  getDataSource: dataSources.getDataSource,
  createDataSource: dataSources.createDataSource,
  deleteDataSource: dataSources.deleteDataSource,
  syncDataSource: dataSources.syncDataSource,
  getDataSourceSyncHistory: dataSources.getDataSourceSyncHistory,
  getStreamHealth: dataSources.getStreamHealth,
  updateDataSourceConfig: dataSources.updateDataSourceConfig,
  updateDataSource: dataSources.updateDataSource,
  activateDataSource: dataSources.activateDataSource,
  deactivateDataSource: dataSources.deactivateDataSource,

  // OAuth
  getOAuthApps: oauth.getOAuthApps,
  getOAuthApp: oauth.getOAuthApp,
  createOAuthApp: oauth.createOAuthApp,
  updateOAuthApp: oauth.updateOAuthApp,
  deleteOAuthApp: oauth.deleteOAuthApp,
  getGitHubRepositories: oauth.getGitHubRepositories,
  getUserOAuthTokens: oauth.getUserOAuthTokens,
  deleteUserOAuthToken: oauth.deleteUserOAuthToken,
  getUserConnectionStatus: oauth.getUserConnectionStatus,
  initiateOAuth: oauth.initiateOAuth,
  saveUserApiToken: oauth.saveUserApiToken,
  getPlatformOAuthApps: oauth.getPlatformOAuthApps,
  getIntegrationConfigs: oauth.getIntegrationConfigs,

  // Custom Tools
  getCustomTools: customTools.getCustomTools,
  getCustomTool: customTools.getCustomTool,
  createCustomTool: customTools.createCustomTool,
  updateCustomTool: customTools.updateCustomTool,
  deleteCustomTool: customTools.deleteCustomTool,
  importCustomToolFromUrl: customTools.importCustomToolFromUrl,
  getCustomToolOperations: customTools.getCustomToolOperations,
  testCustomTool: customTools.testCustomTool,
  executeCustomTool: customTools.executeCustomTool,

  // Widgets
  getWidgets: widgets.getWidgets,
  getWidget: widgets.getWidget,
  createWidget: widgets.createWidget,
  updateWidget: widgets.updateWidget,
  deleteWidget: widgets.deleteWidget,
  regenerateWidgetKey: widgets.regenerateWidgetKey,
  getWidgetEmbedCode: widgets.getWidgetEmbedCode,
  regenerateIdentitySecret: widgets.regenerateIdentitySecret,
  getWidgetRoutes: widgets.getWidgetRoutes,
  setWidgetRoutes: widgets.setWidgetRoutes,
  deleteWidgetRoute: widgets.deleteWidgetRoute,

  // Slack Bots
  getSlackBots: slackBots.getSlackBots,
  getSlackBot: slackBots.getSlackBot,
  createSlackBot: slackBots.createSlackBot,
  updateSlackBot: slackBots.updateSlackBot,
  deleteSlackBot: slackBots.deleteSlackBot,
  startSlackBot: slackBots.startSlackBot,
  stopSlackBot: slackBots.stopSlackBot,
  restartSlackBot: slackBots.restartSlackBot,
  getSlackBotStatus: slackBots.getSlackBotStatus,
  downloadSlackManifest: slackBots.downloadSlackManifest,

  // Telegram Bots
  getTelegramBots: telegramBots.getTelegramBots,
  getTelegramBot: telegramBots.getTelegramBot,
  createTelegramBot: telegramBots.createTelegramBot,
  updateTelegramBot: telegramBots.updateTelegramBot,
  deleteTelegramBot: telegramBots.deleteTelegramBot,
  startTelegramBot: telegramBots.startTelegramBot,
  stopTelegramBot: telegramBots.stopTelegramBot,
  restartTelegramBot: telegramBots.restartTelegramBot,
  getTelegramBotStatus: telegramBots.getTelegramBotStatus,
  validateTelegramToken: telegramBots.validateTelegramToken,

  // App Store
  getAppStoreSources: appStore.getAppStoreSources,
  getAppStoreSource: appStore.getAppStoreSource,
  createAppStoreSource: appStore.createAppStoreSource,
  updateAppStoreSource: appStore.updateAppStoreSource,
  deleteAppStoreSource: appStore.deleteAppStoreSource,
  syncAppStoreReviews: appStore.syncAppStoreReviews,
  analyzeAppStoreReviews: appStore.analyzeAppStoreReviews,
  getAppStoreInsights: appStore.getAppStoreInsights,
  getAppStoreReviews: appStore.getAppStoreReviews,

  // Database Connections
  getDatabaseConnections: databaseConnections.getDatabaseConnections,
  getDatabaseConnection: databaseConnections.getDatabaseConnection,
  createDatabaseConnection: databaseConnections.createDatabaseConnection,
  updateDatabaseConnection: databaseConnections.updateDatabaseConnection,
  deleteDatabaseConnection: databaseConnections.deleteDatabaseConnection,
  testDatabaseConnection: databaseConnections.testDatabaseConnection,
  testDatabaseConnectionDetails: databaseConnections.testDatabaseConnectionDetails,

  // Scheduled Tasks
  getScheduledTasks: scheduledTasks.getScheduledTasks,
  getScheduledTask: scheduledTasks.getScheduledTask,
  createScheduledTask: scheduledTasks.createScheduledTask,
  updateScheduledTask: scheduledTasks.updateScheduledTask,
  deleteScheduledTask: scheduledTasks.deleteScheduledTask,
  executeScheduledTask: scheduledTasks.executeScheduledTask,
  toggleScheduledTask: scheduledTasks.toggleScheduledTask,
  getTaskExecutions: scheduledTasks.getTaskExecutions,
  validateCronExpression: scheduledTasks.validateCronExpression,

  // Projects
  getProjects: projects.getProjects,
  getProject: projects.getProject,
  createProject: projects.createProject,
  updateProject: projects.updateProject,
  deleteProject: projects.deleteProject,
  getProjectContext: projects.getProjectContext,
  updateProjectContext: projects.updateProjectContext,
  addAgentToProject: projects.addAgentToProject,
  removeAgentFromProject: projects.removeAgentFromProject,
  getEscalations: projects.getEscalations,
  getEscalation: projects.getEscalation,
  resolveEscalation: projects.resolveEscalation,

  // Roles
  getAgentRoles: roles.getAgentRoles,
  getAgentRole: roles.getAgentRole,
  createAgentRole: roles.createAgentRole,
  updateAgentRole: roles.updateAgentRole,
  deleteAgentRole: roles.deleteAgentRole,
  getHumanContacts: roles.getHumanContacts,
  getHumanContact: roles.getHumanContact,
  createHumanContact: roles.createHumanContact,
  updateHumanContact: roles.updateHumanContact,
  deleteHumanContact: roles.deleteHumanContact,

  // Agent Lens
  getLensOverview: agentLens.getLensOverview,
  getLensTokenDistribution: agentLens.getLensTokenDistribution,
  getLensSessions: agentLens.getLensSessions,
  getLensSessionDetail: agentLens.getLensSessionDetail,
  getLensAlerts: agentLens.getLensAlerts,
  createLensAlert: agentLens.createLensAlert,
  updateLensAlert: agentLens.updateLensAlert,
  deleteLensAlert: agentLens.deleteLensAlert,
}) as ExtendedAPIClient

// Export the APIClient class for typing purposes
export { APIClient }

// Re-export all domain modules for direct imports
export * from './auth'
export * from './legacy'
export * from './agents'
export * from './conversations'
export * from './knowledge-bases'
export * from './data-sources'
export * from './oauth'
export * from './custom-tools'
export * from './widgets'
export * from './slack-bots'
export * from './telegram-bots'
export * from './app-store'
export * from './database-connections'
export * from './scheduled-tasks'
export * from './projects'
export * from './roles'
export * from './chat-config'
export * from './agent-lens'
