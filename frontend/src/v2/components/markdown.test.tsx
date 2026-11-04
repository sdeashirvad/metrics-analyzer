import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Markdown } from './markdown'

describe('Markdown', () => {
  it('renders bold, lists, and code without keeping the markers', () => {
    const html = renderToStaticMarkup(
      <Markdown text={'**923 applications** reported.\n\n- First\n- Second\n\nUse `rate`.'} />,
    )
    expect(html).toContain('<strong>923 applications</strong>')
    expect(html).toContain('<li>First</li>')
    expect(html).toContain('<code>rate</code>')
    expect(html).not.toContain('**')
  })

  it('renders headings without keeping the # markers', () => {
    const html = renderToStaticMarkup(<Markdown text={'## What changed\nText here.\n\n### Next'} />)
    expect(html).toContain('What changed')
    expect(html).not.toContain('##')
    expect(html).toContain('md-h2')
  })

  it('renders numbered lists, nested bullets, italics and pipe tables', () => {
    const html = renderToStaticMarkup(
      <Markdown text={'1. First\n2. Second\n\n- Parent\n  - Child\n\n| Name | Rows |\n| --- | ---: |\n| A | 3 |\n| B | **4** |\n\nA *slanted* word and 2*3*4.'} />,
    )
    expect(html).toContain('<ol class="md-list"><li>First</li><li>Second</li></ol>')
    expect(html).toContain('<li class="md-nested">Child</li>')
    expect(html).toContain('<th>Name</th>')
    expect(html).toContain('<td><strong>4</strong></td>')
    expect(html).toContain('<em>slanted</em>')
    expect(html).not.toContain('|')
  })

  it('escapes raw HTML', () => {
    const html = renderToStaticMarkup(<Markdown text={'<img src=x onerror="alert(1)"> **safe**'} />)
    expect(html).not.toContain('<img')
    expect(html).toContain('<strong>safe</strong>')
    expect(html).toContain('onerror')
  })
})