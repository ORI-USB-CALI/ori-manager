import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatDateTime } from '../components/tableFormatters'
import { SolicitudHistorialPage } from './SolicitudHistorialPage'
import type { AlcanceHistorialSolicitud, HistorialSolicitud } from './solicitudes'

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

const pendiente: HistorialSolicitud = {
  ...corregida,
  estado: 'DEVUELTA',
  versiones: [
    {
      numero: 1,
      radicada_en: '2026-10-01T15:00:00Z',
      devolucion: {
        observaciones: 'Precisar la vigencia',
        devuelta_por_nombre: 'Gestor ORI',
        devuelta_en: '2026-10-02T14:00:00Z',
        corregida_en_version: null,
      },
    },
  ],
}

// Testing Library compara el texto con los espacios normalizados, y el formato de
// fecha de es-CO puede traer espacios no separables.
function normalizado(texto: string): string {
  return texto.replace(/\s+/g, ' ')
}

function mostrar(alcance: AlcanceHistorialSolicitud, estado: number, cuerpo: unknown) {
  const fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } }),
  )
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
  it('relaciona cada devolución con la versión que la corrigió', async () => {
    const fetch = mostrar('recibida', 200, corregida)

    const versiones = await screen.findAllByRole('listitem')

    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/recibidas/7/historial', expect.anything())
    expect(versiones.map((item) => item.querySelector('.timeline-titulo')?.textContent)).toEqual([
      'Versión 1',
      'Versión 2 Versión vigente',
    ])
    expect(within(versiones[0]).getByText('Adjuntar el RUT actualizado')).toBeTruthy()
    expect(within(versiones[0]).getByText(normalizado(`Gestor ORI · ${formatDateTime('2026-10-02T14:00:00Z')}`))).toBeTruthy()
    expect(within(versiones[0]).getByRole('link', { name: 'versión 2' }).getAttribute('href')).toBe('#version-2')
    expect(within(versiones[1]).queryByText('Devuelta')).toBeNull()
    expect(screen.getByRole('link', { name: 'Volver a la solicitud' }).getAttribute('href')).toBe('/ori/solicitudes/7')
  })

  it('indica la devolución que el Solicitante aún no corrige', async () => {
    mostrar('recibida', 200, pendiente)

    expect(await screen.findByText('Pendiente de corrección por el Solicitante')).toBeTruthy()
    expect(screen.queryByText('Versión vigente')).toBeNull()
  })

  it('el Solicitante consulta el historial de su propia solicitud', async () => {
    const fetch = mostrar('propia', 200, corregida)

    expect(await screen.findByText('Adjuntar el RUT actualizado')).toBeTruthy()
    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/7/historial', expect.anything())
    expect(screen.getByRole('link', { name: 'Volver a mis solicitudes' }).getAttribute('href')).toBe('/solicitudes')
  })

  it('informa cuando la solicitud no tiene radicaciones', async () => {
    mostrar('propia', 200, { ...corregida, estado: 'BORRADOR', versiones: [] })

    expect(await screen.findByText('La solicitud todavía no tiene radicaciones registradas.')).toBeTruthy()
  })

  it('informa cuando la solicitud no existe o no le pertenece al usuario', async () => {
    mostrar('propia', 404, { detail: 'Solicitud no encontrada' })

    expect(await screen.findByRole('heading', { name: 'Solicitud no encontrada' })).toBeTruthy()
  })
})
