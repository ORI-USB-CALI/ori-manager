import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SolicitudHistorialPage } from './SolicitudHistorialPage'
import type { AlcanceHistorialSolicitud, ComparacionVersiones, HistorialSolicitud } from './solicitudes'

const gestor = { id: 1, nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' }

const corregida: HistorialSolicitud = {
  solicitud_id: 7,
  consecutivo: 'SOL-2026-0007',
  estado: 'EN_ESTUDIO',
  versiones: [
    {
      numero: 1,
      radicada_en: '2026-10-01T15:00:00Z',
      devolucion: {
        observaciones: 'Adjuntar el RUT actualizado',
        devuelta_por_nombre: 'Gestor ORI',
        devuelta_en: '2026-10-02T14:00:00Z',
        corregida_en_version: 2,
      },
    },
    { numero: 2, radicada_en: '2026-10-03T16:30:00Z', devolucion: null },
  ],
}

const cambios: ComparacionVersiones = {
  solicitud_id: 7,
  version_base: { numero: 1, radicada_en: '2026-10-01T15:00:00Z', radicada_por: gestor },
  version_comparada: { numero: 2, radicada_en: '2026-10-03T16:30:00Z', radicada_por: gestor },
  hay_cambios: true,
  campos: [{ campo: 'vigencia_estimada', etiqueta: 'Vigencia estimada', valor_anterior: '24 meses', valor_nuevo: '36 meses' }],
  documentos: { agregados: [], eliminados: [], sustituidos: [] },
}

function respuesta(estado: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } })
}

function mostrar(alcance: AlcanceHistorialSolicitud, rutas: Record<string, Response>) {
  const fetch = vi.fn(async (url: string) => rutas[url]?.clone() ?? respuesta(404, { detail: 'Not Found' }))
  vi.stubGlobal('fetch', fetch)
  const ruta = alcance === 'recibida' ? '/ori/solicitudes/:solicitudId/historial' : '/solicitudes/:solicitudId/historial'
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[ruta.replace(':solicitudId', '7')]}>
        <Routes>
          <Route path={ruta} element={<SolicitudHistorialPage alcance={alcance} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return fetch
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('SolicitudHistorialPage', () => {
  it('muestra a la ORI las radicaciones, la devolución corregida y los cambios entre versiones', async () => {
    const fetch = mostrar('recibida', {
      '/api/solicitudes/recibidas/7/historial': respuesta(200, corregida),
      '/api/solicitudes/recibidas/7/versiones/2/comparacion': respuesta(200, cambios),
    })

    const tabla = await screen.findByRole('table', { name: 'Campos modificados' })

    expect(screen.getByRole('heading', { name: 'Historial de la solicitud' })).toBeTruthy()
    expect(screen.getByText('Adjuntar el RUT actualizado')).toBeTruthy()
    expect(screen.getByText('Corregida en la versión 2')).toBeTruthy()
    expect(within(tabla).getByRole('rowheader', { name: 'Vigencia estimada' })).toBeTruthy()
    expect(within(tabla).getByText('24 meses')).toBeTruthy()
    expect(within(tabla).getByText('36 meses')).toBeTruthy()
    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/recibidas/7/versiones/2/comparacion', expect.anything())
    expect(screen.getByRole('link', { name: 'Volver a la solicitud' }).getAttribute('href')).toBe('/ori/solicitudes/7')
  })

  it('indica la devolución que el Solicitante aún no corrige', async () => {
    mostrar('recibida', {
      '/api/solicitudes/recibidas/7/historial': respuesta(200, {
        ...corregida,
        estado: 'DEVUELTA',
        versiones: [{ ...corregida.versiones[0], devolucion: { ...corregida.versiones[0].devolucion!, corregida_en_version: null } }],
      }),
    })

    expect(await screen.findByText('Pendiente de corrección por el Solicitante')).toBeTruthy()
    expect(screen.getByText('Solo existe la radicación inicial; no hay cambios que comparar.')).toBeTruthy()
  })

  it('el Solicitante consulta el historial y los cambios de su propia solicitud', async () => {
    const fetch = mostrar('propia', {
      '/api/solicitudes/7/historial': respuesta(200, corregida),
      '/api/solicitudes/7/versiones/2/comparacion': respuesta(200, cambios),
    })

    expect(await screen.findByRole('table', { name: 'Campos modificados' })).toBeTruthy()
    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/7/historial', expect.anything())
    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/7/versiones/2/comparacion', expect.anything())
    expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining('/recibidas/'), expect.anything())
    expect(screen.getByRole('link', { name: 'Volver a mis solicitudes' }).getAttribute('href')).toBe('/solicitudes')
  })

  it('informa cuando la solicitud no tiene radicaciones', async () => {
    mostrar('propia', { '/api/solicitudes/7/historial': respuesta(200, { ...corregida, estado: 'BORRADOR', versiones: [] }) })

    expect(await screen.findByText('Aún no hay radicaciones registradas.')).toBeTruthy()
  })

  it('informa cuando la solicitud no existe o no le pertenece al usuario', async () => {
    mostrar('propia', {})

    expect(await screen.findByRole('heading', { name: 'Solicitud no encontrada' })).toBeTruthy()
  })
})
