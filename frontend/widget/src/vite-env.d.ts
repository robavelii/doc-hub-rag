/// <reference types="vite/client" />

import type { WidgetInitOptions } from '@shared/types'

declare global {
  interface Window {
    RAGWidget: {
      init: (opts: WidgetInitOptions) => void
    }
  }
}

export {}
