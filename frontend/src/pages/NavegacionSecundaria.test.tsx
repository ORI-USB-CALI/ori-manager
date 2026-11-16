import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { RequierePermiso } from '../auth/RequierePermiso'
import { NotFoundPage } from './NotFoundPage'

vi.mock('../auth/sesion', () => ({
  useSesion: () => ({ sesion: { id: 1 }, cargando: false, puede: () => false }),
}))

afterEach(cleanup)

it.each([
  ['página no encontrada', <NotFoundPage />],
  ['acceso denegado', <RequierePermiso permiso="auditoria.ver" />],
])('mantiene el retorno fijo al inicio y el teclado en %s', async (_nombre, pagina) => {
  render(<MemoryRouter initialEntries={[{ pathname: '/origen', state: { volver: { to: 'https://example.com', texto: 'Sitio externo' } } }]}>
    <Routes>
      <Route path="/origen" element={pagina} />
      <Route path="/" element={<h1>Inicio de prueba</h1>} />
    </Routes>
  </MemoryRouter>)
  const volver = screen.getByRole('link', { name: 'Volver al inicio' })
  expect(volver.getAttribute('href')).toBe('/')
  expect(volver.classList.contains('accion-volver')).toBe(true)
  const usuario = userEvent.setup()
  await usuario.tab()
  expect(document.activeElement).toBe(volver)
  await usuario.keyboard('{Enter}')
  expect(screen.getByRole('heading', { name: 'Inicio de prueba' })).toBeTruthy()
})
