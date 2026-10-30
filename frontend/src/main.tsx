import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { router } from './App'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'
import './styles/architecture.css'

const root = document.getElementById('root')
if (!root) throw new Error('Root element missing')

createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
