import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  })

  it('muestra el mensaje de datos insuficientes (CA-03)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteSinDatos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(
      await screen.findByText('No hay datos suficientes para generar el reporte estadístico.'),
    ).toBeTruthy()
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
    expect(screen.getByText('Colombia')).toBeTruthy()
  })

  it('ofrece enlaces de descarga a PDF y Excel apuntando al backend sin filtros', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteConDatos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const enlacePdf = screen.getByRole('link', { name: 'Descargar PDF' }) as HTMLAnchorElement
    const enlaceExcel = screen.getByRole('link', { name: 'Descargar Excel' }) as HTMLAnchorElement
    expect(enlacePdf.getAttribute('href')).toBe('/api/convenios/reportes/estadisticas/pdf')
    expect(enlaceExcel.getAttribute('href')).toBe('/api/convenios/reportes/estadisticas/excel')
  })

  it('refleja el filtro de estado en la consulta y en los enlaces de descarga', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reporteConDatos), { status: 200 }),
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
  })
})
