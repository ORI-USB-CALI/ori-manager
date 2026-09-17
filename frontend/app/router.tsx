import { createBrowserRouter } from 'react-router-dom'

import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { ConvenioNuevoPage } from '../pages/ConvenioNuevoPage'
import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/convenios/nuevo',
    element: <ConvenioNuevoPage />,
  },
  {
    path: '/convenios/:id',
    element: <ConvenioDetallePage />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])
