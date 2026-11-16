import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { RevisionesContrapartePage } from './RevisionesContrapartePage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('mantiene seis columnas semánticas, texto completo y el destino de revisión en una única región', async () => {
  const objeto = 'Cooperación académica\nObservaciones completas del convenio'
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{
    revision_id: 12, convenio_id: 41, codigo_convenio: null, objeto,
    version_numero: 5, fecha_envio: '2026-11-16T15:00:00Z',
    enviada_por: { id: 7, nombre_completo: 'Gestora de cooperación', correo: 'gestora@example.com' },
  }]), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><RevisionesContrapartePage /></MemoryRouter>
  </QueryClientProvider>)
  const tabla = await screen.findByRole('table', { name: 'Revisiones de contraparte' })
  const region = screen.getByRole('region', { name: 'Revisiones de contraparte' })
  expect(region.tabIndex).toBe(0)
  expect(region.querySelectorAll('table')).toHaveLength(1)
  expect(within(tabla).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Convenio', 'Objeto', 'Versión', 'Enviado por', 'Fecha', 'Acciones'])
  for (const th of within(tabla).getAllByRole('columnheader')) expect(th.getAttribute('scope')).toBe('col')
  const celdas = within(within(tabla).getAllByRole('row')[1]).getAllByRole('cell')
  expect(celdas).toHaveLength(6)
  expect(celdas[0].textContent).toBe('Convenio provisional #41')
  expect(celdas[1].textContent).toBe(objeto)
  expect(celdas[2].textContent).toBe('V5')
  expect(celdas[3].textContent).toBe('Gestora de cooperación')
  expect(within(tabla).getByRole('link', { name: 'Revisar' }).getAttribute('href')).toBe('/revisiones-contraparte/12')
})
