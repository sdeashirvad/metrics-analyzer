/**
 * The Data Explorer agent writes its answer as prose with fixed sections. The service already extracts
 * the intent, the assumptions, the SQL and the result table into structured fields, so the page shows
 * those once. This returns only the prose that is not a repeat of them.
 */
const HEADING = /^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[ \t]*(interpreted intent|assumptions|generated sql|result dataset|truncation)(?:\*\*)?[ \t]*:?[ \t]*$/im

export function remainingProse(agentText: string): string {
  const text = agentText.replace(/\r\n/g, '\n')
  const found = HEADING.exec(text)
  if (!found) return stripInlineIntent(text).trim()
  return stripInlineIntent(text.slice(0, found.index)).trim()
}

function stripInlineIntent(text: string): string {
  return text.replace(/\*\*interpreted intent\*\*[^\n]*(?:\n(?!\s*\n)[^\n]*)*/i, '')
}
