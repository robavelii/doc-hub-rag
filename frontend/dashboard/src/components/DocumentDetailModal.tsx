import { useEffect, useState } from 'react'
import type { DocumentItem } from '@shared/types'
import api from '../lib/api'
import { Modal, Skeleton } from './ui'
import DocStatusBadge from './DocStatusBadge'

interface ChunkPreview {
  id: string
  chunk_index: number
  text_preview: string
  filename: string
}

interface Props {
  docId: string | null
  onClose: () => void
}

export default function DocumentDetailModal({ docId, onClose }: Props) {
  const [doc, setDoc] = useState<DocumentItem | null>(null)
  const [chunks, setChunks] = useState<ChunkPreview[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!docId) return
    setLoading(true)
    void Promise.all([
      api.get<DocumentItem>(`/documents/${docId}`),
      api.get<ChunkPreview[]>(`/documents/${docId}/chunks`),
    ])
      .then(([docRes, chunksRes]) => {
        setDoc(docRes.data)
        setChunks(chunksRes.data)
      })
      .finally(() => setLoading(false))
  }, [docId])

  return (
    <Modal open={!!docId} onClose={onClose} title="Document details">
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : doc ? (
        <div className="space-y-4 text-sm">
          <div>
            <p className="text-muted text-xs mb-1">Filename</p>
            <p className="font-medium">{doc.filename}</p>
          </div>
          <div className="flex gap-4">
            <div>
              <p className="text-muted text-xs mb-1">Status</p>
              <DocStatusBadge status={doc.status} />
            </div>
            <div>
              <p className="text-muted text-xs mb-1">Chunks</p>
              <p>{doc.chunk_count}</p>
            </div>
            <div>
              <p className="text-muted text-xs mb-1">Size</p>
              <p>{(doc.size_bytes / 1024).toFixed(1)} KB</p>
            </div>
          </div>
          {doc.created_at && (
            <div>
              <p className="text-muted text-xs mb-1">Uploaded</p>
              <p>{new Date(doc.created_at).toLocaleString()}</p>
            </div>
          )}
          {doc.error_message && (
            <div className="rounded-lg bg-danger/10 border border-danger/20 p-3 text-danger text-xs">
              {doc.error_message}
            </div>
          )}
          {chunks.length > 0 && (
            <div>
              <p className="text-muted text-xs mb-2">Chunk preview</p>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {chunks.map((c) => (
                  <div key={c.id} className="rounded-lg bg-bg border border-border p-2 text-xs">
                    <span className="text-muted">#{c.chunk_index}</span>
                    <p className="mt-1 text-muted line-clamp-3">{c.text_preview}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  )
}
