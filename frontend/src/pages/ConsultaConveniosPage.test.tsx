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

  // HU-27: filtros por fecha.
  it('arranca en Fecha de formalización y envía tipo_fecha + fecha_desde/hasta al aplicar (CA-01/CA-04)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()
    const usuario = userEvent.setup()
    expect(
      (screen.getByLabelText('Fecha de formalización') as HTMLInputElement).checked,
    ).toBe(true)

    await usuario.click(screen.getByLabelText('Vigencia'))
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-01')
    await usuario.type(screen.getByLabelText('Hasta'), '2026-06-30')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const url = fetchMock.mock.calls.at(-1)?.[0] as string
    expect(url).toContain('tipo_fecha=VIGENCIA')
    expect(url).toContain('fecha_desde=2026-06-01')
    expect(url).toContain('fecha_hasta=2026-06-30')
  })

  it('CA-05: rango inválido muestra el error, deshabilita Buscar y no consulta al backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-30')
    await usuario.type(screen.getByLabelText('Hasta'), '2026-06-01')

    expect(await screen.findByText('El rango de fechas no es válido')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Buscar' })).toHaveProperty('disabled', true)

    const llamadasAntes = fetchMock.mock.calls.length
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(fetchMock.mock.calls.length).toBe(llamadasAntes)
  })

  it('CA-06/RN-08: Quitar fechas limpia el rango sin tocar el término de búsqueda', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.type(screen.getByLabelText('Código, objeto, aliado o NIT'), 'movilidad')
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-01')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    await usuario.click(screen.getByRole('button', { name: 'Quitar fechas' }))

    await waitFor(() => {
      const url = fetchMock.mock.calls.at(-1)?.[0] as string
      expect(url).toContain('buscar=movilidad')
      expect(url).not.toContain('fecha_desde')
      expect(url).not.toContain('tipo_fecha')
    })
    expect((screen.getByLabelText('Desde') as HTMLInputElement).value).toBe('')
  })

  it('FE-5: muestra las columnas de formalización y vigencia, con "Sin formalizar"/"Sin definir" cuando vienen null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            { ...itemReal, id: 1, fecha_formalizacion: '2026-06-15' },
            { ...itemReal, id: 2, fecha_formalizacion: null, fecha_inicio: null, fecha_vencimiento: null },
          ],
          total: 2,
        }),
      }),
    )

    renderPagina()

    expect(await screen.findByText('15/06/2026')).toBeTruthy()
    expect(screen.getByText('01/01/2026 – 01/01/2028')).toBeTruthy()
    expect(screen.getByText('Sin formalizar')).toBeTruthy()
    expect(screen.getByText('Sin definir')).toBeTruthy()
  })
})
