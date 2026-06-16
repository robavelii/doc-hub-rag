import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useTenantStore } from '../store/tenantStore'
import api from '../lib/api'
import { Button, Card, Input, Skeleton, Textarea } from '../components/ui'
import { copyText } from '../lib/copy'
import { useToast } from '../components/ui'

export default function Widget() {
  const storedApiKey = useAuthStore((s) => s.apiKey)
  const [apiKey, setApiKey] = useState(storedApiKey ?? '')
  const { widgetConfig, fetchWidgetConfig, updateWidgetConfig } = useTenantStore()
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(true)
  const [primaryColor, setPrimaryColor] = useState('#1D9E75')
  const [welcomeMessage, setWelcomeMessage] = useState('Hi! How can I help you today?')
  const [domains, setDomains] = useState('')
  const [position, setPosition] = useState('bottom-right')
  const previewRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    void fetchWidgetConfig().then((c) => {
      setPrimaryColor(c.primary_color)
      setWelcomeMessage(c.welcome_message)
      setDomains((c.allowed_domains ?? []).join('\n'))
      setPosition(c.position ?? 'bottom-right')
      setLoading(false)
    })
  }, [fetchWidgetConfig])

  useEffect(() => {
    if (storedApiKey) {
      setApiKey(storedApiKey)
      return
    }
    void api.get<Array<{ api_key?: string }>>('/api-keys').then(() => {
      /* keys are masked — user copies from Settings or registration */
    })
  }, [storedApiKey])

  const widgetCdn = import.meta.env.VITE_WIDGET_CDN_URL || 'http://localhost:3002/widget.js'
  const apiBase = window.location.origin.includes('localhost') ? 'http://localhost:8000' : `${window.location.origin}/api`.replace('/api', '')
  const embedCode = `<!-- Doc-Hub Widget -->
<div id="my-assistant"></div>
<script src="${widgetCdn}"></script>
<script>
  RAGWidget.init({
    apiKey: '${apiKey || 'YOUR_API_KEY'}',
    containerId: 'my-assistant',
    primaryColor: '${primaryColor}',
    apiBase: '${apiBase}'
  })
</script>`

  useEffect(() => {
    const container = previewRef.current
    if (!container || !apiKey) return
    container.innerHTML = '<div id="widget-preview-root"></div>'
    const script = document.createElement('script')
    script.src = widgetCdn
    script.onload = () => {
      const w = window as Window & { RAGWidget?: { init: (opts: Record<string, string>) => void } }
      w.RAGWidget?.init({
        apiKey,
        containerId: 'widget-preview-root',
        primaryColor,
        apiBase,
      })
    }
    document.body.appendChild(script)
    return () => {
      script.remove()
      container.innerHTML = ''
    }
  }, [apiKey, primaryColor, widgetCdn, apiBase])

  const handleSave = async () => {
    await updateWidgetConfig({
      primary_color: primaryColor,
      welcome_message: welcomeMessage,
      allowed_domains: domains.split('\n').map((d) => d.trim()).filter(Boolean),
      position,
    })
    toast('success', 'Widget config saved')
  }

  const handleCopy = async () => {
    const ok = await copyText(embedCode)
    if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000) }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Widget Configuration</h1>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <Card className="p-6 space-y-4">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : (
              <>
                <div>
                  <label className="text-xs text-muted mb-1 block">API key for embed</label>
                  <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Paste API key from Settings" />
                </div>
                <div>
                  <label className="text-xs text-muted mb-1 block">Primary color</label>
                  <div className="flex gap-2">
                    <input type="color" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} className="h-10 w-14 rounded cursor-pointer" />
                    <Input value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted mb-1 block">Welcome message</label>
                  <Textarea value={welcomeMessage} onChange={(e) => setWelcomeMessage(e.target.value)} rows={2} />
                </div>
                <div>
                  <label className="text-xs text-muted mb-1 block">Allowed domains (one per line)</label>
                  <Textarea value={domains} onChange={(e) => setDomains(e.target.value)} rows={3} placeholder="example.com" />
                </div>
                <div>
                  <label className="text-xs text-muted mb-1 block">Position</label>
                  <select value={position} onChange={(e) => setPosition(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm">
                    <option value="bottom-right">Bottom right</option>
                    <option value="bottom-left">Bottom left</option>
                  </select>
                </div>
                <Button onClick={() => void handleSave()}>Save configuration</Button>
              </>
            )}
          </Card>
          <Card>
            <div className="p-4">
              <div className="flex justify-between items-center mb-2">
                <p className="text-sm font-medium">Embed code</p>
                <Button variant="ghost" size="sm" onClick={() => void handleCopy()}>
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                </Button>
              </div>
              <pre className="bg-bg rounded-md p-4 overflow-auto text-xs border border-border">{embedCode}</pre>
            </div>
          </Card>
        </div>
        <Card className="p-4">
          <p className="text-sm font-medium mb-4">Live preview</p>
          <div className="relative mx-auto w-full max-w-[320px] h-[500px] rounded-3xl border-4 border-border bg-bg overflow-hidden">
            <div className="h-8 bg-surface flex items-center justify-center text-[10px] text-muted">preview.local</div>
            <div ref={previewRef} className="relative h-[calc(100%-2rem)]" />
            {!apiKey && (
              <p className="absolute inset-0 flex items-center justify-center text-xs text-muted p-4 text-center">
                Add an API key to load the live widget preview
              </p>
            )}
          </div>
          {widgetConfig?.tenant_name && (
            <p className="text-xs text-muted mt-2 text-center">Tenant: {widgetConfig.tenant_name}</p>
          )}
        </Card>
      </div>
    </div>
  )
}
