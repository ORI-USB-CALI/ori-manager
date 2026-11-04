import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ReporteEstadisticasConveniosPage } from './ReporteEstadisticasConveniosPage'
import type { ReporteEstadisticoConvenios } from './estadisticasConvenios'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const sesionAutorizada: Sesion = {
  id: 1,
  correo: 'admin@example.com',
  nombre_completo: 'Admin',
  activo: true,
  tipo_usuario: 'INTERNO',
  rol: { codigo: 'ADMINISTRADOR_ORI', nombre: 'Administrador ORI' },
  permisos: ['convenios.ver_reportes'],
}

const sesionSinPermiso: Sesion = {
  ...sesionAutorizada,
  rol: { codigo: 'REVISOR_ORI', nombre: 'Revisor ORI' },
  permisos: [],
}

const reporteConDatos: ReporteEstadisticoConvenios = {
  datos_suficientes: true,
  total_convenios: 3,
  por_estado_contractual: [{ etiqueta: 'VIGENTE', cantidad: 3 }],
  por_vigencia_activa: [{ etiqueta: 'Vigencia activa', cantidad: 3 }],
  por_estado_aliado: [{ etiqueta: 'Aliado activo', cantidad: 3 }],
  por_tipo_aliado: [{ etiqueta: 'Universidad', cantidad: 3 }],
  por_pais: [{ etiqueta: 'Colombia', cantidad: 3 }],
}

const reporteSinDatos: ReporteEstadisticoConvenios = {
  datos_suficientes: false,
  total_convenios: 0,
  por_estado_contractual: [],
  por_vigencia_activa: [],
  por_estado_aliado: [],
  por_tipo_aliado: [],
  por_pais: [],
}

function renderizar(sesion: Sesion, fetchMock = vi.fn()) {
  vi.stubGlobal('fetch', fetchMock)
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  cliente.setQueryData(CLAVE_SESION, sesion)
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <ReporteEstadisticasConveniosPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ReporteEstadisticasConveniosPage', () => {
  it('no muestra nada si el usuario no tiene el permiso', () => {
    renderizar(sesionSinPermiso)
    expect(screen.queryByText('Reporte estadístico de convenios')).toBeNull()
  })

  it('muestra el estado de carga', () => {
    const fetchMock = vi.fn(() => new Promise(() => {}))
    renderizar(sesionAutorizada, fetchMock)
    expect(screen.getByText('Cargando estadísticas…')).toBeTruthy()
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect((screen.getByRole('button', { name: 'Descargar PDF' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Descargar Excel' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('muestra el estado de error con botón de reintentar', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'falló' }), { status: 500 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(
      await screen.findByText('No se pudo consultar el reporte estadístico de convenios.'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy()
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect((screen.getByRole('button', { name: 'Descargar PDF' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Descargar Excel' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('muestra el mensaje de datos insuficientes (CA-03)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteSinDatos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(
      await screen.findByText('No hay datos suficientes para generar el reporte estadístico.'),
    ).toBeTruthy()
    expect(screen.queryAllByRole('figure')).toHaveLength(0)
    expect(screen.queryAllByRole('table')).toHaveLength(0)
  })

  it('muestra las agrupaciones cuando hay datos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteConDatos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(await screen.findByText('Por estado contractual')).toBeTruthy()
    expect(screen.getByText('Por vigencia activa')).toBeTruthy()
    expect(screen.getByText('Por estado del aliado')).toBeTruthy()
    expect(screen.getByText('Por tipo de aliado')).toBeTruthy()
    expect(screen.getByText('Por país')).toBeTruthy()
    expect(screen.getAllByRole('figure')).toHaveLength(5)
    expect(within(screen.getByRole('figure', { name: 'Por país' })).getByText('Colombia')).toBeTruthy()
  })

  it('ofrece enlaces de descarga a PDF y Excel apuntando al backend sin filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteConDatos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)
    await screen.findByRole('link', { name: 'Descargar PDF' })

    const enlacePdf = screen.getByRole('link', { name: 'Descargar PDF' }) as HTMLAnchorElement
    const enlaceExcel = screen.getByRole('link', { name: 'Descargar Excel' }) as HTMLAnchorElement
    expect(enlacePdf.getAttribute('href')).toBe('/api/convenios/reportes/estadisticas/pdf')
    expect(enlaceExcel.getAttribute('href')).toBe('/api/convenios/reportes/estadisticas/excel')
  })

  it('refleja el filtro de estado en la consulta y en los enlaces de descarga', async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify(reporteConDatos), { status: 200 })),
    )
    renderizar(sesionAutorizada, fetchMock)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const selectEstado = screen.getByLabelText('Estado del convenio') as HTMLSelectElement
    fireEvent.change(selectEstado, { target: { value: 'VIGENTE' } })

    await waitFor(() => {
      const enlacePdf = screen.getByRole('link', { name: 'Descargar PDF' }) as HTMLAnchorElement
      expect(enlacePdf.getAttribute('href')).toBe(
        '/api/convenios/reportes/estadisticas/pdf?estado=VIGENTE',
      )
    })
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('?estado=VIGENTE'))).toBe(true)
  })

  it('representa categorías, cantidades y proporciones reales y permite consultar la tabla', async () => {
    const nombreLargo = 'País con un nombre extenso para comprobar etiquetas completas y legibles'
    const datos = {
      ...reporteConDatos,
      total_convenios: 9,
      por_pais: [{ etiqueta: nombreLargo, cantidad: 6 }, { etiqueta: 'México', cantidad: 3 }],
    }
    renderizar(sesionAutorizada, vi.fn().mockResolvedValue(new Response(JSON.stringify(datos))))
    const grafico = await screen.findByRole('figure', { name: 'Por país' })
    const filas = within(grafico).getAllByRole('listitem')
    expect(within(filas[0]).getByText(nombreLargo)).toBeTruthy()
    expect(within(filas[0]).getByText('6')).toBeTruthy()
    expect(within(filas[1]).getByText('México')).toBeTruthy()
    expect(within(filas[1]).getByText('3')).toBeTruthy()
    expect((filas[0].querySelector('.estadisticas-barra') as HTMLElement).style.width).toBe('100%')
    expect((filas[1].querySelector('.estadisticas-barra') as HTMLElement).style.width).toBe('50%')
    const tarjeta = grafico.closest('section')!
    await userEvent.click(within(tarjeta).getByText('Ver tabla de datos'))
    const tabla = within(tarjeta).getByRole('table', { name: 'Por país' })
    expect(within(tabla).getByText(nombreLargo)).toBeTruthy()
    expect(within(tabla).getByText('6')).toBeTruthy()
    expect(within(tabla).getByText('México')).toBeTruthy()
    expect(within(tabla).getByText('3')).toBeTruthy()
  })

  it.each([
    { datos_suficientes: false, total_convenios: 3 },
    { datos_suficientes: true, total_convenios: 0 },
  ])('omite gráficos y tablas si los indicadores no permiten representar datos: %j', async (indicadores) => {
    const datos = { ...reporteConDatos, ...indicadores }
    renderizar(sesionAutorizada, vi.fn().mockResolvedValue(new Response(JSON.stringify(datos))))
    await screen.findByText('No hay datos suficientes para generar el reporte estadístico.')
    expect(screen.queryAllByRole('figure')).toHaveLength(0)
    expect(screen.queryAllByRole('table', { hidden: true })).toHaveLength(0)
    expect(screen.queryByText('Colombia')).toBeNull()
  })

  it('actualiza los gráficos y conserva todos los filtros en ambas descargas', async () => {
    const filtrado = {
      ...reporteConDatos,
      total_convenios: 1,
      por_estado_contractual: [{ etiqueta: 'EN_TRAMITE', cantidad: 1 }],
      por_vigencia_activa: [{ etiqueta: 'Vigencia no activa', cantidad: 1 }],
      por_estado_aliado: [{ etiqueta: 'Contraparte propuesta (sin formalizar)', cantidad: 1 }],
      por_tipo_aliado: [{ etiqueta: 'Empresa', cantidad: 1 }],
      por_pais: [{ etiqueta: 'Costa Rica', cantidad: 1 }],
    }
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(
      new Response(JSON.stringify(url.includes('?') ? filtrado : reporteConDatos)),
    ))
    renderizar(sesionAutorizada, fetchMock)
    await screen.findByRole('figure', { name: 'Por país' })
    fireEvent.change(screen.getByLabelText('Estado del convenio'), { target: { value: 'EN_TRAMITE' } })
    fireEvent.change(screen.getByLabelText('Tipo de aliado'), { target: { value: 'EMPRESA' } })
    fireEvent.change(screen.getByLabelText('País'), { target: { value: 'Costa Rica' } })
    await waitFor(() => {
      const enlace = screen.getByRole('link', { name: 'Descargar PDF' })
      const params = new URL(enlace.getAttribute('href')!, 'http://localhost').searchParams
      expect(Object.fromEntries(params)).toEqual({ estado: 'EN_TRAMITE', tipo_aliado: 'EMPRESA', pais: 'Costa Rica' })
    })
    const grafico = screen.getByRole('figure', { name: 'Por país' })
    expect(within(grafico).getByText('Costa Rica')).toBeTruthy()
    expect(within(grafico).getByText('1')).toBeTruthy()
    expect(within(grafico).queryByText('Colombia')).toBeNull()
    const excel = screen.getByRole('link', { name: 'Descargar Excel' })
    expect(excel.getAttribute('href')).toBe('/api/convenios/reportes/estadisticas/excel?estado=EN_TRAMITE&tipo_aliado=EMPRESA&pais=Costa+Rica')
    fireEvent.change(screen.getByLabelText('Estado del aliado'), { target: { value: 'false' } })
    await waitFor(() => expect(screen.getByRole('link', { name: 'Descargar Excel' }).getAttribute('href')).toContain('aliado_activo=false'))
  })

  it('deshabilita descargas durante una actualización y permite reintentar tras un error', async () => {
    let resolver: (respuesta: Response) => void = () => {}
    const pendiente = new Promise<Response>((resolve) => { resolver = resolve })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(reporteConDatos)))
      .mockReturnValueOnce(pendiente)
      .mockResolvedValueOnce(new Response(JSON.stringify(reporteConDatos)))
    renderizar(sesionAutorizada, fetchMock)
    await screen.findByRole('link', { name: 'Descargar PDF' })
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }))
    await screen.findByRole('button', { name: 'Actualizando…' })
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect((screen.getByRole('button', { name: 'Descargar Excel' }) as HTMLButtonElement).disabled).toBe(true)
    resolver(new Response(JSON.stringify({ detail: 'falló' }), { status: 500 }))
    await screen.findByRole('alert')
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(screen.queryAllByRole('figure')).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await screen.findByRole('link', { name: 'Descargar Excel' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
