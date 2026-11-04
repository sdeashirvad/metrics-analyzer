import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { resolveEntry } from './bootstrap/resolveEntry'

const decision = resolveEntry(window.location.pathname)

if (decision === 'redirect') {
  const { pathname, search, hash } = window.location
  window.location.replace(`/legacy${pathname}${search}${hash}`)
} else {
  const root = document.getElementById('root')
  if (!root) throw new Error('Root element missing')
  const loading = decision === 'legacy' ? import('./legacy-entry') : import('./v2/entry')
  void loading.then(({ Entry }) => {
    createRoot(root).render(
      <StrictMode>
        <Entry />
      </StrictMode>,
    )
  })
}
