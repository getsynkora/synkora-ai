'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import {
  Send,
  Square,
  Paperclip,
  Mic,
  Image as ImageIcon,
  Smile,
  Bold,
  Italic,
  Code,
  Link as LinkIcon,
  X,
  Loader2,
  FileText,
  File,
  BarChart2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { VoiceInputModal } from './VoiceInputModal'
import { useFileUpload } from '../hooks/useFileUpload'
import { useDataFileUpload } from '../hooks/useDataFileUpload'
import { Attachment } from '../types'

interface ChatConfig {
  chat_title?: string
  chat_logo_url?: string
  chat_welcome_message?: string
  chat_placeholder?: string
  chat_primary_color?: string
  chat_background_color?: string
  chat_font_family?: string
}

interface ChatInputProps {
  onSend: (message: string, attachments?: Attachment[]) => void
  onStop?: () => void
  isStreaming?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
  conversationId?: string
  chatConfig?: ChatConfig | null
}

/**
 * ChatInput - Rich text input component with formatting toolbar
 * Supports file attachments, emoji, and keyboard shortcuts
 */
export function ChatInput({
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = 'Type your message…',
  className,
  conversationId,
  chatConfig,
}: ChatInputProps) {
  const [input, setInput] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadedAttachments, setUploadedAttachments] = useState<Attachment[]>([])
  const [showToolbar, setShowToolbar] = useState(false)
  const [showVoiceInput, setShowVoiceInput] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const analysisFileInputRef = useRef<HTMLInputElement>(null)

  const { uploadFiles, uploadProgress, isUploading, clearProgress } = useFileUpload()
  const { upload: uploadForAnalysis, state: analysisUploadState, reset: resetAnalysis } = useDataFileUpload()
  
  // Get primary color for theming
  const primaryColor = chatConfig?.chat_primary_color || '#0d9488' // teal-600 as default
  const effectivePlaceholder = chatConfig?.chat_placeholder || placeholder

  const handleSend = async () => {
    if (!input.trim() && uploadedAttachments.length === 0) {
      return
    }
    if (disabled || isUploading) {
      return
    }

    // Capture values before clearing
    const messageContent = input.trim()
    const attachmentsToSend = uploadedAttachments.length > 0 ? [...uploadedAttachments] : undefined

    // Clear input immediately for better UX (don't wait for streaming to complete)
    setInput('')
    setSelectedFiles([])
    setUploadedAttachments([])
    setShowToolbar(false)
    clearProgress()

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    try {
      // Send message - don't await to avoid blocking input clearing
      // Errors will be displayed in the chat UI
      onSend(messageContent, attachmentsToSend)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      setUploadError(errorMessage)
      console.error('Send error:', error)
    }
  }

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        200
      ) + 'px'
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }

    if (files.length === 0) return

    // Upload files immediately when selected
    if (conversationId) {
      try {
        setUploadError(null)
        const newAttachments = await uploadFiles(files, conversationId)
        setUploadedAttachments(prev => [...prev, ...newAttachments])
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to upload files'
        setUploadError(errorMessage)
        console.error('Upload error:', error)
      }
    } else {
      // If no conversationId yet, just add to selectedFiles
      setSelectedFiles((prev) => [...prev, ...files])
    }
  }

  const handleAnalysisFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (analysisFileInputRef.current) analysisFileInputRef.current.value = ''
    if (!file) return

    const result = await uploadForAnalysis(file)
    if (!result) return // error state already set inside the hook

    const prompt =
      `I've uploaded **${result.filename}** for analysis.\n\n` +
      `S3 URL: \`${result.s3Url}\`\n\n` +
      `Please analyze this file: describe the schema, row count, and key statistics. Then ask me what analysis I'd like to run.`
    resetAnalysis()
    onSend(prompt)
  }

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const removeUploadedAttachment = (index: number) => {
    setUploadedAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) {
      return <ImageIcon size={14} className="text-azure" />
    } else if (file.type === 'application/pdf') {
      return <FileText size={14} className="text-leaf" />
    }
    return <File size={14} className="text-ink-mute" />
  }

  const insertFormatting = (format: string) => {
    if (!textareaRef.current) return

    const start = textareaRef.current.selectionStart
    const end = textareaRef.current.selectionEnd
    const selectedText = input.substring(start, end)
    let formattedText = ''

    switch (format) {
      case 'bold':
        formattedText = `**${selectedText || 'bold text'}**`
        break
      case 'italic':
        formattedText = `*${selectedText || 'italic text'}*`
        break
      case 'code':
        formattedText = `\`${selectedText || 'code'}\``
        break
      case 'link':
        formattedText = `[${selectedText || 'link text'}](url)`
        break
    }

    const newInput =
      input.substring(0, start) + formattedText + input.substring(end)
    setInput(newInput)

    // Focus back on textarea
    setTimeout(() => {
      textareaRef.current?.focus()
      const newPosition = start + formattedText.length
      textareaRef.current?.setSelectionRange(newPosition, newPosition)
    }, 0)
  }

  const handleVoiceTranscript = (transcript: string) => {
    setInput((prev) => prev + (prev ? ' ' : '') + transcript)
  }

  const canSend = input.trim() || selectedFiles.length > 0 || uploadedAttachments.length > 0
  const isDisabled = disabled || isUploading

  return (
    <div className={cn('bg-white', className)}>
      {/* Formatting Toolbar */}
      {showToolbar && (
        <div className="px-3 sm:px-4 lg:px-5 pb-2">
          <div className="flex items-center gap-0.5 p-1 bg-cream rounded-lg w-fit">
            <button
              onClick={() => insertFormatting('bold')}
              className="p-1.5 hover:bg-white hover:shadow-sm rounded transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              title="Bold (Ctrl+B)"
            >
              <Bold size={14} className="text-ink-soft" />
            </button>
            <button
              onClick={() => insertFormatting('italic')}
              className="p-1.5 hover:bg-white hover:shadow-sm rounded transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              title="Italic (Ctrl+I)"
            >
              <Italic size={14} className="text-ink-soft" />
            </button>
            <button
              onClick={() => insertFormatting('code')}
              className="p-1.5 hover:bg-white hover:shadow-sm rounded transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              title="Code"
            >
              <Code size={14} className="text-ink-soft" />
            </button>
            <button
              onClick={() => insertFormatting('link')}
              className="p-1.5 hover:bg-white hover:shadow-sm rounded transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              title="Link"
            >
              <LinkIcon size={14} className="text-ink-soft" />
            </button>
            <div className="w-px h-4 bg-taupe mx-1" />
            <button
              onClick={() => setShowToolbar(false)}
              className="p-1.5 hover:bg-white hover:shadow-sm rounded transition-[color,background-color,border-color,box-shadow,opacity,transform]"
            >
              <X size={14} className="text-ink-mute" />
            </button>
          </div>
        </div>
      )}

      {/* Upload Error */}
      {uploadError && (
        <div className="px-3 sm:px-4 lg:px-5 pb-2">
          <div>
            <div className="flex items-center gap-2 px-3 py-2 bg-blush-wash rounded-lg text-danger text-sm">
              <X size={14} />
              <span className="flex-1">{uploadError}</span>
              <button
                onClick={() => setUploadError(null)}
                className="p-1 hover:bg-blush-wash rounded"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Upload Error */}
      {analysisUploadState.error && (
        <div className="px-3 sm:px-4 lg:px-5 pb-2">
          <div className="flex items-center gap-2 px-3 py-2 bg-blush-wash rounded-lg text-danger text-sm">
            <X size={14} />
            <span className="flex-1">{analysisUploadState.error}</span>
            <button onClick={resetAnalysis} className="p-1 hover:bg-blush-wash rounded">
              <X size={12} />
            </button>
          </div>
        </div>
      )}

      {/* Analysis Upload Progress */}
      {analysisUploadState.status === 'uploading' && (
        <div className="px-3 sm:px-4 lg:px-5 pb-2">
          <div className="flex items-center gap-2 text-sm">
            <BarChart2 size={14} className="text-leaf shrink-0" />
            <span className="text-ink-soft flex-1 truncate">Uploading for analysis…</span>
            <div className="w-20 bg-line rounded-full h-1">
              <div
                className="h-1 rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                style={{ width: `${analysisUploadState.progress}%`, backgroundColor: primaryColor }}
              />
            </div>
            <span className="text-ash text-xs w-8">{analysisUploadState.progress}%</span>
          </div>
        </div>
      )}

      {/* Upload Progress */}
      {uploadProgress.length > 0 && (
        <div className="px-3 sm:px-4 lg:px-5 pb-2">
          <div className="space-y-1.5">
            {uploadProgress.map((progress) => (
              <div key={progress.fileId} className="flex items-center gap-2 text-sm">
                <span className="text-ink-soft truncate flex-1">{progress.fileName}</span>
                <div className="w-20 bg-line rounded-full h-1">
                  <div
                    className="h-1 rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                    style={{
                      width: `${progress.progress}%`,
                      backgroundColor: progress.status === 'error' ? '#ef4444' : primaryColor
                    }}
                  />
                </div>
                <span className="text-ash text-xs w-8">{progress.progress}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Selected Files Preview */}
      {(selectedFiles.length > 0 || uploadedAttachments.length > 0) && (
        <div className="px-4 sm:px-6 lg:px-10 pb-2">
          <div className="flex flex-wrap gap-1.5">
            {selectedFiles.map((file, index) => (
              <div
                key={`file-${index}`}
                className="flex items-center gap-1.5 px-2 py-1 bg-sand rounded-md text-sm"
              >
                {getFileIcon(file)}
                <span className="text-ink-soft truncate max-w-[150px]">{file.name}</span>
                <button
                  onClick={() => removeFile(index)}
                  className="p-0.5 hover:bg-line rounded transition-colors"
                  disabled={isUploading}
                >
                  <X size={12} className="text-ink-mute" />
                </button>
              </div>
            ))}
            {uploadedAttachments.map((attachment, index) => (
              <div
                key={`uploaded-${index}`}
                className="flex items-center gap-1.5 px-2 py-1 bg-leaf-wash rounded-md text-sm"
              >
                <Paperclip size={12} className="text-leaf" />
                <span className="text-forest truncate max-w-[150px]">{attachment.file_name}</span>
                <button
                  onClick={() => removeUploadedAttachment(index)}
                  className="p-0.5 hover:bg-leaf-wash rounded transition-colors"
                >
                  <X size={12} className="text-leaf" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="px-3 py-2.5 sm:px-4 sm:py-2.5 lg:px-5">
        <div>
          <div className="flex items-end gap-1 rounded-[1rem] border border-line bg-paper p-2 shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] focus-within:border-black/15 bg-white">
            {/* Action Buttons - Left */}
            <div className="flex items-center">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileSelect}
              />
              <input
                ref={analysisFileInputRef}
                type="file"
                accept=".csv,.tsv,.json,.parquet,.ndjson,.jsonl"
                className="hidden"
                onChange={handleAnalysisFileSelect}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="rounded-[0.8rem] p-1.5 text-ash transition-colors hover:bg-white/70 hover:text-ink-soft"
                title="Attach file"
                disabled={isDisabled}
              >
                <Paperclip size={16} />
              </button>
              <button
                onClick={() => analysisFileInputRef.current?.click()}
                className="rounded-[0.8rem] p-1.5 text-ash transition-colors hover:bg-white/70 hover:text-ink-soft"
                title="Upload CSV / data file for analysis"
                disabled={isDisabled || analysisUploadState.status === 'uploading'}
              >
                <BarChart2 size={16} />
              </button>
            </div>

            {/* Text Input */}
            <div className="flex-1 min-w-0">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyPress}
                placeholder={effectivePlaceholder}
                disabled={isDisabled}
                rows={1}
                className="min-h-[32px] w-full resize-none border-0 bg-transparent py-1 text-[14px] text-ink placeholder-ash focus:outline-none focus:ring-0"
                style={{ maxHeight: '124px' }}
              />
            </div>

            {/* Action Buttons - Right */}
            <div className="flex items-center gap-0.5">
              <button
                onClick={() => setShowVoiceInput(true)}
                className="rounded-[0.8rem] p-1.5 text-ash transition-colors hover:bg-white/70 hover:text-ink-soft"
                title="Voice input"
                disabled={isDisabled}
              >
                <Mic size={16} />
              </button>
              {isStreaming && onStop ? (
                <button
                  onClick={onStop}
                  className="rounded-[0.85rem] p-1.5 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-white"
                  style={{ background: primaryColor }}
                  title="Stop generating"
                >
                  <Square size={15} className="fill-current" />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={isDisabled || !canSend}
                  className={cn(
                    'rounded-[0.85rem] p-1.5 transition-[color,background-color,border-color,box-shadow,opacity,transform]',
                    isDisabled || !canSend
                      ? 'text-taupe cursor-not-allowed'
                      : 'text-white'
                  )}
                  style={
                    !isDisabled && canSend
                      ? { background: primaryColor }
                      : undefined
                  }
                  title="Send message (Enter)"
                >
                  {isUploading ? (
                    <Loader2 size={17} className="motion-safe:animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Voice Input Modal */}
      <VoiceInputModal
        isOpen={showVoiceInput}
        onClose={() => setShowVoiceInput(false)}
        onTranscript={handleVoiceTranscript}
      />
    </div>
  )
}
