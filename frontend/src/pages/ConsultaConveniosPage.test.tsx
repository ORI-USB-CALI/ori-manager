import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import type { Mock } from 'vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ConsultaConveniosPage } from './ConsultaConveniosPage'
import { construirQuery, useConsultaConvenios } from './consultaConvenios'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const itemReal = {
  id: 77,
  codigo: null,
  objeto: 'a',
  estado: 'VIGENTE',
  etapa: { codigo: 'FIRMA_ARCHIVO_SEGUIMIENTO', nombre: 'Firma, archivo y seguimiento' },
  tipo_convenio: { id: 1, nombre: 'Marco' },
  contraparte: {
    nombre: 'Universidad Contraparte Demo',
    tipo: 'UNIVERSIDAD',
    identificacion: '900123456-7',
    es_aliado_formal: true,
  },
  programa: { id: 49, nombre: 'Programa de Ingeniería de Sistemas' },
  fecha_inicio: '2026-01-01',
  fecha_vencimiento: '2028-01-01',
  fecha_formalizacion: '2026-06-15',
  puede_ver_detalle: true,
}

// HU-28 BE-1: respuesta de GET /convenios/catalogos/consulta.
const catalogo = {
  estados: ['VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'FINALIZADO'],
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

function NavegacionPrueba() {
  const navegar = useNavigate()
  return <>
    <button onClick={() => navegar(-1)}>Volver atrás</button>
    <button onClick={() => navegar(1)}>Ir adelante</button>
  </>
}

function renderPagina(entrada = '/convenios') {
  // Los casos de HU-26/HU-27 simulan la consulta. El catálogo usa una ruta
  // distinta y no debe recibir accidentalmente esa respuesta del listado.
  const consultar = globalThis.fetch
  vi.stubGlobal('fetch', (url: RequestInfo | URL, init?: RequestInit) =>
    String(url).includes('/convenios/catalogos/consulta')
      ? respuesta(catalogo)
      : consultar(url, init),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entrada]}>
        <NavegacionPrueba />
        <ConsultaConveniosPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ConsultaConveniosPage (ConsultaConveniosPage)', () => {
  it.each(['', '?solo_formalizados=false'])('consulta siempre formalizados al buscar, paginar y limpiar (%s)', async (parametros) => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina(`/convenios${parametros}`)
    expect(await screen.findByText('41 resultados')).toBeTruthy()
    const usuario = userEvent.setup()
    await usuario.type(screen.getByLabelText('Código, objeto, aliado o NIT'), 'movilidad')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('buscar=movilidad'))
    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('desplazamiento=20'))
    await usuario.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).not.toContain('buscar='))
    for (const [url] of fetchMock.mock.calls) {
      expect(new URL(url, 'http://localhost').searchParams.get('solo_formalizados')).toBe('true')
    }
  })

  it('el hook exige formalizados incluso si el llamador intenta desactivar el filtro', async () => {
    const fetchMock = mockFetch()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(
      () => useConsultaConvenios({ limite: 20, desplazamiento: 0, solo_formalizados: false }),
      { wrapper: ({ children }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider> },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams.get('solo_formalizados')).toBe('true')
  })

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

  it('dirige al historial cuando el acceso es solo de lectura', async () => {
  const convenioHistorico = {
    ...itemReal,
    id: 88,
    puede_ver_detalle: false,
  }

  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [convenioHistorico],
        total: 1,
      }),
    }),
  )

  renderPagina()

  const enlace = await screen.findByRole('link', {
    name: 'Ver historial',
  })

  expect(enlace.getAttribute('href')).toBe(
    '/convenios/88/historial',
  )
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
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    expect(
      (screen.getByLabelText('Fecha de formalización') as HTMLInputElement).checked,
    ).toBe(true)

    await usuario.click(screen.getByLabelText('Vigencia'))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-01' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-06-30' } })
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('fecha_hasta=2026-06-30'))
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
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-30' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-06-01' } })

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
    await usuario.click(screen.getByRole('button', { name: 'Más filtros' }))
    await usuario.type(screen.getByLabelText('Código, objeto, aliado o NIT'), 'movilidad')
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-01' } })
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('fecha_desde=2026-06-01'))

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

  it('combina búsqueda y fechas al paginar y vuelve a la primera página al aplicar', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ items: [itemReal], total: 41 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina('/convenios?buscar=SOL-77&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01&fecha_hasta=2026-06-30')
    await screen.findByText('41 resultados')
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => {
      const parametros = new URL(fetchMock.mock.calls.at(-1)?.[0] as string, 'http://localhost').searchParams
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.get('tipo_fecha')).toBe('VIGENCIA')
      expect(parametros.get('fecha_desde')).toBe('2026-06-01')
      expect(parametros.get('fecha_hasta')).toBe('2026-06-30')
      expect(parametros.get('desplazamiento')).toBe('20')
    })
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-02' } })
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => {
      const url = fetchMock.mock.calls.at(-1)?.[0] as string
      expect(url).toContain('fecha_desde=2026-06-02')
      expect(url).not.toContain('desplazamiento')
    })
    expect(screen.getByText('Página 1 de 3')).toBeTruthy()
  })

  it('limpia texto, fechas y paginación con Limpiar filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ items: [itemReal], total: 41 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina('/convenios?buscar=%2377&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01&pagina=2')
    await screen.findByText('41 resultados')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/convenios?limite=20&solo_formalizados=true'))
    expect(screen.getByLabelText('Código, objeto, aliado o NIT')).toHaveProperty('value', '')
    expect(screen.getByLabelText('Desde')).toHaveProperty('value', '')
    expect(screen.getByLabelText('Hasta')).toHaveProperty('value', '')
    expect(screen.getByLabelText('Fecha de formalización')).toHaveProperty('checked', true)
    expect(screen.getByText('Página 1 de 3')).toBeTruthy()
  })

  it('conserva la navegación histórica al combinar texto y fechas', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ items: [{ ...itemReal, puede_ver_detalle: false }], total: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina('/convenios?buscar=SOL-77&tipo_fecha=FORMALIZACION&fecha_hasta=2026-06-30')
    expect((await screen.findByRole('link', { name: 'Ver historial' })).getAttribute('href')).toBe('/convenios/77/historial')
    expect(screen.queryByRole('link', { name: 'Ver' })).toBeNull()
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('fecha_hasta=2026-06-30')
  })

  it('muestra un mensaje útil cuando solo el rango de fechas no tiene resultados', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ items: [], total: 0 }),
    }))
    renderPagina('/convenios?tipo_fecha=VIGENCIA&fecha_desde=2026-06-01')
    expect(await screen.findByText('No se encontraron convenios que coincidan con el rango de fechas.')).toBeTruthy()
  })

  it('muestra el rechazo 422 del backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 422, json: async () => ({ detail: 'El rango de fechas no es válido' }),
    }))
    renderPagina('/convenios?tipo_fecha=VIGENCIA&fecha_desde=2026-06-30&fecha_hasta=2026-06-01')
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'El rango de fechas no es válido')
  })

  it('restaura el formulario y la consulta al volver atrás en el navegador', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ items: [], total: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina('/convenios?buscar=SOL-77&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01')
    const usuario = userEvent.setup()
    await screen.findByText('0 resultados')
    await usuario.click(screen.getByLabelText('Fecha de formalización'))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-15' } })
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('fecha_desde=2026-06-15'))
    await usuario.click(screen.getByRole('button', { name: 'Volver atrás' }))
    await waitFor(() => expect(screen.getByLabelText('Desde')).toHaveProperty('value', '2026-06-01'))
    expect(screen.getByLabelText('Vigencia')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Código, objeto, aliado o NIT')).toHaveProperty('value', 'SOL-77')
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
    expect(screen.queryByLabelText('En trámite')).toBeNull()
    expect(screen.queryByLabelText('Cancelado')).toBeNull()
    expect(screen.getByText('Filtra los convenios formalizados por el tipo de su contraparte.')).toBeTruthy()
    expect(screen.getByLabelText('Entidad gubernamental')).toBeTruthy()
    const programa = screen.getByLabelText('Programa académico')
    expect(within(programa).getByRole('option', { name: 'Todos los convenios' })).toBeTruthy()
    expect(within(programa).getByRole('option', { name: 'Todos los convenios de alcance por programa' })).toBeTruthy()
    expect(within(programa).getByRole('option', { name: 'Alcance institucional / sin programa' })).toBeTruthy()
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
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), 'programa:50')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      const url = ultimaConsulta(fetchMock)
      expect(new URL(url, 'http://localhost').searchParams.getAll('estado').sort()).toEqual(['POR_VENCER', 'VIGENTE'])
      expect(url).toContain('tipo_contraparte=COLEGIO')
      expect(url).toContain('programa_id=50')
      expect(url).toContain('alcance=PROGRAMA')
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

    renderPagina('/convenios?estado=FINALIZADO&programa_id=49')

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
    expect((screen.getByLabelText('Finalizado') as HTMLInputElement).checked).toBe(false)
  })

  it('selecciona alcance institucional, reinicia página y permite quitarlo por chip', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?buscar=SOL-77&programa_id=49&pagina=2')
    const usuario = userEvent.setup()
    await usuario.selectOptions(await screen.findByLabelText('Programa académico'), 'INSTITUCIONAL')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.get('alcance')).toBe('INSTITUCIONAL')
      expect(parametros.has('programa_id')).toBe(false)
      expect(parametros.has('desplazamiento')).toBe(false)
    })
    expect(screen.getByText('Página 1 de 3')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Quitar filtro: Alcance institucional / sin programa' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toBe('/api/convenios?buscar=SOL-77&limite=20&solo_formalizados=true'))
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', '')
  })

  it('restaura todos los criterios y la consulta al navegar Atrás y Adelante', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?buscar=SOL-77&estado=VIGENTE&estado=VENCIDO&tipo_contraparte=EMPRESA&programa_id=49&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01&pagina=2')
    const usuario = userEvent.setup()
    await usuario.click(await screen.findByLabelText('Vencido'))
    await usuario.click(screen.getByLabelText('Finalizado'))
    await usuario.click(screen.getByLabelText('Empresa'))
    await usuario.click(screen.getByLabelText('Colegio'))
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), 'INSTITUCIONAL')
    await usuario.click(screen.getByLabelText('Fecha de formalización'))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-15' } })
    fireEvent.change(screen.getByLabelText('Código, objeto, aliado o NIT'), { target: { value: '#88' } })
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('alcance=INSTITUCIONAL'))
    await usuario.click(screen.getByRole('button', { name: 'Volver atrás' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.getAll('estado')).toEqual(['VENCIDO', 'VIGENTE'])
      expect(parametros.getAll('tipo_contraparte')).toEqual(['EMPRESA'])
      expect(parametros.get('programa_id')).toBe('49')
      expect(parametros.get('tipo_fecha')).toBe('VIGENCIA')
      expect(parametros.get('fecha_desde')).toBe('2026-06-01')
      expect(parametros.get('desplazamiento')).toBe('20')
      expect(parametros.has('alcance')).toBe(false)
    })
    expect(screen.getByLabelText('Vencido')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Finalizado')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Empresa')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Colegio')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Vigencia')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Desde')).toHaveProperty('value', '2026-06-01')
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'programa:49')
    await usuario.click(screen.getByRole('button', { name: 'Ir adelante' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('alcance=INSTITUCIONAL'))
    expect(screen.getByLabelText('Finalizado')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Vencido')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Colegio')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Empresa')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Desde')).toHaveProperty('value', '2026-06-15')
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'INSTITUCIONAL')
    expect(screen.getByLabelText('Fecha de formalización')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Código, objeto, aliado o NIT')).toHaveProperty('value', '#88')
  })

  it.each([
    ['estado', 'Vigente'], ['tipo_contraparte', 'Empresa'],
    ['programa_id', 'Programa de Ingeniería de Sistemas'],
    ['fecha_desde', 'Vigencia: 01/06/2026 – …'], ['buscar', 'Búsqueda: «SOL-77»'],
  ])('quitar el chip %s conserva otros filtros y borradores, reinicia página y hace una sola consulta', async (campo, etiqueta) => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?buscar=SOL-77&estado=VIGENTE&tipo_contraparte=EMPRESA&programa_id=49&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01&pagina=2')
    const usuario = userEvent.setup()
    await usuario.click(await screen.findByLabelText('Finalizado'))
    await usuario.click(screen.getByLabelText('Colegio'))
    const consultasAntes = fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/convenios?')).length
    await usuario.click(await screen.findByRole('button', { name: `Quitar filtro: ${etiqueta}` }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.has(campo)).toBe(false)
      expect(parametros.has('desplazamiento')).toBe(false)
      if (campo !== 'estado') expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
      if (campo !== 'tipo_contraparte') expect(parametros.getAll('tipo_contraparte')).toEqual(['EMPRESA'])
      if (campo !== 'programa_id') expect(parametros.get('programa_id')).toBe('49')
      if (campo !== 'fecha_desde') expect(parametros.get('fecha_desde')).toBe('2026-06-01')
      if (campo !== 'buscar') expect(parametros.get('buscar')).toBe('SOL-77')
    })
    expect(screen.getByLabelText('Finalizado')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Colegio')).toHaveProperty('checked', true)
    expect(screen.getByText('Página 1 de 3')).toBeTruthy()
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/convenios?'))).toHaveLength(consultasAntes + 1)
  })

  it('paginar conserva todos los filtros aplicados y no aplica borradores', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?buscar=SOL-77&estado=VIGENTE&tipo_contraparte=EMPRESA&alcance=INSTITUCIONAL&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01')
    const usuario = userEvent.setup()
    await usuario.click(await screen.findByLabelText('Finalizado'))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-07-01' } })
    const consultasAntes = fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/convenios?')).length
    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('desplazamiento')).toBe('20')
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
      expect(parametros.getAll('tipo_contraparte')).toEqual(['EMPRESA'])
      expect(parametros.get('alcance')).toBe('INSTITUCIONAL')
      expect(parametros.get('tipo_fecha')).toBe('VIGENCIA')
      expect(parametros.get('fecha_desde')).toBe('2026-06-01')
    })
    expect(screen.getByLabelText('Finalizado')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Desde')).toHaveProperty('value', '2026-07-01')
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith('/api/convenios?'))).toHaveLength(consultasAntes + 1)
  })

  it('limpia todos los criterios, el alcance institucional y la página', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?buscar=SOL-77&estado=VIGENTE&tipo_contraparte=EMPRESA&alcance=INSTITUCIONAL&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01&pagina=2')
    await screen.findByLabelText('Vigente')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toBe('/api/convenios?limite=20&solo_formalizados=true'))
    expect(screen.queryByRole('list', { name: 'Filtros activos' })).toBeNull()
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', '')
    expect(screen.getByLabelText('Vigente')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Empresa')).toHaveProperty('checked', false)
    expect(screen.getByLabelText('Desde')).toHaveProperty('value', '')
    expect(screen.getByLabelText('Código, objeto, aliado o NIT')).toHaveProperty('value', '')
    expect(screen.getByText('Página 1 de 3')).toBeTruthy()
  })

  it('mantiene Ver historial cuando hay filtros avanzados y fechas', async () => {
    mockFetch({ items: [{ ...itemReal, puede_ver_detalle: false }], total: 1 })
    renderPagina('/convenios?estado=VIGENTE&tipo_contraparte=EMPRESA&alcance=INSTITUCIONAL&fecha_desde=2026-06-01&tipo_fecha=FORMALIZACION')
    expect((await screen.findByRole('link', { name: 'Ver historial' })).getAttribute('href')).toBe('/convenios/77/historial')
    expect(screen.queryByRole('link', { name: 'Ver' })).toBeNull()
  })

  it('representa alcance PROGRAMA y Buscar sin cambios conserva el filtro sin otra consulta', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?alcance=PROGRAMA&buscar=SOL-77')
    await screen.findByText('41 resultados')
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'PROGRAMA')
    expect(screen.getByRole('button', { name: 'Quitar filtro: Todos los convenios de alcance por programa' })).toBeTruthy()
    const consultasAntes = fetchMock.mock.calls.length
    await userEvent.setup().click(screen.getByRole('button', { name: 'Buscar' }))
    expect(new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams.get('alcance')).toBe('PROGRAMA')
    expect(fetchMock.mock.calls).toHaveLength(consultasAntes)
  })

  it('cambia entre las cuatro opciones y elimina solo los parámetros de programa incompatibles', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?alcance=PROGRAMA&buscar=SOL-77&estado=VIGENTE&fecha_desde=2026-06-01&tipo_fecha=VIGENCIA&pagina=2')
    const usuario = userEvent.setup()
    await screen.findByLabelText('Vigente')
    for (const [opcion, alcance, programa] of [
      ['INSTITUCIONAL', 'INSTITUCIONAL', null],
      ['programa:50', 'PROGRAMA', '50'], ['', null, null], ['PROGRAMA', 'PROGRAMA', null],
    ]) {
      await usuario.selectOptions(screen.getByLabelText('Programa académico'), opcion as string)
      await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
      await waitFor(() => {
        const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
        expect(parametros.get('alcance')).toBe(alcance)
        expect(parametros.get('programa_id')).toBe(programa)
        expect(parametros.get('buscar')).toBe('SOL-77')
        expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
        expect(parametros.get('fecha_desde')).toBe('2026-06-01')
        expect(parametros.has('desplazamiento')).toBe(false)
      })
    }
  })

  it('restaura todos los programas, un programa específico e institucional con Atrás/Adelante', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 1 })
    renderPagina('/convenios?alcance=PROGRAMA')
    const usuario = userEvent.setup()
    await screen.findByLabelText('Vigente')
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), 'programa:49')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('programa_id=49'))
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), 'INSTITUCIONAL')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('alcance=INSTITUCIONAL'))
    await usuario.click(screen.getByRole('button', { name: 'Volver atrás' }))
    await waitFor(() => expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'programa:49'))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('programa_id=49'))
    await usuario.click(screen.getByRole('button', { name: 'Volver atrás' }))
    await waitFor(() => expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'PROGRAMA'))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('alcance')).toBe('PROGRAMA')
      expect(parametros.has('programa_id')).toBe(false)
    })
    await usuario.click(screen.getByRole('button', { name: 'Ir adelante' }))
    await waitFor(() => expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'programa:49'))
    await usuario.click(screen.getByRole('button', { name: 'Ir adelante' }))
    await waitFor(() => expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'INSTITUCIONAL'))
  })

  it('pagina y quita alcance PROGRAMA preservando los otros filtros y borradores', async () => {
    const fetchMock = mockFetch({ items: [itemReal], total: 41 })
    renderPagina('/convenios?alcance=PROGRAMA&buscar=SOL-77&estado=VIGENTE&tipo_fecha=VIGENCIA&fecha_desde=2026-06-01')
    const usuario = userEvent.setup()
    await usuario.click(await screen.findByLabelText('Finalizado'))
    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('alcance')).toBe('PROGRAMA')
      expect(parametros.get('desplazamiento')).toBe('20')
      expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
    })
    await usuario.click(screen.getByRole('button', { name: 'Quitar filtro: Todos los convenios de alcance por programa' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.has('alcance')).toBe(false)
      expect(parametros.has('programa_id')).toBe(false)
      expect(parametros.has('desplazamiento')).toBe(false)
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.get('fecha_desde')).toBe('2026-06-01')
      expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
    })
    expect(screen.getByLabelText('Finalizado')).toHaveProperty('checked', true)
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', '')
  })

  it.each(['0', 'abc', '', '-1', '1.5'])('programa_id=%s llega intacto al backend, muestra 422 y se puede quitar', async (identificador) => {
    const fetchMock = vi.fn((url: string) => {
      const parametros = new URL(url, 'http://localhost').searchParams
      if (parametros.has('programa_id')) {
        return Promise.resolve({
          ok: false, status: 422,
          json: async () => ({ detail: [{ loc: ['query', 'programa_id'], msg: 'Invalid integer' }] }),
        })
      }
      return respuesta({ items: [itemReal], total: 41 })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina(`/convenios?buscar=SOL-77&estado=VIGENTE&programa_id=${encodeURIComponent(identificador)}`)
    expect(await screen.findByRole('alert')).toHaveProperty('textContent',
      'El identificador de programa no es válido. Selecciona otro programa o quita el filtro.')
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', `programa:${identificador}`)
    expect(screen.queryByText('41 resultados')).toBeNull()
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(ultimaConsulta(fetchMock)).toContain('alcance=PROGRAMA'))
    // Todas las consultas antes de quitar explícitamente el filtro lo
    // contienen, incluyendo valores vacíos, sin conversiones a NaN.
    for (const [url] of fetchMock.mock.calls) {
      expect(new URL(url, 'http://localhost').searchParams.get('programa_id')).toBe(identificador)
      expect(url).not.toContain('NaN')
    }
    await usuario.click(screen.getByRole('button', { name: `Quitar filtro: Programa solicitado: ${identificador || '(vacío)'}` }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.has('programa_id')).toBe(false)
      expect(parametros.has('alcance')).toBe(false)
      expect(parametros.get('buscar')).toBe('SOL-77')
      expect(parametros.getAll('estado')).toEqual(['VIGENTE'])
    })
    expect(await screen.findByText('41 resultados')).toBeTruthy()
  })

  it.each([
    ['INSTITUCIONAL', '49'], ['OTRO', '49'], ['', '49'],
  ])('alcance=%s con programa_id=%s permanece inválido hasta una elección explícita', async (alcance, programa) => {
    const fetchMock = vi.fn((url: string) => {
      const parametros = new URL(url, 'http://localhost').searchParams
      if (parametros.get('alcance') === alcance) {
        return Promise.resolve({ ok: false, status: 422,
          json: async () => ({ detail: 'La combinación de alcance y programa no es válida.' }),
        })
      }
      return respuesta({ items: [itemReal], total: 1 })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPagina(`/convenios?alcance=${alcance}&programa_id=${programa}&buscar=SOL-77`)
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'La combinación de alcance y programa no es válida.')
    expect(screen.getByLabelText('Programa académico')).toHaveProperty('value', 'URL_INVALIDA')
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    for (const [url] of fetchMock.mock.calls) {
      const parametros = new URL(url, 'http://localhost').searchParams
      expect(parametros.get('alcance')).toBe(alcance)
      expect(parametros.get('programa_id')).toBe(programa)
    }
    await usuario.selectOptions(screen.getByLabelText('Programa académico'), 'PROGRAMA')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => {
      const parametros = new URL(ultimaConsulta(fetchMock), 'http://localhost').searchParams
      expect(parametros.get('alcance')).toBe('PROGRAMA')
      expect(parametros.has('programa_id')).toBe(false)
      expect(parametros.get('buscar')).toBe('SOL-77')
    })
  })

  it('construirQuery preserva IDs inválidos y rechaza números no finitos antes de crear una URL', () => {
    for (const programa_id of [0, '0', 'abc', '']) {
      const parametros = new URLSearchParams(construirQuery({ limite: 20, desplazamiento: 0, programa_id }))
      expect(parametros.get('programa_id')).toBe(String(programa_id))
    }
    for (const programa_id of [NaN, Infinity]) {
      expect(() => construirQuery({ limite: 20, desplazamiento: 0, programa_id })).toThrow('El identificador de programa no es válido.')
    }
  })
})
