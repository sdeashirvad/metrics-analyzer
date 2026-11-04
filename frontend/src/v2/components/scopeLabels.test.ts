import { describe, expect, it } from 'vitest'
import { describeFilters, legalEntityLabel, legalEntityWithCode } from './scopeLabels'

describe('scope labels', () => {
  const names = { LE2048: 'Legal_Entity_07' }

  it('maps only confirmed legal entity codes and keeps unknown ids as they arrived', () => {
    expect(legalEntityLabel('LE2048', names)).toBe('Legal_Entity_07')
    expect(legalEntityLabel('LE9999', names)).toBe('LE9999')
    expect(legalEntityWithCode('LE2048', names)).toBe('Legal_Entity_07 (LE2048)')
    expect(legalEntityWithCode('LE9999', names)).toBe('LE9999')
  })

  it('describes active filters in a stable order and is empty for the default scope', () => {
    expect(describeFilters({})).toEqual([])
    expect(describeFilters({ orgTree: 'BU', legalEntity: ['LE2048'], tier: [4], ma: 'Y' }, names)).toEqual(['Bank group', 'Legal_Entity_07', 'Tier 4', 'M&A Y'])
  })
})
