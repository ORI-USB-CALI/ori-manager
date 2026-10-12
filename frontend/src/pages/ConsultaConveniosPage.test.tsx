import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ConsultaConveniosPage } from './ConsultaConveniosPage'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const itemReal = {
  id: 77,
  codigo: null,
  objeto: 'a',
  estado: 'EN_TRAMITE',
  etapa: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
  tipo_convenio: { id: 1, nombre: 'Marco' },
  contraparte: {
    nombre: 'Universidad Contraparte Demo',
    tipo: 'UNIVERSIDAD',
    identificacion: '900123456-7',
    es_aliado_formal: false,
  },
  programa: { id: 49, nombre: 'Programa de Ingeniería de Sistemas' },
  fecha_inicio: '2026-01-01',
  fecha_vencimiento: '2028-01-01',
  fecha_formalizacion: null,
}

function renderPagina() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/convenios']}>
        <ConsultaConveniosPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ConsultaConveniosPage (ConsultaConveniosPage)', () => {
  it('muestra los resultados que devuelve el backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [itemReal], total: 1 }),
      }),
    )

    renderPagina()

    expect(await screen.findByText('1 resultado')).toBeTruthy()
    expect(screen.getByText('Universidad Contraparte Demo (Universidad)')).toBeTruthy()
    expect(screen.getByText('Marco')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ver' }).getAttribute('href')).toBe('/convenios/77')
  })

  it('muestra el mensaje de sin resultados con el término buscado (CA-03)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], total: 0 }),
      }),
    )

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.type(screen.getByLabelText('Código, objeto, aliado o NIT'), 'zzz-no-existe')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    expect(
      await screen.findByText('No se encontraron convenios que coincidan con «zzz-no-existe».'),
    ).toBeTruthy()
  })

  it('muestra el error cuando el backend responde 403 (CA-04)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: async () => ({ detail: 'No tiene permiso para consultar convenios.' }),
      }),
    )

    renderPagina()

    await waitFor(() =>
      expect(screen.getByText('No tiene permiso para consultar convenios.')).toBeTruthy(),
    )
  })
})
