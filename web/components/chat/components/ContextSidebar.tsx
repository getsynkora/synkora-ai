'use client'

import { useState } from 'react'
import {
  ExternalLink,
  Users,
  Newspaper,
  ChevronDown,
  ChevronUp,
  Linkedin,
  Globe,
  Calendar,
  TrendingUp,
  Server,
  Database,
  Wrench,
  FileText,
  CheckCircle2,
  Clock,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Source, Person, NewsItem } from '../types'
import { AgentProfile } from './AgentProfile'

interface ContextSidebarProps {
  sources?: Source[]
  keyPeople?: Person[]
  news?: NewsItem[]
  mcpServers?: any[]
  knowledgeBases?: any[]
  tools?: any[]
  contextFiles?: any[]
  className?: string
  chatConfig?: {
    chat_primary_color?: string
    chat_background_color?: string
    chat_font_family?: string
  } | null
  agent?: {
    agent_name?: string
    agent_type?: string
    description?: string
    avatar?: string
    creator?: string
    likes?: number
    interactions?: string
  }
}

/**
 * ContextSidebar - Modern right sidebar displaying contextual information
 * Shows agent configuration, sources, key people, and related news
 */
export function ContextSidebar({
  sources = [],
  keyPeople = [],
  news = [],
  mcpServers = [],
  knowledgeBases = [],
  tools = [],
  contextFiles = [],
  className,
  chatConfig,
  agent,
}: ContextSidebarProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['mcp-servers', 'knowledge-bases', 'tools', 'context-files', 'sources', 'people', 'news'])
  )

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const hasConfig = mcpServers.length > 0 || knowledgeBases.length > 0 || tools.length > 0 || contextFiles.length > 0

  const primaryColor = chatConfig?.chat_primary_color || '#14b8a6'
  const bgColor = chatConfig?.chat_background_color || '#ffffff'
  const fontFamily = chatConfig?.chat_font_family

  // Generate lighter and darker shades of primary color
  const primaryLight = `${primaryColor}15`

  const sidebarStyle: React.CSSProperties = {
    backgroundColor: bgColor,
    fontFamily: fontFamily || undefined,
  }

  return (
    <div 
      className={cn('flex flex-col h-full overflow-y-auto', className)}
      style={sidebarStyle}
    >
      {/* Agent Profile Section */}
      {agent && (
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
          <AgentProfile
            agentName={agent.agent_name || 'Agent'}
            agentType={agent.agent_type}
            description={agent.description}
            avatar={agent.avatar}
            creator={agent.creator || 'Admin'}
            likes={agent.likes || 0}
            interactions={agent.interactions || '0'}
            primaryColor={primaryColor}
          />
        </div>
      )}

      <div className="p-2 space-y-1.5">
        {/* Agent Configuration Section */}
        {hasConfig && (
          <>
            {mcpServers.length > 0 && (
              <ModernSection
                title="MCP Servers"
                icon={<Server size={14} />}
                count={mcpServers.length}
                isExpanded={expandedSections.has('mcp-servers')}
                onToggle={() => toggleSection('mcp-servers')}
                primaryColor={primaryColor}
                gradient="from-blue-500 to-cyan-500"
              >
                <div className="space-y-1.5">
                  {mcpServers.map((server: any, index: number) => (
                    <ModernCard key={index} primaryColor={primaryColor}>
                      <div className="flex items-start gap-1.5">
                        <div 
                          className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: primaryLight }}
                        >
                          <Server size={12} style={{ color: primaryColor }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-900 text-[11px] truncate leading-tight">
                            {server.server_name || server.name}
                          </p>
                          {server.description && (
                            <p className="text-[10px] text-gray-500 mt-0.5 line-clamp-1 leading-tight">
                              {server.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </ModernCard>
                  ))}
                </div>
              </ModernSection>
            )}

            {knowledgeBases.length > 0 && (
              <ModernSection
                title="Knowledge Bases"
                icon={<Database size={16} />}
                count={knowledgeBases.length}
                isExpanded={expandedSections.has('knowledge-bases')}
                onToggle={() => toggleSection('knowledge-bases')}
                primaryColor={primaryColor}
                gradient="from-purple-500 to-pink-500"
              >
                <div className="space-y-2">
                  {knowledgeBases.map((kb: any, index: number) => (
                    <ModernCard key={index} primaryColor={primaryColor}>
                      <div className="flex items-start gap-2">
                        <div 
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: primaryLight }}
                        >
                          <Database size={14} style={{ color: primaryColor }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-900 text-xs truncate">{kb.name}</p>
                          {kb.description && (
                            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{kb.description}</p>
                          )}
                        </div>
                      </div>
                    </ModernCard>
                  ))}
                </div>
              </ModernSection>
            )}

            {tools.length > 0 && (
              <ModernSection
                title="Tools"
                icon={<Wrench size={16} />}
                count={tools.length}
                isExpanded={expandedSections.has('tools')}
                onToggle={() => toggleSection('tools')}
                primaryColor={primaryColor}
                gradient="from-orange-500 to-red-500"
              >
                <div className="space-y-2">
                  {tools.map((tool: any, index: number) => (
                    <ModernCard key={index} primaryColor={primaryColor}>
                      <div className="flex items-start gap-2">
                        <div 
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: primaryLight }}
                        >
                          <Wrench size={14} style={{ color: primaryColor }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-900 text-xs truncate">
                            {tool.tool_name || tool.name}
                          </p>
                          {tool.description && (
                            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{tool.description}</p>
                          )}
                        </div>
                      </div>
                    </ModernCard>
                  ))}
                </div>
              </ModernSection>
            )}

            {contextFiles.length > 0 && (
              <ModernSection
                title="Skills"
                icon={<FileText size={16} />}
                count={contextFiles.length}
                isExpanded={expandedSections.has('context-files')}
                onToggle={() => toggleSection('context-files')}
                primaryColor={primaryColor}
                gradient="from-green-500 to-emerald-500"
              >
                <div className="space-y-2">
                  {contextFiles.map((file: any, index: number) => (
                    <ModernCard key={index} primaryColor={primaryColor}>
                      <div className="flex items-start gap-2">
                        <div 
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: primaryLight }}
                        >
                          <FileText size={14} style={{ color: primaryColor }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-900 text-xs truncate">{file.filename}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-gray-500">
                              {(file.file_size / 1024).toFixed(1)} KB
                            </span>
                            {file.extraction_status === 'COMPLETED' && (
                              <StatusBadge icon={<CheckCircle2 size={10} />} color="green">
                                Ready
                              </StatusBadge>
                            )}
                            {file.extraction_status === 'PENDING' && (
                              <StatusBadge icon={<Clock size={10} />} color="yellow">
                                Processing
                              </StatusBadge>
                            )}
                            {file.extraction_status === 'FAILED' && (
                              <StatusBadge icon={<XCircle size={10} />} color="red">
                                Failed
                              </StatusBadge>
                            )}
                          </div>
                        </div>
                      </div>
                    </ModernCard>
                  ))}
                </div>
              </ModernSection>
            )}
          </>
        )}

        {/* Sources Section */}
        {sources.length > 0 && (
          <ModernSection
            title="Sources"
            icon={<Globe size={16} />}
            count={sources.length}
            isExpanded={expandedSections.has('sources')}
            onToggle={() => toggleSection('sources')}
            primaryColor={primaryColor}
            gradient="from-teal-500 to-cyan-500"
          >
            <div className="space-y-2">
              {sources.map((source, index) => (
                <SourceCard key={index} source={source} primaryColor={primaryColor} />
              ))}
            </div>
          </ModernSection>
        )}

        {/* Key People Section */}
        {keyPeople.length > 0 && (
          <ModernSection
            title="Key People"
            icon={<Users size={16} />}
            count={keyPeople.length}
            isExpanded={expandedSections.has('people')}
            onToggle={() => toggleSection('people')}
            primaryColor={primaryColor}
            gradient="from-indigo-500 to-purple-500"
          >
            <div className="space-y-2">
              {keyPeople.map((person, index) => (
                <PersonCard key={index} person={person} primaryColor={primaryColor} />
              ))}
            </div>
          </ModernSection>
        )}

        {/* News Section */}
        {news.length > 0 && (
          <ModernSection
            title="Related News"
            icon={<Newspaper size={16} />}
            count={news.length}
            isExpanded={expandedSections.has('news')}
            onToggle={() => toggleSection('news')}
            primaryColor={primaryColor}
            gradient="from-rose-500 to-pink-500"
          >
            <div className="space-y-2">
              {news.map((item, index) => (
                <NewsCard key={index} news={item} primaryColor={primaryColor} />
              ))}
            </div>
          </ModernSection>
        )}
      </div>
    </div>
  )
}

interface ModernSectionProps {
  title: string
  icon: React.ReactNode
  count: number
  isExpanded: boolean
  onToggle: () => void
  children: React.ReactNode
  primaryColor?: string
  gradient?: string
}

function ModernSection({ 
  title, 
  icon, 
  count, 
  isExpanded, 
  onToggle, 
  children, 
  primaryColor = '#14b8a6',
  gradient = 'from-teal-500 to-cyan-500'
}: ModernSectionProps) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-200 bg-white shadow-sm hover:shadow transition-all duration-150">
      <button
        onClick={onToggle}
        className="w-full px-2.5 py-2 flex items-center justify-between hover:bg-gray-50 transition-colors text-left group"
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <div 
            className={`w-6 h-6 rounded-md flex items-center justify-center bg-gradient-to-br ${gradient}`}
          >
            <div className="text-white">{icon}</div>
          </div>
          <h3 className="font-semibold text-gray-900 text-[11px] truncate">{title}</h3>
          <span 
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0"
            style={{ 
              backgroundColor: `${primaryColor}15`,
              color: primaryColor
            }}
          >
            {count}
          </span>
        </div>
        <div className="flex-shrink-0 ml-1">
          {isExpanded ? (
            <ChevronUp size={14} className="text-gray-400 group-hover:text-gray-600 transition-colors" />
          ) : (
            <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600 transition-colors" />
          )}
        </div>
      </button>
      {isExpanded && (
        <div className="px-2.5 pb-2 bg-gray-50/30">
          {children}
        </div>
      )}
    </div>
  )
}

interface ModernCardProps {
  children: React.ReactNode
  primaryColor?: string
  className?: string
}

function ModernCard({ children, className }: ModernCardProps) {
  return (
    <div 
      className={cn(
        'p-2 rounded-md border border-gray-100 bg-white hover:border-gray-200 transition-all duration-150 hover:shadow-sm',
        className
      )}
    >
      {children}
    </div>
  )
}

interface StatusBadgeProps {
  icon: React.ReactNode
  color: 'green' | 'yellow' | 'red'
  children: React.ReactNode
}

function StatusBadge({ icon, color, children }: StatusBadgeProps) {
  const colors = {
    green: 'bg-green-100 text-green-700 border-green-200',
    yellow: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    red: 'bg-red-100 text-red-700 border-red-200',
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-xs font-medium border', colors[color])}>
      {icon}
      {children}
    </span>
  )
}

interface SourceCardProps {
  source: Source
  primaryColor?: string
}

function SourceCard({ source, primaryColor = '#14b8a6' }: SourceCardProps) {
  const isRagSource = !source.url && (source as any).kb_name
  const primaryLight = `${primaryColor}15`
  
  if (isRagSource) {
    const ragSource = source as any
    return (
      <ModernCard primaryColor={primaryColor}>
        <div className="flex items-start gap-2">
          <div 
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: primaryLight }}
          >
            <Database size={14} style={{ color: primaryColor }} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-900 line-clamp-2 leading-relaxed">
              {ragSource.text || 'Knowledge Base Source'}
            </p>
            {ragSource.full_text && ragSource.full_text !== ragSource.text && (
              <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
                {ragSource.full_text}
              </p>
            )}
            <div className="flex items-center gap-2 mt-2">
              <span 
                className="text-xs font-semibold px-2 py-0.5 rounded-md"
                style={{ 
                  backgroundColor: primaryLight,
                  color: primaryColor
                }}
              >
                {ragSource.kb_name}
              </span>
              {ragSource.score && (
                <span className="text-xs text-gray-500 flex items-center gap-1">
                  <TrendingUp size={10} />
                  {(ragSource.score * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>
        </div>
      </ModernCard>
    )
  }
  
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block"
    >
      <ModernCard primaryColor={primaryColor} className="hover:scale-[1.02] cursor-pointer">
        <div className="flex items-start gap-2">
          <div 
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: primaryLight }}
          >
            {source.favicon ? (
               
              <img
                src={source.favicon}
                alt=""
                width={16}
                height={16}
                loading="lazy"
                className="w-4 h-4 rounded"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <Globe size={14} style={{ color: primaryColor }} />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-gray-900 line-clamp-2 leading-relaxed hover:underline">
              {source.title}
            </p>
            {source.description && (
              <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
                {source.description}
              </p>
            )}
            <div className="flex items-center gap-1 mt-2">
              <ExternalLink size={10} className="text-gray-400" />
              <span className="text-xs text-gray-400 truncate">
                {new URL(source.url).hostname}
              </span>
            </div>
          </div>
        </div>
      </ModernCard>
    </a>
  )
}

interface PersonCardProps {
  person: Person
  primaryColor?: string
}

function PersonCard({ person, primaryColor = '#14b8a6' }: PersonCardProps) {
  const primaryLight = `${primaryColor}15`
  
  return (
    <ModernCard primaryColor={primaryColor}>
      <div className="flex items-start gap-2">
        {person.avatar ? (
           
          <img
            src={person.avatar}
            alt={person.name}
            width={40}
            height={40}
            loading="lazy"
            className="w-10 h-10 rounded-lg object-cover flex-shrink-0 ring-2 ring-gray-100"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        ) : (
          <div 
            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm"
            style={{ 
              background: `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)` 
            }}
          >
            <span className="text-white font-bold text-sm">
              {person.name.charAt(0)}
            </span>
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-gray-900 truncate">{person.name}</h4>
          <p className="text-xs text-gray-600 mt-0.5 truncate">{person.title}</p>
          {person.company && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{person.company}</p>
          )}
          {person.linkedin && (
            <a
              href={person.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-2 text-xs font-medium hover:opacity-80 transition-opacity px-2 py-1 rounded-md"
              style={{ 
                backgroundColor: primaryLight,
                color: primaryColor
              }}
            >
              <Linkedin size={10} />
              <span>Profile</span>
            </a>
          )}
        </div>
      </div>
    </ModernCard>
  )
}

interface NewsCardProps {
  news: NewsItem
  primaryColor?: string
}

function NewsCard({ news, primaryColor = '#14b8a6' }: NewsCardProps) {
  const primaryLight = `${primaryColor}15`
  
  return (
    <a
      href={news.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block"
    >
      <ModernCard primaryColor={primaryColor} className="hover:scale-[1.02] cursor-pointer">
        <div className="flex gap-2">
          {news.thumbnail && (
             
            <img
              src={news.thumbnail}
              alt=""
              width={64}
              height={64}
              loading="lazy"
              className="w-16 h-16 rounded-lg object-cover flex-shrink-0 ring-2 ring-gray-100"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          )}
          <div className="flex-1 min-w-0">
            <h4 className="text-xs font-semibold text-gray-900 line-clamp-2 leading-relaxed hover:underline">
              {news.title}
            </h4>
            <div className="flex items-center gap-2 mt-2">
              <span 
                className="text-xs font-medium px-2 py-0.5 rounded-md"
                style={{ 
                  backgroundColor: primaryLight,
                  color: primaryColor
                }}
              >
                {news.source}
              </span>
              <div className="flex items-center gap-1 text-xs text-gray-400">
                <Calendar size={10} />
                <span>{formatDate(news.date)}</span>
              </div>
            </div>
          </div>
        </div>
      </ModernCard>
    </a>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffInMs = now.getTime() - date.getTime()
  const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60))
  const diffInDays = Math.floor(diffInHours / 24)

  if (diffInHours < 1) return 'Just now'
  if (diffInHours < 24) return `${diffInHours}h ago`
  if (diffInDays < 7) return `${diffInDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}
