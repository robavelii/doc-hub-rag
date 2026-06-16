import { useState } from 'react'
import { Check, Copy, Download, FileText } from 'lucide-react'
import type { QuerySource } from '@shared/types'
import { copyText, formatQaMarkdown } from '../lib/copy'
import { stripCitations } from '../lib/markdown'
import { IconButton } from './ui'

interface MessageActionsProps {
  question?: string
  answer: string
  sources?: QuerySource[]
}

export default function MessageActions({ question, answer, sources }: MessageActionsProps) {
  const [copied, setCopied] = useState<string | null>(null)

  const flash = (key: string) => {
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const handleCopyAnswer = async () => {
    const ok = await copyText(stripCitations(answer))
    if (ok) flash('answer')
  }

  const handleCopyQa = async () => {
    if (!question) return
    const text = `Q: ${question}\n\nA: ${stripCitations(answer)}`
    const ok = await copyText(text)
    if (ok) flash('qa')
  }

  const handleExport = () => {
    if (!question) return
    const md = formatQaMarkdown(question, answer, sources)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `qa-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
    flash('export')
  }

  return (
    <div className="flex items-center gap-0.5 mt-2">
      <IconButton label="Copy answer" onClick={() => void handleCopyAnswer()}>
        {copied === 'answer' ? <Check size={14} className="text-success" /> : <Copy size={14} />}
      </IconButton>
      {question && (
        <IconButton label="Copy Q&A" onClick={() => void handleCopyQa()}>
          {copied === 'qa' ? <Check size={14} className="text-success" /> : <FileText size={14} />}
        </IconButton>
      )}
      {question && (
        <IconButton label="Export as Markdown" onClick={handleExport}>
          {copied === 'export' ? <Check size={14} className="text-success" /> : <Download size={14} />}
        </IconButton>
      )}
    </div>
  )
}
