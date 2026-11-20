'use client'

import { useState, useEffect } from 'react'
import { X, Save, Loader2, FileText, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'

interface SkillEditorProps {
  fileId: string
  filename: string
  onClose: () => void
  onSave?: () => void
}

export default function SkillEditor({ fileId, filename, onClose, onSave }: SkillEditorProps) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalContent, setOriginalContent] = useState('')

  // Load file content
  useEffect(() => {
    const loadContent = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await apiClient.request('GET', `/api/v1/agents/context-files/${fileId}/content`)
        const fileContent = response?.data?.content || response?.content || ''
        setContent(fileContent)
        setOriginalContent(fileContent)
      } catch (err) {
        console.error('Failed to load skill content:', err)
        setError('Failed to load skill content')
      } finally {
        setLoading(false)
      }
    }

    loadContent()
  }, [fileId])

  // Track changes
  useEffect(() => {
    setHasChanges(content !== originalContent)
  }, [content, originalContent])

  // Handle save
  const handleSave = async () => {
    if (!hasChanges) return

    setSaving(true)
    try {
      await apiClient.request('PUT', `/api/v1/agents/context-files/${fileId}/content`, {
        content
      })
      setOriginalContent(content)
      setHasChanges(false)
      toast.success('Skill updated successfully')
      onSave?.()
    } catch (err) {
      console.error('Failed to save skill:', err)
      toast.error('Failed to save skill')
    } finally {
      setSaving(false)
    }
  }

  // Handle close with unsaved changes warning
  const handleClose = () => {
    if (hasChanges) {
      if (confirm('You have unsaved changes. Are you sure you want to close?')) {
        onClose()
      }
    } else {
      onClose()
    }
  }

  // Format filename for display
  const displayName = filename.startsWith('skill-')
    ? filename.replace('skill-', '').replace('.md', '').split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    : filename

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-line flex items-center justify-between bg-blush-wash">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-ink rounded-xl flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">Edit Skill</h2>
              <p className="text-sm text-ink-soft">{displayName}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasChanges && (
              <span className="text-xs text-warn bg-sand-deep px-2 py-1 rounded-full">
                Unsaved changes
              </span>
            )}
            <button
              onClick={handleClose}
              className="p-2 hover:bg-white/80 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-ink-mute" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-leaf motion-safe:animate-spin" />
            </div>
          ) : error ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-leaf mx-auto mb-3" />
                <p className="text-ink font-medium">{error}</p>
                <button
                  onClick={onClose}
                  className="mt-4 px-4 py-2 text-sm text-ink-soft hover:text-ink"
                >
                  Close
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 p-4 overflow-hidden">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full h-full p-4 border border-line rounded-xl font-mono text-sm resize-none focus:ring-2 focus:ring-ink focus:border-transparent"
                placeholder="Enter skill content…"
                spellCheck={false}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-line bg-cream flex items-center justify-between">
          <div className="text-sm text-ink-mute">
            {content.length.toLocaleString()} characters
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-ink-soft hover:bg-sand rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="px-4 py-2 text-sm font-medium text-white bg-ink rounded-lg hover:from-danger hover:to-danger transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg shadow-red-500/30"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 motion-safe:animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
