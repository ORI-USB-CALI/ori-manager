import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DirectorioConveniosPage, type ConvenioPublico } from './DirectorioConveniosPage'

const CONVENIO: ConvenioPublico = {
  codigo: 'CONV-2027-001',
  aliado: 'Universidad Aliada',
  tipo_convenio: 'Marco',
  objeto: 'Movilidad académica',
  fecha_inicio: '2027-01-01',
  fecha_vencimiento: '2027-12-31',
  estado: 'VIGENTE',
}

function mostrar(respuesta: Response) {
  const fetch = vi.fn<(url: string) => Promise<Response>>(async () => respuesta)
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Sin sesión en la caché: la página no debe pedirla (CA-01, CA-07).
  render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter><DirectorioConveniosPage /></MemoryRouter>
    </QueryClientProvider>,
  )
  return fetch
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('directorio público de convenios (HU-09)', () => {
  it('muestra los convenios vigentes sin sesión y solo consulta el endpoint público', async () => {
    const fetch = mostrar(Response.json({ items: [CONVENIO], total: 1 }))

    expect(await screen.findByText('CONV-2027-001')).toBeTruthy()
    expect(screen.getByText('Universidad Aliada')).toBeTruthy()
    expect(screen.getByText('Movilidad académica')).toBeTruthy()
    expect(screen.getByText('Vigente')).toBeTruthy()
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
      expect.stringContaining('/public/directorio-convenios?'),
    ])
  })

  it('no muestra campos fuera de la lista blanca (CA-03)', async () => {
    mostrar(Response.json({ items: [{ ...CONVENIO, implicacion_financiera: 'Dato interno' }], total: 1 }))
    expect(await screen.findByText('CONV-2027-001')).toBeTruthy()
    expect(screen.queryByText('Dato interno')).toBeNull()
  })

  it('informa cuando no hay convenios vigentes (CA-05)', async () => {
    mostrar(Response.json({ items: [], total: 0 }))
    expect(await screen.findByText('No hay convenios vigentes disponibles en este momento.')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('un error del servidor muestra un mensaje y no una pantalla rota', async () => {
    mostrar(Response.json({ detail: 'Error' }, { status: 500 }))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})
