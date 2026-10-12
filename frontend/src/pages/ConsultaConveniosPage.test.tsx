import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { Mock } from 'vitest'
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

// HU-28 BE-1: respuesta de GET /convenios/catalogos/consulta.
const catalogo = {
  estados: ['EN_TRAMITE', 'VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'FINALIZADO', 'CANCELADO'],
  tipos_contraparte: ['UNIVERSIDAD', 'COLEGIO', 'EMPRESA', 'ENTIDAD_GUBERNAMENTAL'],
  programas: [
    { id: 49, codigo: 'ISIS', nombre: 'Programa de Ingeniería de Sistemas', tipo: 'PROGRAMA' },
    { id: 50, codigo: 'DER', nombre: 'Programa de Derecho', tipo: 'PROGRAMA' },
  ],
}

function respuesta(cuerpo: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => cuerpo })
}

// El catálogo y el listado comparten fetch: se responde según la ruta.
function mockFetch(listado: unknown = { items: [], total: 0 }) {
  const fetchMock = vi.fn((url: string) =>
    respuesta(url.includes('/convenios/catalogos/consulta') ? catalogo : listado),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function ultimaConsulta(fetchMock: Mock) {
  const urls = fetchMock.mock.calls
    .map((llamada) => llamada[0] as string)
    .filter((url) => url.startsWith('/api/convenios?'))
  return urls.at(-1) ?? ''
}

function renderPagina(ruta = '/convenios') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[ruta]}>
        <ConsultaConveniosPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ConsultaConveniosPage (ConsultaConveniosPage)', () => {
  it('muestra los resultados que devuelve el backend', async () => {
    mockFetch({ items: [itemReal], total: 1 })

    renderPagina()

    expect(await screen.findByText('1 resultado')).toBeTruthy()
    expect(screen.getByText('Universidad Contraparte Demo (Universidad)')).toBeTruthy()
    expect(screen.getByText('Marco')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ver' }).getAttribute('href')).toBe('/convenios/77')
  })

  it('muestra el mensaje de sin resultados con el término buscado (CA-03)', async () => {
    mockFetch()

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

  // HU-27: filtros por fecha (van dentro de "Más filtros").
  it('arranca en Fecha de formalización y envía tipo_fecha + fecha_desde/hasta al aplicar (CA-01/CA-04)', async () => {
    const fetchMock = mockFetch()

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    expect(
      (screen.getByLabelText('Fecha de formalización') as HTMLInputElement).checked,
    ).toBe(true)

    await usuario.click(screen.getByLabelText('Vigencia'))
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-01')
    await usuario.type(screen.getByLabelText('Hasta'), '2026-06-30')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(url).toContain('tipo_fecha=VIGENCIA')
      expect(url).toContain('fecha_desde=2026-06-01')
      expect(url).toContain('fecha_hasta=2026-06-30')
    })
  })

  it('CA-05: rango inválido muestra el error, deshabilita Buscar y no consulta al backend', async () => {
    const fetchMock = mockFetch()

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-30')
    await usuario.type(screen.getByLabelText('Hasta'), '2026-06-01')

    expect(await screen.findByText('El rango de fechas no es válido')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Buscar' })).toHaveProperty('disabled', true)

    // Con el rango inválido el panel no se puede plegar: el error quedaría oculto.
    await usuario.click(screen.getByRole('button', { name: 'Menos filtros' }))
    expect(screen.getByText('El rango de fechas no es válido')).toBeTruthy()

    const llamadasAntes = fetchMock.mock.calls.length
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(fetchMock.mock.calls.length).toBe(llamadasAntes)
  })

  it('CA-06/RN-08: Quitar fechas limpia el rango sin tocar el término de búsqueda', async () => {
    const fetchMock = mockFetch()

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    await usuario.type(screen.getByLabelText('Código, objeto, aliado o NIT'), 'movilidad')
    await usuario.type(screen.getByLabelText('Desde'), '2026-06-01')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('fecha_desde=2026-06-01'))

    await usuario.click(screen.getByRole('button', { name: 'Quitar fechas' }))

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(url).toContain('buscar=movilidad')
      expect(url).not.toContain('fecha_desde')
      expect(url).not.toContain('tipo_fecha')
    })
    expect((screen.getByLabelText('Desde') as HTMLInputElement).value).toBe('')
  })

  it('FE-5: muestra las columnas de formalización y vigencia, con "Sin formalizar"/"Sin definir" cuando vienen null', async () => {
    mockFetch({
      items: [
        { ...itemReal, id: 1, fecha_formalizacion: '2026-06-15' },
        { ...itemReal, id: 2, fecha_formalizacion: null, fecha_inicio: null, fecha_vencimiento: null },
      ],
      total: 2,
    })

    renderPagina()

    expect(await screen.findByText('15/06/2026')).toBeTruthy()
    expect(screen.getByText('01/01/2026 – 01/01/2028')).toBeTruthy()
    expect(screen.getByText('Sin formalizar')).toBeTruthy()
    expect(screen.getByText('Sin definir')).toBeTruthy()
  })

  // HU-28: filtros avanzados.
  it('FE-1: los filtros avanzados están plegados y muestran las opciones del catálogo al desplegarlos', async () => {
    mockFetch()

    renderPagina()
    const usuario = userEvent.setup()
    expect(screen.queryByLabelText('Vigente')).toBeNull()

    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))

    expect(await screen.findByLabelText('Vigente')).toBeTruthy()
    expect(screen.getByLabelText('Por vencer')).toBeTruthy()
    expect(screen.getByLabelText('Entidad gubernamental')).toBeTruthy()
    const programa = screen.getByLabelText('Programa académico')
    expect(within(programa).getByRole('option', { name: 'Todos los programas' })).toBeTruthy()
    expect(within(programa).getByRole('option', { name: 'Programa de Derecho' })).toBeTruthy()
  })

  it('CA-02/CA-03/CA-04: envía estados y tipos repetidos y el programa al aplicar', async () => {
    const fetchMock = mockFetch()

    renderPagina()
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    await usuario.click(await screen.findByLabelText('Vigente'))
    await usuario.click(screen.getByLabelText('Por vencer'))
    await usuario.click(screen.getByLabelText('Colegio'))
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), '50')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(url).toContain('estado=VIGENTE&estado=POR_VENCER')
      expect(url).toContain('tipo_contraparte=COLEGIO')
      expect(url).toContain('programa_id=50')
    })
  })

  it('FE-5: con filtros en la URL abre el panel, cuenta los filtros y muestra un chip por filtro', async () => {
    mockFetch()

    renderPagina(
      '/convenios?buscar=movilidad&tipo_fecha=FORMALIZACION&fecha_desde=2026-01-01&estado=VIGENTE&tipo_contraparte=EMPRESA&programa_id=49',
    )

    expect(screen.getByRole('button', { name: 'Menos filtros (4)' })).toBeTruthy()
    const chips = screen.getByRole('list', { name: 'Filtros activos' })
    expect(within(chips).getByText('Búsqueda: «movilidad»')).toBeTruthy()
    expect(within(chips).getByText('Formalización: 01/01/2026 – …')).toBeTruthy()
    expect(within(chips).getByText('Vigente')).toBeTruthy()
    expect(within(chips).getByText('Empresa')).toBeTruthy()
    expect(await within(chips).findByText('Programa de Ingeniería de Sistemas')).toBeTruthy()
  })

  it('FE-5: quitar un chip no aplica las casillas marcadas sin pulsar Buscar', async () => {
    const fetchMock = mockFetch()

    renderPagina('/convenios?estado=VIGENTE&estado=VENCIDO')
    const usuario = userEvent.setup()
    // Casilla marcada pero no aplicada.
    await usuario.click(await screen.findByLabelText('Finalizado'))
    await usuario.click(screen.getByRole('button', { name: 'Quitar filtro: Vigente' }))

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(url).toContain('estado=VENCIDO')
      expect(url).not.toContain('estado=VIGENTE')
      expect(url).not.toContain('estado=FINALIZADO')
    })
    expect((screen.getByLabelText('Vigente') as HTMLInputElement).checked).toBe(false)
    expect((screen.getByLabelText('Finalizado') as HTMLInputElement).checked).toBe(true)
  })

  it('FE-5: Limpiar filtros borra todos los filtros y muestra el mensaje genérico cuando no hay resultados', async () => {
    const fetchMock = mockFetch()

    renderPagina('/convenios?estado=CANCELADO&programa_id=49')

    expect(
      await screen.findByText('No hay convenios que cumplan los filtros seleccionados.'),
    ).toBeTruthy()

    const usuario = userEvent.setup()
    await usuario.click(screen.getAllByRole('button', { name: 'Limpiar filtros' })[0])

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(url).not.toContain('estado=')
      expect(url).not.toContain('programa_id=')
    })
    expect(screen.queryByRole('list', { name: 'Filtros activos' })).toBeNull()
    expect((screen.getByLabelText('Cancelado') as HTMLInputElement).checked).toBe(false)
  })
})
