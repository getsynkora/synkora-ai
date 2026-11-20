'use client'

import { useState } from 'react'
import { Search, X, Check, Sparkles } from 'lucide-react'
import { AGENT_TEMPLATES, TEMPLATE_CATEGORIES, AgentTemplate, searchTemplates, getTemplatesByCategory } from '@/lib/data/agent-templates'

interface TemplateSelectorProps {
  onSelect: (template: AgentTemplate) => void
  onClose: () => void
}

export default function TemplateSelector({ onSelect, onClose }: TemplateSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [hoveredTemplate, setHoveredTemplate] = useState<string | null>(null)

  const filteredTemplates = searchQuery
    ? searchTemplates(searchQuery)
    : selectedCategory
      ? getTemplatesByCategory(selectedCategory)
      : AGENT_TEMPLATES

  const groupedTemplates = selectedCategory || searchQuery
    ? { [selectedCategory || 'Search Results']: filteredTemplates }
    : TEMPLATE_CATEGORIES.reduce((acc, cat) => {
        acc[cat.id] = getTemplatesByCategory(cat.id)
        return acc
      }, {} as Record<string, AgentTemplate[]>)

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-line flex items-center justify-between bg-blush-wash">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-ink rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">Choose a Template</h2>
              <p className="text-sm text-ink-soft">Start with a pre-configured agent template</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/80 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-ink-mute" />
          </button>
        </div>

        {/* Search and Filters */}
        <div className="px-6 py-4 border-b border-sand">
          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ash" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setSelectedCategory(null)
                }}
                placeholder="Search templates…"
                className="w-full pl-10 pr-4 py-2 border border-line rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent text-sm"
              />
            </div>

            {/* Category Filters */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setSelectedCategory(null)
                  setSearchQuery('')
                }}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  !selectedCategory && !searchQuery
                    ? 'bg-blush-wash text-leaf'
                    : 'text-ink-soft hover:bg-sand'
                }`}
              >
                All
              </button>
              {TEMPLATE_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => {
                    setSelectedCategory(cat.id)
                    setSearchQuery('')
                  }}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                    selectedCategory === cat.id
                      ? 'bg-blush-wash text-leaf'
                      : 'text-ink-soft hover:bg-sand'
                  }`}
                >
                  <span>{cat.icon}</span>
                  {cat.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Templates Grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {Object.entries(groupedTemplates).map(([category, templates]) => {
            if (templates.length === 0) return null
            const categoryInfo = TEMPLATE_CATEGORIES.find(c => c.id === category)

            return (
              <div key={category} className="mb-8 last:mb-0">
                {!searchQuery && (
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-xl">{categoryInfo?.icon}</span>
                    <h3 className="text-base font-semibold text-ink">{categoryInfo?.name || category}</h3>
                    <span className="text-sm text-ink-mute">({templates.length})</span>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {templates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => onSelect(template)}
                      onMouseEnter={() => setHoveredTemplate(template.id)}
                      onMouseLeave={() => setHoveredTemplate(null)}
                      className={`relative text-left p-4 rounded-xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                        hoveredTemplate === template.id
                          ? 'border-hotpink bg-blush-wash shadow-md'
                          : 'border-line hover:border-taupe bg-white'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-10 h-10 ${template.color} rounded-lg flex items-center justify-center text-white text-lg flex-shrink-0`}>
                          {template.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-ink text-sm">{template.name}</h4>
                          <p className="text-xs text-ink-mute mt-1 line-clamp-2">{template.description}</p>
                        </div>
                      </div>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-1 mt-3">
                        {template.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-0.5 bg-sand text-ink-soft text-[10px] rounded-full"
                          >
                            {tag}
                          </span>
                        ))}
                        {template.tags.length > 3 && (
                          <span className="px-2 py-0.5 bg-sand text-ink-soft text-[10px] rounded-full">
                            +{template.tags.length - 3}
                          </span>
                        )}
                      </div>

                      {/* Hover indicator */}
                      {hoveredTemplate === template.id && (
                        <div className="absolute top-2 right-2 w-6 h-6 bg-ink rounded-full flex items-center justify-center">
                          <Check className="w-4 h-4 text-white" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )
          })}

          {filteredTemplates.length === 0 && (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-sand rounded-full flex items-center justify-center mx-auto mb-4">
                <Search className="w-8 h-8 text-ash" />
              </div>
              <h3 className="text-lg font-medium text-ink mb-2">No templates found</h3>
              <p className="text-ink-mute">Try a different search term or category</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-line bg-cream flex items-center justify-between">
          <p className="text-sm text-ink-mute">
            {AGENT_TEMPLATES.length} templates available
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-ink-soft hover:bg-sand rounded-lg transition-colors"
          >
            Start from scratch instead
          </button>
        </div>
      </div>
    </div>
  )
}
