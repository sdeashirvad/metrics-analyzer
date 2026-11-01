import { describe, expect, it } from 'vitest'
import { summaryRetry } from './summaryFlow'

describe('summaryRetry', () => {
  it('reloads a failed read without generating', () => {
    expect(summaryRetry('load')).toBe('reload')
  })

  it('offers another generation only after a generation failure', () => {
    expect(summaryRetry('generate')).toBe('generate')
  })

  it('offers nothing while there is no failure', () => {
    expect(summaryRetry(null)).toBe('none')
  })
})