'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api/client'

export interface DataFileUploadResult {
  s3Url: string
  s3Key: string
  filename: string
}

export interface DataFileUploadState {
  progress: number          // 0–100
  status: 'idle' | 'uploading' | 'done' | 'error'
  error: string | null
}

const ALLOWED_EXTENSIONS = /\.(csv|tsv|json|parquet|ndjson|jsonl)$/i

const CONTENT_TYPE_MAP: Record<string, string> = {
  csv: 'text/csv',
  tsv: 'text/tab-separated-values',
  json: 'application/json',
  ndjson: 'application/json',
  jsonl: 'application/json',
  parquet: 'application/octet-stream',
}

function getContentType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  return CONTENT_TYPE_MAP[ext] ?? 'application/octet-stream'
}

export function useDataFileUpload() {
  const [state, setState] = useState<DataFileUploadState>({
    progress: 0,
    status: 'idle',
    error: null,
  })

  const reset = () => setState({ progress: 0, status: 'idle', error: null })

  const upload = async (file: File): Promise<DataFileUploadResult> => {
    if (!ALLOWED_EXTENSIONS.test(file.name)) {
      throw new Error('Unsupported file type. Allowed: CSV, TSV, JSON, Parquet, NDJSON')
    }

    setState({ progress: 0, status: 'uploading', error: null })

    // 1. Get presigned PUT URL from backend
    const contentType = getContentType(file.name)
    const { upload_url, s3_key, s3_url } = await apiClient.getAnalysisUploadUrl(
      file.name,
      contentType
    )

    // 2. Upload file directly to S3 via XHR for progress tracking
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100)
          setState((prev) => ({ ...prev, progress: pct }))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`))
        }
      })

      xhr.addEventListener('error', () => reject(new Error('Network error during upload')))
      xhr.addEventListener('abort', () => reject(new Error('Upload aborted')))

      xhr.open('PUT', upload_url)
      xhr.setRequestHeader('Content-Type', contentType)
      xhr.send(file)
    })

    setState({ progress: 100, status: 'done', error: null })

    return { s3Url: s3_url, s3Key: s3_key, filename: file.name }
  }

  const uploadWithErrorHandling = async (file: File): Promise<DataFileUploadResult | null> => {
    try {
      return await upload(file)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setState({ progress: 0, status: 'error', error: msg })
      return null
    }
  }

  return { upload: uploadWithErrorHandling, state, reset }
}
