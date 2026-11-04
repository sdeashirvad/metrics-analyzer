import { RouterProvider } from 'react-router-dom'
import { router } from './App'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'
import './styles/architecture.css'

export function Entry() {
  return <RouterProvider router={router} />
}
