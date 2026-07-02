'use client'

import { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, CheckCircle, AlertCircle, Loader2, Download, Trash2, Search, Sparkles, ChevronDown, Plus, Pencil, Zap, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { apiClient } from '@/lib/api/client'
import { PREDEFINED_SKILLS, SKILL_CATEGORIES, PredefinedSkill, searchSkills, getSkillsByCategory } from '@/lib/data/predefined-skills'
import SkillEditor from './SkillEditor'

interface FileWithProgress {
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
}

interface ContextFile {
  id: string
  filename: string
  file_type: string
  file_size: number
  extraction_status: 'PENDING' | 'COMPLETED' | 'FAILED'
  extraction_error?: string
  display_order: number
  created_at: string
  load_mode: 'always' | 'on_demand'
  description?: string
}

interface ContextFilesUploadProps {
  agentName: string
  onUploadComplete?: () => void
}

const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'text/html': ['.html'],
  'text/csv': ['.csv'],
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const MAX_FILES = 20

export default function ContextFilesUpload({ agentName, onUploadComplete }: ContextFilesUploadProps) {
  const [files, setFiles] = useState<FileWithProgress[]>([])
  const [uploading, setUploading] = useState(false)
  const [existingFiles, setExistingFiles] = useState<ContextFile[]>([])
  const [loading, setLoading] = useState(true)

  // Skill selector state
  const [showSkillSelector, setShowSkillSelector] = useState(false)
  const [skillSearchQuery, setSkillSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [addingSkill, setAddingSkill] = useState<string | null>(null)

  // Editor state
  const [editingFile, setEditingFile] = useState<ContextFile | null>(null)

  // Load existing context files
  const loadExistingFiles = useCallback(async () => {
    try {
      setLoading(true)
      const response = await apiClient.request('GET', `/api/v1/agents/${agentName}/context-files`)
      // Handle nested response structure: response.data.files
      const files = response?.data?.files || response?.files || response || []
      setExistingFiles(files)
    } catch (error) {
      console.error('Failed to load context files:', error)
      toast.error('Failed to load existing files')
    } finally {
      setLoading(false)
    }
  }, [agentName])

  // Load files on mount
  useEffect(() => {
    loadExistingFiles()
  }, [loadExistingFiles])

  // Get filtered skills based on search and category
  const filteredSkills = skillSearchQuery
    ? searchSkills(skillSearchQuery)
    : selectedCategory
      ? getSkillsByCategory(selectedCategory)
      : PREDEFINED_SKILLS

  // Handle adding a pre-defined skill
  const handleAddSkill = async (skill: PredefinedSkill) => {
    if (existingFiles.length >= MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} files allowed`)
      return
    }

    // Check if skill already exists
    const skillFilename = `skill-${skill.id}.md`
    if (existingFiles.some(f => f.filename === skillFilename)) {
      toast.error('This skill is already added')
      return
    }

    setAddingSkill(skill.id)
    try {
      // Backend fetches skill content from S3
      await apiClient.request('POST', `/api/v1/agents/${agentName}/skills/add`, {
        skill_id: skill.id,
        skill_name: skill.name,
        skill_category: skill.category
      })

      toast.success(`Added "${skill.name}" skill`)
      await loadExistingFiles()
      setShowSkillSelector(false)
      setSkillSearchQuery('')
      setSelectedCategory(null)
    } catch (error) {
      console.error('Failed to add skill:', error)
      toast.error('Failed to add skill')
    } finally {
      setAddingSkill(null)
    }
  }

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    // Handle rejected files
    if (rejectedFiles.length > 0) {
      rejectedFiles.forEach(({ file, errors }) => {
        errors.forEach((error: any) => {
          if (error.code === 'file-too-large') {
            toast.error(`${file.name} is too large. Maximum size is 50MB.`)
          } else if (error.code === 'file-invalid-type') {
            toast.error(`${file.name} has an invalid file type.`)
          } else {
            toast.error(`${file.name}: ${error.message}`)
          }
        })
      })
    }

    // Check total file count (including existing files)
    const totalFiles = existingFiles.length + files.length + acceptedFiles.length
    if (totalFiles > MAX_FILES) {
      toast.error(`You can only have up to ${MAX_FILES} files per agent.`)
      return
    }

    // Add accepted files
    const newFiles: FileWithProgress[] = acceptedFiles.map(file => ({
      file,
      progress: 0,
      status: 'pending' as const,
    }))

    setFiles(prev => [...prev, ...newFiles])
  }, [files.length, existingFiles.length])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    disabled: uploading,
  })

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setUploading(true)
    let successCount = 0
    let errorCount = 0

    try {
      // Upload files one by one
      for (let i = 0; i < files.length; i++) {
        const fileWithProgress = files[i]

        // Update status to uploading
        setFiles(prev => prev.map((f, idx) =>
          idx === i ? { ...f, status: 'uploading' as const } : f
        ))

        try {
          const formData = new FormData()
          formData.append('file', fileWithProgress.file)

          await apiClient.request(
            'POST',
            `/api/v1/agents/${agentName}/context-files/upload`,
            formData,
            {
              headers: {
                'Content-Type': 'multipart/form-data',
              },
              onUploadProgress: (progressEvent: any) => {
                const progress = progressEvent.total
                  ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
                  : 0
                setFiles(prev => prev.map((f, idx) =>
                  idx === i ? { ...f, progress } : f
                ))
              },
            }
          )

          // Mark as success
          setFiles(prev => prev.map((f, idx) =>
            idx === i ? { ...f, status: 'success' as const, progress: 100 } : f
          ))
          successCount++
        } catch (error) {
          // Mark as error
          setFiles(prev => prev.map((f, idx) =>
            idx === i ? {
              ...f,
              status: 'error' as const,
              error: error instanceof Error ? error.message : 'Upload failed'
            } : f
          ))
          errorCount++
        }
      }

      if (successCount > 0) {
        toast.success(`Successfully uploaded ${successCount} file(s)`)

        // Reload existing files
        await loadExistingFiles()

        // Clear uploaded files after a delay
        setTimeout(() => {
          setFiles([])
          onUploadComplete?.()
        }, 2000)
      }

      if (errorCount > 0) {
        toast.error(`Failed to upload ${errorCount} file(s)`)
      }
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (fileId: string) => {
    if (!confirm('Are you sure you want to delete this file?')) {
      return
    }

    try {
      await apiClient.request('DELETE', `/api/v1/agents/context-files/${fileId}`)
      toast.success('File deleted successfully')
      await loadExistingFiles()
    } catch (error) {
      console.error('Failed to delete file:', error)
      toast.error('Failed to delete file')
    }
  }

  const handleDownload = async (fileId: string) => {
    try {
      const response = await apiClient.request('GET', `/api/v1/agents/context-files/${fileId}/download`)
      const downloadUrl = response.download_url

      // Open download URL in new tab
      window.open(downloadUrl, '_blank')
    } catch (error) {
      console.error('Failed to download file:', error)
      toast.error('Failed to download file')
    }
  }

  const handleUpdateFile = async (fileId: string, updates: { load_mode?: 'always' | 'on_demand'; description?: string }) => {
    try {
      await apiClient.request('PATCH', `/api/v1/agents/context-files/${fileId}`, updates)
      setExistingFiles(prev => prev.map(f => f.id === fileId ? { ...f, ...updates } : f))
    } catch (error) {
      console.error('Failed to update file:', error)
      toast.error('Failed to update file')
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getFileIcon = (filename: string) => {
    if (filename.startsWith('skill-')) {
      return <Sparkles className="w-5 h-5 text-red-500" />
    }
    return <FileText className="w-5 h-5 text-blue-600" />
  }

  // Check if file is editable (text formats: .md, .txt, .csv, .docx)
  const isFileEditable = (filename: string): boolean => {
    const lowerFilename = filename.toLowerCase()
    return lowerFilename.endsWith('.md') || lowerFilename.endsWith('.txt') || lowerFilename.endsWith('.csv') || lowerFilename.endsWith('.docx')
  }

  const getStatusIcon = (status: FileWithProgress['status']) => {
    switch (status) {
      case 'uploading':
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-600" />
      default:
        return null
    }
  }

  const getExtractionStatusBadge = (status: ContextFile['extraction_status']) => {
    switch (status) {
      case 'PENDING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-yellow-700 bg-yellow-100 rounded-full">
            <Loader2 className="w-3 h-3 animate-spin" />
            Extracting...
          </span>
        )
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-100 rounded-full">
            <CheckCircle className="w-3 h-3" />
            Ready
          </span>
        )
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded-full">
            <AlertCircle className="w-3 h-3" />
            Failed
          </span>
        )
    }
  }

  return (
    <div className="space-y-6">
      {/* Add Skills Section */}
      {!loading && existingFiles.length < MAX_FILES && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">Add Skills</h3>
            <span className="text-xs text-gray-500">{existingFiles.length}/{MAX_FILES} skills</span>
          </div>

          {/* Two options: Select from library or Upload custom */}
          <div className="grid grid-cols-2 gap-4">
            {/* Select from Library */}
            <button
              onClick={() => setShowSkillSelector(!showSkillSelector)}
              className={`flex items-center justify-center gap-2 p-4 border-2 rounded-xl transition-all ${
                showSkillSelector
                  ? 'border-red-500 bg-red-50 text-red-700'
                  : 'border-gray-200 hover:border-red-300 hover:bg-red-50 text-gray-700'
              }`}
            >
              <Sparkles className="w-5 h-5" />
              <span className="font-medium">Select from Library</span>
              <ChevronDown className={`w-4 h-4 transition-transform ${showSkillSelector ? 'rotate-180' : ''}`} />
            </button>

            {/* Upload Custom Skill - using dropzone */}
            <div
              {...getRootProps()}
              className={`flex items-center justify-center gap-2 p-4 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                isDragActive
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-gray-700'
              } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <input {...getInputProps()} />
              <Upload className="w-5 h-5" />
              <span className="font-medium">Upload Custom Skill</span>
            </div>
          </div>

          {/* Skill Selector Dropdown */}
          {showSkillSelector && (
            <div className="bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
              {/* Search and Filters */}
              <div className="p-4 border-b border-gray-100 bg-gray-50">
                <div className="flex items-center gap-3">
                  {/* Search */}
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={skillSearchQuery}
                      onChange={(e) => {
                        setSkillSearchQuery(e.target.value)
                        setSelectedCategory(null)
                      }}
                      placeholder="Search skills..."
                      className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm"
                    />
                  </div>

                  {/* Category Filters */}
                  <div className="flex items-center gap-1 overflow-x-auto">
                    <button
                      onClick={() => {
                        setSelectedCategory(null)
                        setSkillSearchQuery('')
                      }}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap ${
                        !selectedCategory && !skillSearchQuery
                          ? 'bg-red-100 text-red-700'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      All
                    </button>
                    {SKILL_CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        onClick={() => {
                          setSelectedCategory(cat.id)
                          setSkillSearchQuery('')
                        }}
                        className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1 whitespace-nowrap ${
                          selectedCategory === cat.id
                            ? 'bg-red-100 text-red-700'
                            : 'text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        <span>{cat.icon}</span>
                        {cat.name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Skills List */}
              <div className="max-h-80 overflow-y-auto p-2">
                {filteredSkills.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No skills found</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-2">
                    {filteredSkills.map((skill) => {
                      const isAdded = existingFiles.some(f => f.filename === `skill-${skill.id}.md`)
                      const isAdding = addingSkill === skill.id

                      return (
                        <button
                          key={skill.id}
                          onClick={() => !isAdded && !isAdding && handleAddSkill(skill)}
                          disabled={isAdded || isAdding}
                          className={`flex items-start gap-3 p-3 rounded-lg text-left transition-all ${
                            isAdded
                              ? 'bg-green-50 border border-green-200 cursor-default'
                              : isAdding
                                ? 'bg-gray-50 border border-gray-200 cursor-wait'
                                : 'hover:bg-red-50 border border-transparent hover:border-red-200'
                          }`}
                        >
                          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center text-white text-sm flex-shrink-0">
                            {skill.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-gray-900 text-sm">{skill.name}</span>
                              {isAdded && (
                                <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">Added</span>
                              )}
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{skill.description}</p>
                          </div>
                          {!isAdded && (
                            <div className="flex-shrink-0">
                              {isAdding ? (
                                <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
                              ) : (
                                <Plus className="w-5 h-5 text-gray-400" />
                              )}
                            </div>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="p-3 border-t border-gray-100 bg-gray-50 text-center">
                <p className="text-xs text-gray-500">
                  {PREDEFINED_SKILLS.length} skills available
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Existing Files Section */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 text-red-500 animate-spin" />
        </div>
      ) : existingFiles.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">
              Active Skills ({existingFiles.length}/{MAX_FILES})
            </h3>
          </div>

          <div className="space-y-2">
            {existingFiles.map((file) => (
              <div
                key={file.id}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getFileIcon(file.filename)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {file.filename.startsWith('skill-')
                            ? file.filename.replace('skill-', '').replace('.md', '').split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
                            : file.filename
                          }
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <p className="text-xs text-gray-500">
                            {formatFileSize(file.file_size)}
                          </p>
                          <span className="text-gray-300">•</span>
                          {getExtractionStatusBadge(file.extraction_status)}
                          {file.filename.startsWith('skill-') && (
                            <>
                              <span className="text-gray-300">•</span>
                              <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full">Pre-defined</span>
                            </>
                          )}
                        </div>
                        {file.extraction_status === 'FAILED' && file.extraction_error && (
                          <p className="text-xs text-red-600 mt-1">
                            {file.extraction_error}
                          </p>
                        )}
                        {file.description && (
                          <p className="text-xs text-gray-400 mt-1 line-clamp-1" title={file.description}>
                            {file.description}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-1">
                        {/* Load mode toggle */}
                        <button
                          onClick={() => handleUpdateFile(file.id, { load_mode: file.load_mode === 'always' ? 'on_demand' : 'always' })}
                          title={file.load_mode === 'always' ? 'Always injected — click to make on-demand' : 'On-demand — click to always inject'}
                          className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full transition-colors ${
                            file.load_mode === 'always'
                              ? 'bg-blue-50 text-blue-600 hover:bg-blue-100'
                              : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                          }`}
                        >
                          {file.load_mode === 'always' ? (
                            <><Zap className="w-3 h-3" />Always</>
                          ) : (
                            <><Clock className="w-3 h-3" />On-demand</>
                          )}
                        </button>
                        {isFileEditable(file.filename) && (
                          <button
                            onClick={() => setEditingFile(file)}
                            className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDownload(file.id)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(file.id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium">No skills added yet</p>
          <p className="text-xs mt-1">Select from the library or upload your own skill files</p>
        </div>
      )}

      {/* New Files List (for manual uploads) */}
      {files.length > 0 && (
        <div className="space-y-2 border-t border-gray-200 pt-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">
              Files to Upload ({files.length})
            </h3>
            {!uploading && (
              <button
                onClick={() => setFiles([])}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Clear all
              </button>
            )}
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {files.map((fileWithProgress, index) => (
              <div
                key={index}
                className="bg-white border border-gray-200 rounded-lg p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {fileWithProgress.file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(fileWithProgress.file.size)}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        {getStatusIcon(fileWithProgress.status)}
                        {!uploading && fileWithProgress.status === 'pending' && (
                          <button
                            onClick={() => removeFile(index)}
                            className="text-gray-400 hover:text-gray-600"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {fileWithProgress.status === 'uploading' && (
                      <div className="mt-2">
                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                          <div
                            className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${fileWithProgress.progress}%` }}
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {fileWithProgress.progress}%
                        </p>
                      </div>
                    )}

                    {/* Error Message */}
                    {fileWithProgress.status === 'error' && fileWithProgress.error && (
                      <p className="text-xs text-red-600 mt-1">
                        {fileWithProgress.error}
                      </p>
                    )}

                    {/* Success Message */}
                    {fileWithProgress.status === 'success' && (
                      <p className="text-xs text-green-600 mt-1">
                        Uploaded successfully
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={uploading || files.length === 0 || files.some(f => f.status === 'success')}
            className="w-full px-4 py-3 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium shadow-lg shadow-red-500/30"
          >
            {uploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Upload {files.length} File{files.length !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      )}

      {/* Skill Editor Modal */}
      {editingFile && (
        <SkillEditor
          fileId={editingFile.id}
          filename={editingFile.filename}
          onClose={() => setEditingFile(null)}
          onSave={() => {
            loadExistingFiles()
            setEditingFile(null)
          }}
        />
      )}
    </div>
  )
}
