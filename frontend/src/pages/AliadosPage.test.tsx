import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { apiFetch } from '../app/api'
import { AliadosPage } from './AliadosPage'

vi.mock('../app/api', async (original) => ({ ...await original<typeof import('../app/api')>(), apiFetch: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('pagina todos los resultados, combina filtros y restaura el listado', async () => {
  const documento = '1234567890123456789012345678901234567890'
  const llamadas: URLSearchParams[] = []
  vi.mocked(apiFetch).mockImplementation(async (ruta) => {
    if (ruta === '/paises') return [{ id: 1, nombre: 'Colombia' }, { id: 2, nombre: 'Chile' }]
    const params = new URL(ruta, 'http://localhost').searchParams
    llamadas.push(params)
    const filtrado = params.has('tipo') || params.has('activo') || params.has('pais_id') || params.has('buscar')
    const total = params.get('pais_id') === '2' ? 0 : filtrado ? 1 : 105
    const offset = Number(params.get('desplazamiento'))
    return { total, items: Array.from({ length: Math.min(20, Math.max(0, total - offset)) }, (_, i) => ({ id: offset + i, nombre: `Aliado ${offset + i}`, identificacion: documento, pais_id: 1, tipo: 'UNIVERSIDAD', activo: true })) }
  })
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AliadosPage /></QueryClientProvider></MemoryRouter>)
  await screen.findByText('105 resultados')
  expect((screen.getByRole('button', { name: 'Anterior' }) as HTMLButtonElement).disabled).toBe(true)
  for (let pagina = 1; pagina <= 5; pagina++) {
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await screen.findByText(`Aliado ${pagina * 20}`)
  }
  expect((screen.getByRole('button', { name: 'Siguiente' }) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getAllByText(documento)).toHaveLength(5)
  fireEvent.change(screen.getByLabelText('Tipo de aliado'), { target: { value: 'UNIVERSIDAD' } })
  await screen.findByText('1 resultado')
  fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'inactivo' } })
  fireEvent.change(screen.getByLabelText('Pa\u00eds'), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText('Nombre o NIT/documento'), { target: { value: documento } })
  fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))
  await waitFor(() => expect(llamadas.at(-1)?.get('buscar')).toBe(documento))
  expect(Object.fromEntries(llamadas.at(-1)!)).toMatchObject({ desplazamiento: '0', tipo: 'UNIVERSIDAD', activo: 'false', pais_id: '1' })
  fireEvent.change(screen.getByLabelText('Pa\u00eds'), { target: { value: '2' } })
  await screen.findByText('0 resultados')
  expect(screen.getByText('No se encontraron resultados con los filtros seleccionados.')).toBeTruthy()
  fireEvent.click(screen.getAllByRole('button', { name: 'Limpiar filtros' })[0])
  await screen.findByText('105 resultados')
  await screen.findByText('Aliado 0')
  expect((screen.getByLabelText('Nombre o NIT/documento') as HTMLInputElement).value).toBe('')
})
