import { create } from 'zustand'
import type { WidgetConfig } from '@shared/types'
import api from '../lib/api'

interface TenantState {
  widgetConfig: WidgetConfig | null
  fetchWidgetConfig: () => Promise<WidgetConfig>
  updateWidgetConfig: (config: Partial<WidgetConfig>) => Promise<WidgetConfig>
}

export const useTenantStore = create<TenantState>((set) => ({
  widgetConfig: null,

  fetchWidgetConfig: async () => {
    const { data } = await api.get<WidgetConfig>('/widget/config')
    set({ widgetConfig: data })
    return data
  },

  updateWidgetConfig: async (config) => {
    const { data } = await api.put<WidgetConfig>('/widget/config', config)
    set({ widgetConfig: data })
    return data
  },
}))
