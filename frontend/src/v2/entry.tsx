import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import { V2Routes } from './routes'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'
import './styles/architecture.css'

const router = createBrowserRouter([{ path: '*', element: <V2Routes /> }])

export function Entry() {
  return <RouterProvider router={router} />
}
