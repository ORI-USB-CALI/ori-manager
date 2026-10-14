import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { ConvenioNuevoPage } from './ConvenioNuevoPage'

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function abrir() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={vi.fn()}>
        <MemoryRouter initialEntries={['/convenios/nuevo']}>
          <Routes>
            <Route path="/convenios/nuevo" element={<ConvenioNuevoPage />} />
            <Route path="/convenios/:convenioId/elaboracion" element={<p>Editor disponible</p>} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HU-10 - creación de convenio manual', () => {
  it('crea sin solicitud y sin aliado, identifica el origen y abre el editor (CA-01/02/03)', async () => {
    const peticiones: Array<{ url: string; init?: RequestInit }> = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      peticiones.push({ url, init })
      if (url.startsWith('/api/aliados')) return respuesta(200, { items: [], total: 0 })
      if (url === '/api/convenios/manual') return respuesta(201, { id: 31, origen: 'MANUAL_ORI' })
      throw new Error(`Ruta inesperada: ${url}`)
    }))

    abrir()
    expect(screen.getByRole('heading', { name: 'Crear convenio manualmente' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Crear y abrir editor' }))

    expect(await screen.findByText('Editor disponible')).toBeTruthy()
    const creacion = peticiones.filter((peticion) => peticion.url === '/api/convenios/manual')
    expect(creacion).toHaveLength(1)
    expect(creacion[0].init?.method).toBe('POST')
    const payload = JSON.parse(String(creacion[0].init?.body)) as Record<string, unknown>
    expect(payload.objeto).toBeNull()
    expect(payload.aliado_id).toBeNull()
    expect(payload).not.toHaveProperty('solicitud_id')
  })

  it('no navega al editor si la API niega la creación (CA-08)', async () => {
    const peticiones: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      peticiones.push(url)
      if (url.startsWith('/api/aliados')) return respuesta(200, { items: [], total: 0 })
      return respuesta(403, { detail: 'No tiene permisos para crear convenios' })
    }))
    abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Crear y abrir editor' }))
    await waitFor(() => expect(peticiones.filter((url) => url === '/api/convenios/manual')).toHaveLength(1))
    expect(screen.queryByText('Editor disponible')).toBeNull()
  })
})
