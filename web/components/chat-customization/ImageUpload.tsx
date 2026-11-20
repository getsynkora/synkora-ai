'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { X, Image as ImageIcon, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import Image from 'next/image'

interface ImageUploadProps {
  label: string
  description?: string
  currentImageUrl?: string | null
  onUpload: (file: File) => Promise<string>
  onRemove?: () => Promise<void>
  maxSize?: number
  aspectRatio?: string
  recommendedSize?: string
}

const MAX_FILE_SIZE = 2 * 1024 * 1024 // 2MB
const ACCEPTED_IMAGE_TYPES = {
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/svg+xml': ['.svg'],
  'image/webp': ['.webp'],
}

export default function ImageUpload({
  label,
  description,
  currentImageUrl,
  onUpload,
  onRemove,
  maxSize = MAX_FILE_SIZE,
  aspectRatio,
  recommendedSize,
}: ImageUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<string | null>(currentImageUrl || null)

  const onDrop = useCallback(async (acceptedFiles: File[], rejectedFiles: any[]) => {
    // Handle rejected files
    if (rejectedFiles.length > 0) {
      rejectedFiles.forEach(({ file, errors }) => {
        errors.forEach((error: any) => {
          if (error.code === 'file-too-large') {
            toast.error(`${file.name} is too large. Maximum size is ${maxSize / 1024 / 1024}MB.`)
          } else if (error.code === 'file-invalid-type') {
            toast.error(`${file.name} must be an image file (PNG, JPG, SVG, or WebP).`)
          } else {
            toast.error(`${file.name}: ${error.message}`)
          }
        })
      })
      return
    }

    if (acceptedFiles.length === 0) return

    const file = acceptedFiles[0]
    
    // Create preview
    const reader = new FileReader()
    reader.onloadend = () => {
      setPreview(reader.result as string)
    }
    reader.readAsDataURL(file)

    // Upload file
    setUploading(true)
    try {
      await onUpload(file)
      toast.success('Image uploaded successfully')
    } catch (error) {
      console.error('Upload error:', error)
      toast.error('Failed to upload image')
      setPreview(currentImageUrl || null)
    } finally {
      setUploading(false)
    }
  }, [currentImageUrl, maxSize, onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_IMAGE_TYPES,
    maxSize,
    maxFiles: 1,
    disabled: uploading,
  })

  const handleRemove = async () => {
    if (!onRemove) return
    
    setUploading(true)
    try {
      await onRemove()
      setPreview(null)
      toast.success('Image removed successfully')
    } catch (error) {
      console.error('Remove error:', error)
      toast.error('Failed to remove image')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-ink-soft">
        {label}
      </label>
      
      {description && (
        <p className="text-sm text-ink-mute">{description}</p>
      )}
      
      {recommendedSize && (
        <p className="text-xs text-ash">Recommended: {recommendedSize}</p>
      )}

      {preview ? (
        <div className="relative">
          <div 
            className="relative border-2 border-line rounded-lg p-4 bg-cream"
            style={aspectRatio ? { aspectRatio } : undefined}
          >
            <div className="relative w-full h-full flex items-center justify-center">
              <Image
                src={preview}
                alt={label}
                width={200}
                height={200}
                className="max-w-full max-h-full object-contain"
                unoptimized={preview.startsWith('data:')}
              />
            </div>
          </div>
          
          {onRemove && (
            <button
              onClick={handleRemove}
              disabled={uploading}
              className="absolute top-2 right-2 p-2 bg-danger text-white rounded-full hover:bg-danger transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
              title="Remove image"
            >
              {uploading ? (
                <Loader2 className="w-4 h-4 motion-safe:animate-spin" />
              ) : (
                <X className="w-4 h-4" />
              )}
            </button>
          )}
          
          <button
            {...getRootProps()}
            disabled={uploading}
            className="mt-2 w-full px-4 py-2 text-sm text-ink-soft bg-white border border-taupe rounded-lg hover:bg-cream transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <input {...getInputProps()} />
            {uploading ? 'Uploading…' : 'Change Image'}
          </button>
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-azure bg-sky-wash'
              : 'border-taupe hover:border-ash bg-cream'
          } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
          style={aspectRatio ? { aspectRatio } : undefined}
        >
          <input {...getInputProps()} />
          
          {uploading ? (
            <Loader2 className="w-12 h-12 text-ash mx-auto mb-4 motion-safe:animate-spin" />
          ) : (
            <ImageIcon className="w-12 h-12 text-ash mx-auto mb-4" />
          )}
          
          {isDragActive ? (
            <p className="text-sm font-medium text-azure">Drop image here…</p>
          ) : uploading ? (
            <p className="text-sm font-medium text-ink-soft">Uploading…</p>
          ) : (
            <>
              <p className="text-sm font-medium text-ink mb-1">
                Drag & drop an image here, or click to select
              </p>
              <p className="text-xs text-ink-mute">
                PNG, JPG, SVG, or WebP (max {maxSize / 1024 / 1024}MB)
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}