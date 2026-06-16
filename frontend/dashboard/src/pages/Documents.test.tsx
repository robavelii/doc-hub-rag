import { describe, expect, it } from 'vitest'

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\]/g, '_').replace(/\.\./g, '_').trim() || 'upload'
}

describe('Documents upload helpers', () => {
  it('sanitizes unsafe filenames', () => {
    expect(sanitizeFilename('../../etc/passwd')).not.toContain('..')
    expect(sanitizeFilename('report.pdf')).toBe('report.pdf')
  })

  it('defaults empty filename', () => {
    expect(sanitizeFilename('   ')).toBe('upload')
  })
})
