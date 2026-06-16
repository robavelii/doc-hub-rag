import { describe, expect, it } from 'vitest'
import { formatQaMarkdown } from './copy'

describe('formatQaMarkdown', () => {
  it('formats question, answer, and sources', () => {
    const md = formatQaMarkdown(
      'What is UNVRS?',
      'It is a platform [source:abc]',
      [{ id: 'abc', text: 'UNVRS is Universe Labs platform', filename: 'design.docx' }]
    )
    expect(md).toContain('## Question')
    expect(md).toContain('What is UNVRS?')
    expect(md).toContain('## Answer')
    expect(md).toContain('It is a platform')
    expect(md).not.toContain('[source:abc]')
    expect(md).toContain('## Sources')
    expect(md).toContain('design.docx')
  })
})
