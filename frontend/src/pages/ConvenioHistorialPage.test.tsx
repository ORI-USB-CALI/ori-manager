import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConvenioHistorialPage } from './ConvenioHistorialPage'
import type { HistorialConvenio, UsuarioResumen } from './epica02'

const revisor: UsuarioResumen = { id: 2, nombre_completo: 'Revisora Jurídica', correo: 'revisora@example.com' }
const gestor: UsuarioResumen = { id: 1, nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' }

const historial: HistorialConvenio = {
  revisiones: [
    {
      id: 10,
      version_convenio_id: null,
      version_resultado_id: null,
      version_convenio: null,
      version_resultado: null,
      instancia_juridica: 1,
      numero_ronda: 1,
      tipo: 'JURIDICA',
      estado: 'RESUELTA',
      resultado: 'DEVUELTA',
      responsable: null,
      creada_por: gestor,
      resuelta_por: revisor,
      snapshot_datos: null,
      creado_en: '2026-10-01T14:00:00Z',
      resuelta_en: '2026-10-01T15:00:00Z',
      observaciones: [
        {
          id: 100,
          origen: 'REVISOR_ORI',
          descripcion: 'Precisar el objeto del convenio',
          respuesta: 'Objeto precisado con las actividades',
          estado: 'ATENDIDA',
          registrada_por: revisor,
          responsable: gestor,
          atendida_por: gestor,
          fecha_atencion: '2026-10-02T13:30:00Z',
          creado_en: '2026-10-01T15:00:00Z',
        },
      ],
      invitaciones_contraparte: [],
      respuesta_contraparte: null,
    },
  ],
  cambios_etapa: [],
}

const sesionRevisor: Sesion = {
  id: revisor.id,
  correo: revisor.correo,
  nombre_completo: revisor.nombre_completo,
  activo: true,
  tipo_usuario: 'INTERNO',
  rol: { codigo: 'REVISOR_ORI', nombre: 'Revisor ORI' },
  permisos: ['convenios.ver', 'convenios.revisar'],
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('ConvenioHistorialPage', () => {
  it('muestra el historial a un Revisor con acceso histórico aunque no tenga acceso operativo', async () => {
    const fetch = vi.fn(async (url: string) => {
      if (url === '/api/convenios/41/revisiones') return respuesta(200, historial)
      if (url === '/api/convenios/41/linea-tiempo') {
        return respuesta(200, [{ codigo: 'INICIO_ELABORACION', nombre: 'Inicio de elaboración', fecha: '2026-09-30T13:00:00Z', estado: 'COMPLETADO' }])
      }
      return respuesta(404, { detail: 'Convenio no encontrado' })
    })
    vi.stubGlobal('fetch', fetch)
    const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    cliente.setQueryData(CLAVE_SESION, sesionRevisor)

    render(
      <QueryClientProvider client={cliente}>
        <NotificationsContext.Provider value={vi.fn()}>
          <MemoryRouter initialEntries={['/convenios/41/historial']}>
            <Routes>
              <Route path="/convenios/:convenioId/historial" element={<ConvenioHistorialPage />} />
              <Route path="/convenios/:convenioId" element={<h1>Convenio de prueba</h1>} />
            </Routes>
          </MemoryRouter>
        </NotificationsContext.Provider>
      </QueryClientProvider>,
    )

    const lineaTiempo = screen.getByRole('region', { name: 'Línea de tiempo' })
    expect(await within(lineaTiempo).findByText('Inicio de elaboración')).toBeTruthy()
    const seccion = await screen.findByRole('region', { name: 'Observaciones jurídicas' })
    expect(lineaTiempo.compareDocumentPosition(seccion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(seccion).getByText('Precisar el objeto del convenio')).toBeTruthy()
    expect(within(seccion).getByText('Objeto precisado con las actividades')).toBeTruthy()
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/convenios/41/evaluacion', expect.anything()))
    await waitFor(() => expect(screen.queryByText('Cargando evaluación del convenio…')).toBeNull())
    expect(screen.queryByRole('alert')).toBeNull()
    expect(fetch).not.toHaveBeenCalledWith('/api/convenios/41', expect.anything())
    // Sin solicitudId la página no consulta las versiones de la solicitud.
    expect(fetch.mock.calls.some(([url]) => url.includes('/solicitudes/'))).toBe(false)
    expect(screen.getByRole('link', { name: 'Tablero de convenios' }).getAttribute('href')).toBe('/convenios/tablero')
    const navegacion = screen.getByRole('navigation', { name: 'Navegación del historial' })
    expect(within(navegacion).getByRole('link', { name: 'Consulta de convenios formalizados' }).getAttribute('href')).toBe('/convenios')
    await userEvent.click(within(navegacion).getByRole('link', { name: 'Volver al convenio' }))
    expect(await screen.findByRole('heading', { name: 'Convenio de prueba' })).toBeTruthy()
  })
})
