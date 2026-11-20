'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

interface FileWithProgress {
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
}

interface FileUploadProps {
  onUploadComplete: () => void
  onUpload: (files: File[], onProgress: (progress: number) => void) => Promise<any>
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
const MAX_FILES = 10

export default function FileUpload({ onUploadComplete, onUpload }: FileUploadProps) {
  const [files, setFiles] = useState<FileWithProgress[]>([])
  const [uploading, setUploading] = useState(false)

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

    // Check total file count
    if (files.length + acceptedFiles.length > MAX_FILES) {
      toast.error(`You can only upload up to ${MAX_FILES} files at once.`)
      return
    }

    // Add accepted files
    const newFiles: FileWithProgress[] = acceptedFiles.map(file => ({
      file,
      progress: 0,
      status: 'pending' as const,
    }))

    setFiles(prev => [...prev, ...newFiles])
  }, [files.length])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles: MAX_FILES,
    disabled: uploading,
  })

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setUploading(true)

    try {
      // Update all files to uploading status
      setFiles(prev => prev.map(f => ({ ...f, status: 'uploading' as const })))

      // Upload files
      const filesToUpload = files.map(f => f.file)

      const result = await onUpload(filesToUpload, (progress) => {
        // Update progress for all files
        setFiles(prev => prev.map(f => ({ ...f, progress })))
      })

      // Build a map of filename → error from failed_files
      const failedMap: Record<string, string> = {}
      if (result?.failed_files?.length) {
        for (const f of result.failed_files) {
          if (f.filename) failedMap[f.filename] = f.error || 'Rejected by server'
        }
      }

      // Mark each file success or error based on server response
      setFiles(prev => prev.map(f => {
        const serverError = failedMap[f.file.name]
        if (serverError) {
          return { ...f, status: 'error' as const, progress: 100, error: serverError }
        }
        return { ...f, status: 'success' as const, progress: 100 }
      }))

      const successCount = filesToUpload.length - Object.keys(failedMap).length
      const failCount = Object.keys(failedMap).length

      if (successCount > 0) {
        toast.success(`Successfully uploaded ${successCount} file${successCount !== 1 ? 's' : ''}`)
      }
      if (failCount > 0) {
        const names = Object.keys(failedMap).join(', ')
        toast.error(`${failCount} file${failCount !== 1 ? 's' : ''} rejected: ${names}`)
      }

      // Clear only successful files after a delay; keep failed ones visible
      if (successCount > 0) {
        setTimeout(() => {
          setFiles(prev => prev.filter(f => f.status === 'error'))
          onUploadComplete()
        }, 2000)
      }
    } catch (error) {
      // Mark all as error
      setFiles(prev => prev.map(f => ({
        ...f,
        status: 'error' as const,
        error: error instanceof Error ? error.message : 'Upload failed'
      })))

      toast.error('Failed to upload files')
    } finally {
      setUploading(false)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getFileIcon = () => {
    return <FileText className="w-5 h-5 text-leaf" />
  }

  const getStatusIcon = (status: FileWithProgress['status']) => {
    switch (status) {
      case 'uploading':
        return <Loader2 className="w-5 h-5 text-leaf motion-safe:animate-spin" />
      case 'success':
        return <CheckCircle className="w-5 h-5 text-leaf" />
      case 'error':
        return <AlertCircle className="w-5 h-5 text-danger" />
      default:
        return null
    }
  }

  return (
    <div className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-[1.5rem] border-2 border-dashed p-8 text-center transition-colors ${
          isDragActive
            ? 'border-leaf bg-leaf-wash'
            : 'border-black/10 bg-white hover:border-black/20 hover:bg-paper'
        } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto mb-4 h-12 w-12 text-ash" />
        {isDragActive ? (
          <p className="text-lg font-medium text-leaf">Drop files here…</p>
        ) : (
          <>
            <p className="text-lg font-medium text-ink mb-2">
              Drag & drop files here, or click to select
            </p>
            <p className="text-sm text-ink-mute mb-4">
              Supported formats: PDF, DOCX, TXT, MD, HTML, CSV
            </p>
            <p className="text-xs text-ash">
              Maximum {MAX_FILES} files, 50MB per file
            </p>
          </>
        )}
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-ink">
              Selected Files ({files.length})
            </h3>
            {!uploading && (
              <button
                onClick={() => setFiles([])}
                className="text-sm text-ink-mute transition-colors hover:text-ink"
              >
                Clear all
              </button>
            )}
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {files.map((fileWithProgress, index) => (
              <div
                key={index}
                className="rounded-[1.15rem] border border-black/10 bg-white/90 p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getFileIcon()}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-ink truncate">
                          {fileWithProgress.file.name}
                        </p>
                        <p className="text-xs text-ink-mute">
                          {formatFileSize(fileWithProgress.file.size)}
                        </p>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {getStatusIcon(fileWithProgress.status)}
                        {!uploading && fileWithProgress.status === 'pending' && (
                          <button
                            onClick={() => removeFile(index)}
                            className="text-ash transition-colors hover:text-ink"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {fileWithProgress.status === 'uploading' && (
                      <div className="mt-2">
                        <div className="h-1.5 w-full rounded-full bg-line">
                          <div
                            className="h-1.5 rounded-full bg-leaf transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-300"
                            style={{ width: `${fileWithProgress.progress}%` }}
                          />
                        </div>
                        <p className="text-xs text-ink-mute mt-1">
                          {fileWithProgress.progress}%
                        </p>
                      </div>
                    )}

                    {/* Error Message */}
                    {fileWithProgress.status === 'error' && fileWithProgress.error && (
                      <p className="text-xs text-danger mt-1">
                        {fileWithProgress.error}
                      </p>
                    )}

                    {/* Success Message */}
                    {fileWithProgress.status === 'success' && (
                      <p className="text-xs text-leaf mt-1">
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
            className="flex w-full items-center justify-center gap-2 rounded-[1rem] bg-ink px-4 py-3 font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 className="w-5 h-5 motion-safe:animate-spin" />
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
    </div>
  )
}
