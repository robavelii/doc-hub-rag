import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'
import type { DocumentItem, DocumentUploadResponse, UploadProgress } from '@shared/types'
import api from '../lib/api'
import { Badge } from './ui'
import { cn } from '../lib/cn'

interface UploadZoneProps {
  onUploadComplete?: (doc: DocumentItem) => void
}

const statusVariant: Record<string, 'default' | 'info' | 'success' | 'warning' | 'danger'> = {
  uploading: 'info',
  processing: 'warning',
  ready: 'success',
  failed: 'danger',
  error: 'danger',
}

export default function UploadZone({ onUploadComplete }: UploadZoneProps) {
  const [uploads, setUploads] = useState<UploadProgress[]>([])
  const [url, setUrl] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)

  const pollStatus = useCallback(
    async (_uploadId: string, docId: string) => {
      const interval = setInterval(async () => {
        try {
          const { data } = await api.get<DocumentItem>(`/documents/${docId}`)
          if (data.status === 'ready') {
            setUploads((prev) =>
              prev.map((u) => (u.docId === docId ? { ...u, status: 'ready' } : u))
            )
            clearInterval(interval)
            onUploadComplete?.(data)
          } else if (data.status === 'failed') {
            setUploads((prev) =>
              prev.map((u) =>
                u.docId === docId
                  ? { ...u, status: 'failed', error: data.error_message ?? undefined }
                  : u
              )
            )
            clearInterval(interval)
          }
        } catch {
          clearInterval(interval)
        }
      }, 2000)
    },
    [onUploadComplete]
  )

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        const id = Math.random().toString(36).slice(2)
        setUploads((prev) => [...prev, { id, name: file.name, status: 'uploading' }])
        const form = new FormData()
        form.append('file', file)
        try {
          const { data } = await api.post<DocumentUploadResponse>('/documents', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          setUploads((prev) =>
            prev.map((u) =>
              u.id === id ? { ...u, status: 'processing', docId: data.id } : u
            )
          )
          void pollStatus(id, data.id)
        } catch (err: unknown) {
          const message =
            err && typeof err === 'object' && 'response' in err
              ? String((err as { response?: { data?: { detail?: string } } }).response?.data?.detail)
              : 'Upload failed'
          setUploads((prev) =>
            prev.map((u) => (u.id === id ? { ...u, status: 'error', error: message } : u))
          )
        }
      }
    },
    [pollStatus]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => void onDrop(files),
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxSize: 50 * 1024 * 1024,
  })

  const ingestUrl = async () => {
    if (!url.trim()) return
    setUrlLoading(true)
    try {
      const { data } = await api.post<DocumentUploadResponse>('/documents/url', { url: url.trim() })
      setUploads((prev) => [...prev, { id: data.id, name: url, status: 'processing', docId: data.id }])
      void pollStatus(data.id, data.id)
      setUrl('')
    } finally {
      setUrlLoading(false)
    }
  }

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input
          type="url"
          placeholder="Or paste a URL to ingest..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
        />
        <button
          onClick={() => void ingestUrl()}
          disabled={urlLoading || !url.trim()}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-bg disabled:opacity-50"
        >
          Ingest URL
        </button>
      </div>
      <div
        {...getRootProps()}
        className={cn(
          'rounded-lg border-2 border-dashed border-border p-8 text-center cursor-pointer transition-colors',
          isDragActive ? 'border-primary bg-primary/5' : 'hover:border-primary/40 hover:bg-surface-2'
        )}
      >
        <input {...getInputProps()} />
        <Upload size={32} className="mx-auto mb-3 text-muted" />
        <p className="text-sm">Drop PDF, DOCX, or TXT files here, or click to select</p>
        <p className="text-xs text-muted mt-1">Max 50MB per file</p>
      </div>
      {uploads.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploads.map((u) => (
            <div key={u.id} className="flex items-center gap-3 text-sm">
              <span className="truncate flex-1">{u.name}</span>
              <Badge variant={statusVariant[u.status] ?? 'default'}>{u.status}</Badge>
              {u.error && <span className="text-danger text-xs">{u.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
