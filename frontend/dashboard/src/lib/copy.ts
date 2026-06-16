import type { QuerySource } from '@shared/types'
import { stripCitations } from './markdown'

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

export function formatQaMarkdown(
  question: string,
  answer: string,
  sources?: QuerySource[]
): string {
  const cleanAnswer = stripCitations(answer)
  let md = `## Question\n\n${question}\n\n## Answer\n\n${cleanAnswer}\n`
  if (sources?.length) {
    md += '\n## Sources\n\n'
    sources.forEach((s, i) => {
      md += `${i + 1}. **${s.filename || 'source'}** — ${s.text.slice(0, 200)}${s.text.length > 200 ? '…' : ''}\n`
    })
  }
  return md
}
