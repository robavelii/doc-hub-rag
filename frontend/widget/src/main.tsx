import { createRoot } from 'react-dom/client'
import Widget from './Widget'
import './widget.css'
import type { WidgetInitOptions } from '@shared/types'

interface WidgetConfigResponse {
  primary_color?: string
  welcome_message?: string
  position?: string
  tenant_name?: string
}

async function fetchWidgetConfig(apiKey: string, apiBase: string): Promise<WidgetConfigResponse> {
  try {
    const res = await fetch(`${apiBase.replace(/\/$/, '')}/widget/config`, {
      headers: { 'X-API-Key': apiKey },
    })
    if (res.ok) return (await res.json()) as WidgetConfigResponse
  } catch {
    /* use init defaults */
  }
  return {}
}

window.RAGWidget = {
  async init({ apiKey, containerId, primaryColor = '#1D9E75', apiBase = 'http://localhost:8000' }: WidgetInitOptions) {
    const container = document.getElementById(containerId)
    if (!container) {
      console.error(`RAGWidget: no element with id "${containerId}"`)
      return
    }

    const config = await fetchWidgetConfig(apiKey, apiBase)
    createRoot(container).render(
      <Widget
        apiKey={apiKey}
        primaryColor={config.primary_color ?? primaryColor}
        welcomeMessage={config.welcome_message ?? 'Hi! How can I help you today?'}
        position={config.position ?? 'bottom-right'}
        tenantName={config.tenant_name}
        apiBase={apiBase}
      />
    )
  },
}
