import type { ReactNode } from 'react'

/**
 * Renders a small Markdown subset: headings, paragraphs, bullet and numbered lists (one level of
 * indentation), pipe tables, fenced code, bold, italic and inline code.
 * Children are text nodes, so HTML in the source stays text.
 */
export function Markdown({ text }: { text: string }) {
  return <div className="md">{blocks(text)}</div>
}

const BULLET = /^(\s*)[-*]\s+(.*)$/
const NUMBERED = /^(\s*)\d+[.)]\s+(.*)$/
const SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/

function cells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isTableStart(lines: string[], index: number): boolean {
  return lines[index].includes('|') && index + 1 < lines.length && SEPARATOR.test(lines[index + 1]) && lines[index + 1].includes('-')
}

function startsBlock(lines: string[], index: number): boolean {
  const line = lines[index]
  return (
    line.trim() === '' ||
    line.startsWith('```') ||
    /^#{1,6}\s+/.test(line) ||
    BULLET.test(line) ||
    NUMBERED.test(line) ||
    isTableStart(lines, index) ||
    /^\s*(-{3,}|\*{3,})\s*$/.test(line)
  )
}

function blocks(text: string): ReactNode[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: ReactNode[] = []
  let index = 0
  let key = 0
  while (index < lines.length) {
    const line = lines[index]
    if (line.startsWith('```')) {
      const code: string[] = []
      index += 1
      while (index < lines.length && !lines[index].startsWith('```')) {
        code.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      out.push(
        <pre key={key} className="code">
          {code.join('\n')}
        </pre>,
      )
      key += 1
      continue
    }
    if (line.trim() === '') {
      index += 1
      continue
    }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      out.push(<hr key={key} className="md-rule" />)
      key += 1
      index += 1
      continue
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      out.push(
        <p key={key} className={`md-h md-h${Math.min(heading[1].length, 3)}`}>
          <strong>{inline(heading[2].replace(/\s*#+\s*$/, ''), String(key))}</strong>
        </p>,
      )
      key += 1
      index += 1
      continue
    }
    if (isTableStart(lines, index)) {
      const head = cells(lines[index])
      index += 2
      const rows: string[][] = []
      while (index < lines.length && lines[index].includes('|') && lines[index].trim() !== '') {
        rows.push(cells(lines[index]))
        index += 1
      }
      out.push(
        <div key={key} className="table-wrap">
          <table className="mini-table">
            <thead>
              <tr>
                {head.map((cell, cellKey) => (
                  <th key={cellKey}>{inline(cell, `${key}-h${cellKey}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowKey) => (
                <tr key={rowKey}>
                  {head.map((_, cellKey) => (
                    <td key={cellKey}>{inline(row[cellKey] ?? '', `${key}-${rowKey}-${cellKey}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      key += 1
      continue
    }
    const listMatch = BULLET.test(line) ? BULLET : NUMBERED.test(line) ? NUMBERED : null
    if (listMatch) {
      const ordered = listMatch === NUMBERED
      const items: Array<{ text: string; depth: number }> = []
      while (index < lines.length) {
        const found = ordered ? NUMBERED.exec(lines[index]) : BULLET.exec(lines[index])
        if (!found) break
        items.push({ text: found[2], depth: found[1].length >= 2 ? 1 : 0 })
        index += 1
      }
      const Tag = ordered ? 'ol' : 'ul'
      out.push(
        <Tag key={key} className="md-list">
          {items.map((item, itemKey) => (
            <li key={itemKey} className={item.depth ? 'md-nested' : undefined}>
              {inline(item.text, `${key}-${itemKey}`)}
            </li>
          ))}
        </Tag>,
      )
      key += 1
      continue
    }
    const paragraph: string[] = []
    while (index < lines.length && !startsBlock(lines, index)) {
      paragraph.push(lines[index])
      index += 1
    }
    if (paragraph.length === 0) {
      paragraph.push(lines[index])
      index += 1
    }
    out.push(<p key={key}>{inline(paragraph.join(' '), String(key))}</p>)
    key += 1
  }
  return out
}

function inline(text: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = []
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`|(?<![*\w])\*([^*\s][^*]*)\*(?![*\w]))/g
  let last = 0
  let match: RegExpExecArray | null
  let part = 0
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    if (match[2] != null) parts.push(<strong key={`${keyPrefix}-b${part}`}>{match[2]}</strong>)
    else if (match[3] != null) parts.push(<code key={`${keyPrefix}-c${part}`}>{match[3]}</code>)
    else if (match[4] != null) parts.push(<em key={`${keyPrefix}-i${part}`}>{match[4]}</em>)
    part += 1
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}
