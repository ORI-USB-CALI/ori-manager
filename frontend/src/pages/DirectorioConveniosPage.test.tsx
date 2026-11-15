import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { router } from '../app/router'
import type { ConvenioPublico } from './DirectorioConveniosPage'

const CONVENIO: ConvenioPublico = {
  codigo: 'CONV-2027-001',
  aliado: 'Universidad Aliada',
  tipo_convenio: 'Marco',
  objeto: 'Movilidad académica',
  fecha_inicio: '2027-01-01',
  fecha_vencimiento: '2027-12-31',
  estado: 'VIGENTE',
}

function mostrar(respuesta: Response | ((url: string) => Promise<Response>)) {
  const fetch = vi.fn<(url: string) => Promise<Response>>(async (url) =>
    typeof respuesta === 'function' ? respuesta(url) : respuesta,
  )
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Sin sesión en la caché: la página no debe pedirla (CA-01, CA-07).
  const enrutador = createMemoryRouter(router.routes, { initialEntries: ['/directorio'] })
  render(
    <QueryClientProvider client={cliente}>
      <RouterProvider router={enrutador} />
    </QueryClientProvider>,
  )
  return { fetch, enrutador }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('directorio público de convenios (HU-09)', () => {
  it('muestra los convenios vigentes sin sesión y solo consulta el endpoint público', async () => {
    const { fetch, enrutador } = mostrar(Response.json({ items: [CONVENIO], total: 1 }))

    expect(await screen.findByText('CONV-2027-001')).toBeTruthy()
    expect(screen.getByText('Universidad Aliada')).toBeTruthy()
    expect(screen.getByText('Movilidad académica')).toBeTruthy()
    expect(screen.getByText('Vigente')).toBeTruthy()
    expect(enrutador.state.location.pathname).toBe('/directorio')
    expect(screen.queryByLabelText('Contraseña')).toBeNull()
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

  it('pagina con el total del servidor y permite volver', async () => {
    const usuario = userEvent.setup()
    const { fetch } = mostrar(async (url) => Response.json({
      items: [{ ...CONVENIO, codigo: url.includes('desplazamiento=20') ? 'SEGUNDO' : CONVENIO.codigo }],
      total: 21,
    }))
    expect(await screen.findByText('Página 1 de 2')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Anterior' }) as HTMLButtonElement).disabled).toBe(true)
    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByText('SEGUNDO')).toBeTruthy()
    expect(screen.getByText('Página 2 de 2')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Siguiente' }) as HTMLButtonElement).disabled).toBe(true)
    expect(fetch.mock.calls[1][0]).toContain('limite=20&desplazamiento=20')
    await usuario.click(screen.getByRole('button', { name: 'Anterior' }))
    expect(await screen.findByText(CONVENIO.codigo)).toBeTruthy()
  })

  it.each([401, 403])('un error %s no redirige al login ni muestra detalles internos', async (status) => {
    const { enrutador } = mostrar(Response.json({ detail: 'Información privada' }, { status }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(enrutador.state.location.pathname).toBe('/directorio')
    expect(screen.queryByText('Información privada')).toBeNull()
  })

  it('informa un error de red', async () => {
    mostrar(async () => { throw new TypeError('Failed to fetch') })
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})
