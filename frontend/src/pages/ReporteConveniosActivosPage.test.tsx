import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ReporteConveniosActivosPage } from './ReporteConveniosActivosPage'
import type { ConvenioReporteActivo } from './reportes'

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

const convenioEjemplo: ConvenioReporteActivo = {
  id: 10,
  codigo: 'CON-10',
  objeto: 'Movilidad académica',
  estado: 'VIGENTE',
  aliado: 'Universidad Aliada',
  tipo_convenio: 'Marco',
  unidad_organizacional: 'Facultad de Ingeniería',
  responsable: 'Gestora ORI',
  fecha_inicio: '2026-01-01',
  fecha_vencimiento: '2027-01-01',
  actividades: [],
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
        <ReporteConveniosActivosPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ReporteConveniosActivosPage', () => {
  it('no muestra nada si el usuario no tiene el permiso', () => {
    renderizar(sesionSinPermiso)
    expect(screen.queryByText('Reporte de convenios activos')).toBeNull()
  })

  it('muestra el estado de carga', () => {
    const fetchMock = vi.fn(() => new Promise(() => {}))
    renderizar(sesionAutorizada, fetchMock)
    expect(screen.getByText('Cargando convenios activos…')).toBeTruthy()
  })

  it('muestra el estado de error con botón de reintentar', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'falló' }), { status: 500 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(
      await screen.findByText('No se pudo consultar el reporte de convenios activos.'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy()
  })

  it('muestra el estado vacío cuando no hay convenios activos', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(await screen.findByText('No hay convenios activos para mostrar.')).toBeTruthy()
  })

  it('lista los convenios con su información principal', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([convenioEjemplo]), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(await screen.findByText('CON-10')).toBeTruthy()
    expect(screen.getByText('Universidad Aliada')).toBeTruthy()
    expect(screen.getByText('Marco')).toBeTruthy()
    expect(screen.getByText('Facultad de Ingeniería')).toBeTruthy()
    expect(screen.getByText('Gestora ORI')).toBeTruthy()
    expect(screen.getByText('Sin actividades registradas')).toBeTruthy()
    expect(screen.getByText('VIGENTE')).toBeTruthy()
  })

  it('muestra el número de actividades cuando el convenio tiene registradas', async () => {
    const conActividades: ConvenioReporteActivo = {
      ...convenioEjemplo,
      actividades: [
        { id: 1, titulo: 'Taller', estado: 'REALIZADA', fecha_planificada: null, fecha_ejecucion: null },
      ],
    }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([conActividades]), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(await screen.findByText('1 registrada(s)')).toBeTruthy()
  })

  it('ofrece enlaces de descarga a PDF y Excel apuntando al backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([convenioEjemplo]), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const enlacePdf = screen.getByRole('link', { name: 'Descargar PDF' }) as HTMLAnchorElement
    const enlaceExcel = screen.getByRole('link', { name: 'Descargar Excel' }) as HTMLAnchorElement
    expect(enlacePdf.getAttribute('href')).toBe('/api/convenios/reportes/activos/pdf')
    expect(enlaceExcel.getAttribute('href')).toBe('/api/convenios/reportes/activos/excel')
  })
})
