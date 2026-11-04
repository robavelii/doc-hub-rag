export const CITATION_PATTERN = /\[source:([^\]]+)\]/g

export type ContentPart =
  | { type: 'text'; value: string }
  | { type: 'citation'; chunkId: string }

export function splitByCitations(content: string): ContentPart[] {
  const parts: ContentPart[] = []
  let lastIndex = 0
  const regex = new RegExp(CITATION_PATTERN.source, 'g')
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.slice(lastIndex, match.index) })
    }
    const chunkId = match[1]
    if (chunkId) parts.push({ type: 'citation', chunkId })
    lastIndex = regex.lastIndex
  }

  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.slice(lastIndex) })
  }

  return parts
}

const CITE_HREF_PREFIX = '#cite-'

// Turns [source:<id>] into an inline markdown link so the whole answer renders as one
// markdown tree and citations sit inside their sentence instead of breaking it.
export function citationsToLinks(content: string): string {
  return content.replace(new RegExp(CITATION_PATTERN.source, 'g'), (_m, id: string) => `[cite](${CITE_HREF_PREFIX}${encodeURIComponent(id)})`)
}

export function citationId(href: string | undefined): string | null {
  if (!href?.startsWith(CITE_HREF_PREFIX)) return null
  return decodeURIComponent(href.slice(CITE_HREF_PREFIX.length))
}

export function buildSourceIndexMap(sources: { id: string }[]): Map<string, number> {
  const map = new Map<string, number>()
  sources.forEach((s, i) => {
    if (!map.has(s.id)) map.set(s.id, i + 1)
  })
  return map
}

export function stripCitations(content: string): string {
  return content.replace(CITATION_PATTERN, '').trim()
}
