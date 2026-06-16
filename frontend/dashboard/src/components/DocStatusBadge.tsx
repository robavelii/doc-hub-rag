import type { DocumentStatus } from '@shared/types'
import { Badge } from './ui'

const statusVariant: Record<DocumentStatus, 'default' | 'info' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  processing: 'info',
  ready: 'success',
  failed: 'danger',
}

export default function DocStatusBadge({ status }: { status: DocumentStatus }) {
  return <Badge variant={statusVariant[status]}>{status}</Badge>
}
