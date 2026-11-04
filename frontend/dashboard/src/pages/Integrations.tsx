import { useEffect, useState } from 'react'
import { FolderOpen, Globe, Link2, NotebookText } from 'lucide-react'
import api from '../lib/api'
import { Button, Card, EmptyState } from '../components/ui'

interface IntegrationStatus {
  connected: string[]
}

export default function Integrations() {
  const [status, setStatus] = useState<IntegrationStatus>({ connected: [] })

  useEffect(() => {
    void api.get<IntegrationStatus>('/integrations/status').then(({ data }) => setStatus(data)).catch(() => {})
  }, [])

  const connectNotion = () => {
    window.location.href = '/api/integrations/notion/connect'
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Integrations</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-secondary" aria-hidden="true"><NotebookText size={20} /></div>
            <div>
              <h3 className="font-semibold">Notion</h3>
              <p className="text-xs text-muted">{status.connected?.includes('notion') ? 'Connected' : 'Not connected'}</p>
            </div>
          </div>
          <Button onClick={connectNotion} variant={status.connected?.includes('notion') ? 'secondary' : 'primary'} className="w-full">
            <Link2 size={16} />
            {status.connected?.includes('notion') ? 'Reconnect' : 'Connect'}
          </Button>
        </Card>
        <Card className="p-6 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-secondary" aria-hidden="true"><FolderOpen size={20} /></div>
            <div><h3 className="font-semibold">Google Drive</h3><p className="text-xs text-muted">Coming soon</p></div>
          </div>
          <Button disabled className="w-full">Connect</Button>
        </Card>
        <Card className="p-6 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-secondary" aria-hidden="true"><Globe size={20} /></div>
            <div><h3 className="font-semibold">Web Crawler</h3><p className="text-xs text-muted">Coming soon</p></div>
          </div>
          <Button disabled className="w-full">Connect</Button>
        </Card>
      </div>
      {!status.connected?.includes('notion') && (
        <div className="mt-8">
          <EmptyState title="Connect your tools" description="Sync documents from Notion and other sources automatically." />
        </div>
      )}
    </div>
  )
}
