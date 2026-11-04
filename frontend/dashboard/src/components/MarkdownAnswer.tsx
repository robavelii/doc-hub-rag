import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import type { QuerySource } from '@shared/types'
import { buildSourceIndexMap, citationId, citationsToLinks } from '../lib/markdown'
import CitationPill from './CitationPill'

interface MarkdownAnswerProps {
  content: string
  sources?: QuerySource[]
}

export default function MarkdownAnswer({ content, sources }: MarkdownAnswerProps) {
  const indexMap = buildSourceIndexMap(sources ?? [])

  return (
    <div className="prose-chat">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ href, children }) => {
            const chunkId = citationId(href)
            if (chunkId) {
              return <CitationPill chunkId={chunkId} source={sources?.find((s) => s.id === chunkId)} refNum={indexMap.get(chunkId)} />
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            )
          },
        }}
      >
        {citationsToLinks(content)}
      </ReactMarkdown>
    </div>
  )
}
