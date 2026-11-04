import { describe, expect, it } from 'vitest'
import { groupDefinitions, humanStatus } from './DefinitionsPage'

describe('definitions grouping', () => {
  it('groups by status in a fixed order and drops empty groups', () => {
    const groups = groupDefinitions([
      { id: 'B', status: 'assumption' },
      { id: 'A', status: 'provisional' },
      { id: 'C', status: 'provisional' },
    ])
    expect(groups.map((group) => group.label)).toEqual(['Provisional', 'Assumption'])
    expect(groups[0].items.map((item) => item.id)).toEqual(['A', 'C'])
  })

  it('keeps unknown statuses visible in an Other group', () => {
    const groups = groupDefinitions([{ id: 'X', status: 'mystery_state' }])
    expect(groups).toHaveLength(1)
    expect(groups[0].label).toBe('Other')
    expect(humanStatus('mystery_state')).toBe('mystery state')
  })
})
