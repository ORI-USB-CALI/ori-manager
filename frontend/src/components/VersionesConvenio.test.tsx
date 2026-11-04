import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { VersionConvenioResumen } from '../pages/epica02'
import { VersionesConvenio } from './VersionesConvenio'

const AUTOR = { id: 1, nombre_completo: 'Gestora ORI', correo: 'gestor@example.com' }
const v1: VersionConvenioResumen = {
  id: 11, numero: 1, autor: AUTOR, contexto: 'INICIALIZACION', creado_en: '2026-10-20T12:00:00Z', plantilla: null,
  etapa: { id: 1, orden: 1, codigo: 'ELABORACION', nombre: 'Elaboración' },
}
const v2: VersionConvenioResumen = {
  ...v1, id: 12, numero: 2, contexto: 'FINALIZACION', creado_en: '2026-10-22T12:00:00Z',
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function mostrar(versiones: Response) {
  vi.stubGlobal('fetch', vi.fn(async () => versiones.clone()))
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <VersionesConvenio convenioId={7} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HT-05 - versiones en el historial del convenio', () => {
  it('lista las versiones formales con su enlace y marca la actual en cualquier etapa (CA-01, CA-04)', async () => {
    mostrar(respuesta(200, [v2, v1]))

    const seccion = (await screen.findByRole('heading', { name: 'Versiones del convenio' })).closest('section') as HTMLElement
    const enlaces = within(seccion).getAllByRole('link', { name: /Ver contenido de la versión/ })
    expect(enlaces.map((enlace) => enlace.getAttribute('href'))).toEqual([
      '/convenios/7/versiones/2', '/convenios/7/versiones/1',
    ])
    const actual = within(seccion).getByText('Versión 2').closest('article') as HTMLElement
    expect(within(actual).getByText('Actual')).toBeTruthy()
    expect(within(actual).getByText('Elaboración finalizada')).toBeTruthy()
    expect(within(seccion).getByText(/guardar avances no agrega versiones/)).toBeTruthy()
  })

  it('no muestra la sección a quien no puede consultar las versiones (CA-07)', async () => {
    mostrar(respuesta(403, { detail: 'No autorizado' }))

    await vi.waitFor(() => expect(screen.queryByText('Cargando versiones…')).toBeNull())
    expect(screen.queryByRole('heading', { name: 'Versiones del convenio' })).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
