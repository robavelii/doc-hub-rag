import { useCallback, useEffect, useMemo, useState } from 'react'
import { File, Grid, List, RefreshCw, Trash2 } from 'lucide-react'
import type { DocumentItem } from '@shared/types'
import api from '../lib/api'
import UploadZone from '../components/UploadZone'
import DocStatusBadge from '../components/DocStatusBadge'
import DocumentDetailModal from '../components/DocumentDetailModal'
import { Button, Card, CardHeader, CardTitle, EmptyState, Input, Modal, Skeleton, useToast } from '../components/ui'
import UsageBar from '../components/UsageBar'
import type { UsageSummary } from '@shared/types'

type ViewMode = 'list' | 'grid'
type SortKey = 'filename' | 'created_at' | 'status' | 'size_bytes'

const FILE_ICONS: Record<string, string> = { pdf: '📕', docx: '📘', txt: '📄', url: '🔗' }

export default function Documents() {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [view, setView] = useState<ViewMode>('list')
  const [sort, setSort] = useState<SortKey>('created_at')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [detailId, setDetailId] = useState<string | null>(null)
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [confirmSingleId, setConfirmSingleId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [reingesting, setReingesting] = useState<Set<string>>(new Set())
  const { toast } = useToast()

  const loadDocs = useCallback(async () => {
    const [{ data: docData }, { data: usageData }] = await Promise.all([
      api.get<DocumentItem[]>('/documents'),
      api.get<UsageSummary>('/usage/summary'),
    ])
    setDocs(docData)
    setUsage(usageData)
    setLoading(false)
  }, [])

  useEffect(() => { void loadDocs() }, [loadDocs])

  useEffect(() => {
    const hasPending = docs.some((d) => d.status === 'pending' || d.status === 'processing')
    if (!hasPending) return
    const interval = setInterval(() => void loadDocs(), 3000)
    return () => clearInterval(interval)
  }, [docs, loadDocs])

  const filtered = useMemo(() => {
    let result = docs.filter((d) => d.filename.toLowerCase().includes(search.toLowerCase()))
    if (statusFilter !== 'all') result = result.filter((d) => d.status === statusFilter)
    result = [...result].sort((a, b) => {
      if (sort === 'filename') return a.filename.localeCompare(b.filename)
      if (sort === 'status') return a.status.localeCompare(b.status)
      if (sort === 'size_bytes') return b.size_bytes - a.size_bytes
      return (b.created_at ?? '').localeCompare(a.created_at ?? '')
    })
    return result
  }, [docs, search, sort, statusFilter])

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleDelete = async (id: string) => {
    await api.delete(`/documents/${id}`)
    toast('success', 'Document deleted')
    void loadDocs()
  }

  const handleBulkDelete = async () => {
    await Promise.all([...selected].map((id) => api.delete(`/documents/${id}`)))
    setSelected(new Set())
    setConfirmBulk(false)
    toast('success', 'Documents deleted')
    void loadDocs()
  }

  const handleReingest = async (id: string) => {
    setReingesting((prev) => new Set(prev).add(id))
    try {
      await api.post(`/documents/${id}/reingest`)
      void loadDocs()
    } finally {
      setReingesting((prev) => { const n = new Set(prev); n.delete(id); return n })
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Documents</h1>
      {usage && (
        <div className="mb-6">
          <UsageBar label="Storage" used={usage.storage_used_bytes} limit={usage.storage_limit_bytes} />
        </div>
      )}
      <UploadZone onUploadComplete={() => void loadDocs()} />

      <Card className="mt-8">
        <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap">
          <CardTitle>Your Documents</CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <Input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-48" />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm">
              <option value="all">All statuses</option>
              <option value="ready">Ready</option>
              <option value="processing">Processing</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm">
              <option value="created_at">Date</option>
              <option value="filename">Name</option>
              <option value="status">Status</option>
              <option value="size_bytes">Size</option>
            </select>
            <Button variant="ghost" size="sm" onClick={() => setView('list')}><List size={16} /></Button>
            <Button variant="ghost" size="sm" onClick={() => setView('grid')}><Grid size={16} /></Button>
            {selected.size > 0 && (
              <Button variant="danger" size="sm" onClick={() => setConfirmBulk(true)}>
                Delete ({selected.size})
              </Button>
            )}
          </div>
        </CardHeader>

        {loading ? (
          <div className="space-y-2 p-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No documents" description="Upload your first document to get started." />
        ) : view === 'grid' ? (
          <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((d) => (
              <div key={d.id} className="glass rounded-xl p-4 cursor-pointer hover:border-primary/30" onClick={() => setDetailId(d.id)}>
                <div className="flex items-start gap-3">
                  <input type="checkbox" checked={selected.has(d.id)} onChange={() => toggleSelect(d.id)} onClick={(e) => e.stopPropagation()} />
                  <span className="text-2xl">{FILE_ICONS[d.file_type] ?? <File size={20} />}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{d.filename}</p>
                    <DocStatusBadge status={d.status} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="py-2 px-4 w-8" />
                  <th className="py-2 pr-4 font-medium">Filename</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Chunks</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => (
                  <tr key={d.id} className="border-b border-border last:border-0 hover:bg-surface-2/30">
                    <td className="py-3 px-4"><input type="checkbox" checked={selected.has(d.id)} onChange={() => toggleSelect(d.id)} /></td>
                    <td className="py-3 pr-4 cursor-pointer" onClick={() => setDetailId(d.id)}>
                      <span className="mr-2">{FILE_ICONS[d.file_type] ?? '📄'}</span>
                      <span className="font-medium">{d.filename}</span>
                    </td>
                    <td className="py-3 pr-4"><DocStatusBadge status={d.status} /></td>
                    <td className="py-3 pr-4 text-muted">{d.chunk_count}</td>
                    <td className="py-3">
                      <div className="flex gap-2">
                        <Button variant="secondary" size="sm" onClick={() => void handleReingest(d.id)} disabled={reingesting.has(d.id)}>
                          <RefreshCw size={14} className={reingesting.has(d.id) ? 'animate-spin' : ''} />
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => setConfirmSingleId(d.id)} aria-label={`Delete ${d.filename}`}>
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <DocumentDetailModal docId={detailId} onClose={() => setDetailId(null)} />
      <Modal open={!!confirmSingleId} onClose={() => setConfirmSingleId(null)} title="Delete document?">
        <p className="text-sm text-muted mb-4">This cannot be undone.</p>
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={() => setConfirmSingleId(null)}>Cancel</Button>
          <Button
            variant="danger"
            onClick={() => {
              if (confirmSingleId) void handleDelete(confirmSingleId).then(() => setConfirmSingleId(null))
            }}
          >
            Delete
          </Button>
        </div>
      </Modal>
      <Modal open={confirmBulk} onClose={() => setConfirmBulk(false)} title="Delete documents?">
        <p className="text-sm text-muted mb-4">Delete {selected.size} selected document(s)? This cannot be undone.</p>
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={() => setConfirmBulk(false)}>Cancel</Button>
          <Button variant="danger" onClick={() => void handleBulkDelete()}>Delete</Button>
        </div>
      </Modal>
    </div>
  )
}
