import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import type { QuerySource } from '@shared/types'
import { buildSourceIndexMap, splitByCitations } from '../lib/markdown'
import CitationPill from './CitationPill'

interface MarkdownAnswerProps {
  content: string
  sources?: QuerySource[]
}

export default function MarkdownAnswer({ content, sources }: MarkdownAnswerProps) {
  const parts = splitByCitations(content)
  const indexMap = buildSourceIndexMap(sources ?? [])

  return (
    <div className="prose-chat">
      {parts.map((part, i) => {
        if (part.type === 'citation') {
          const src = sources?.find((s) => s.id === part.chunkId)
          const refNum = indexMap.get(part.chunkId)
          return (
            <CitationPill
              key={`cite-${i}`}
              chunkId={part.chunkId}
              source={src}
              refNum={refNum}
            />
          )
        }
        if (!part.value.trim()) return null
        return (
          <ReactMarkdown
            key={`md-${i}`}
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeSanitize]}
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {part.value}
          </ReactMarkdown>
        )
      })}
    </div>
  )
}
