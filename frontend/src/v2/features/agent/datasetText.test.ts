import { describe, expect, it } from 'vitest'
import { remainingProse } from './datasetText'

describe('remainingProse', () => {
  it('drops the sections the page shows from structured fields', () => {
    const text = 'Here are the counts.\n\n**Interpreted intent**\nCount non-compliant applications.\n\n**Assumptions**\n- Latest month\n\n**Generated SQL**\n```sql\nselect 1\n```\n\n**Result dataset**\n| a |\n| - |\n| 1 |'
    expect(remainingProse(text)).toBe('Here are the counts.')
  })

  it('handles markdown heading markers and a missing preamble', () => {
    expect(remainingProse('## Interpreted intent\nCount.\n## Generated SQL\nselect 1')).toBe('')
  })

  it('keeps free prose when no known section appears', () => {
    expect(remainingProse('No query was needed. The register has 24 metrics.')).toBe('No query was needed. The register has 24 metrics.')
  })

  it('removes an inline intent paragraph but keeps what follows it', () => {
    expect(remainingProse('**Interpreted intent** Count apps.\n\nNote: counts are provisional.')).toBe('Note: counts are provisional.')
  })
})
