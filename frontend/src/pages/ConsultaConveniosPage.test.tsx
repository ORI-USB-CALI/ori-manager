import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useNavigate } from 'react-router-dom'
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
  puede_ver_detalle: true,
}

function NavegacionPrueba() {
  const navegar = useNavigate()
  return <button onClick={() => navegar(-1)}>Volver atrás</button>
}

function renderPagina(entrada = '/convenios') {
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
    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/convenios?limite=20'))
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
})
