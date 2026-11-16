import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION } from '../auth/sesion'
import { AliadoDetallePage } from './AliadoDetallePage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function montar(permisos: string[]) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, { permisos, rol: { codigo: 'GESTOR_ORI' } })
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    id: 1, nombre: 'Universidad aliada', tipo: 'UNIVERSIDAD', tipo_identificacion: 'NIT',
    identificacion: '900000017', ciudad: null, correo: 'contacto.institucional.extenso@example.com',
    telefono: null, activo: true, convenios: [],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  render(<QueryClientProvider client={cliente}><NotificationsContext.Provider value={vi.fn()}>
    <MemoryRouter initialEntries={['/aliados/1']}><Routes>
      <Route path="/aliados/:aliadoId" element={<AliadoDetallePage />} />
    </Routes></MemoryRouter>
  </NotificationsContext.Provider></QueryClientProvider>)
}

it('conserva información completa y consulta sin controles de edición para quien no tiene permiso', async () => {
  montar(['aliados.ver'])
  const correo = await screen.findByText('contacto.institucional.extenso@example.com')
  expect(correo.tagName).toBe('DD')
  expect(correo.previousElementSibling?.textContent).toBe('Correo')
  expect(screen.getByText('900000017').tagName).toBe('DD')
  expect(screen.queryByRole('button', { name: 'Editar datos' })).toBeNull()
  expect(screen.queryByRole('textbox')).toBeNull()
})

it('permite entrar y salir de edición conservando las restricciones de identidad', async () => {
  montar(['aliados.ver', 'aliados.editar'])
  const usuario = userEvent.setup()
  await usuario.click(await screen.findByRole('button', { name: 'Editar datos' }))
  expect((screen.getByLabelText('NIT / documento') as HTMLInputElement).readOnly).toBe(true)
  expect((screen.getByLabelText('Tipo de identificación') as HTMLSelectElement).disabled).toBe(true)
  expect((screen.getByLabelText('Nombre') as HTMLInputElement).required).toBe(true)
  await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))
  expect(screen.getByText('900000017').tagName).toBe('DD')
  expect(screen.queryByRole('textbox')).toBeNull()
})
