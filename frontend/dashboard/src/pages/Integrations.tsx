import { useEffect, useState } from 'react'
import { Link2 } from 'lucide-react'
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
      <h1 className="text-2xl font-bold mb-6">Integrations</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-lg bg-surface-2 flex items-center justify-center text-xl">📝</div>
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
            <div className="h-10 w-10 rounded-lg bg-surface-2 flex items-center justify-center text-xl">📁</div>
            <div><h3 className="font-semibold">Google Drive</h3><p className="text-xs text-muted">Coming soon</p></div>
          </div>
          <Button disabled className="w-full">Connect</Button>
        </Card>
        <Card className="p-6 opacity-60">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-lg bg-surface-2 flex items-center justify-center text-xl">🌐</div>
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
