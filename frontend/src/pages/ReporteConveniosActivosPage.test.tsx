import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
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

  it('muestra el estado de carga y deshabilita las descargas', () => {
    const fetchMock = vi.fn(() => new Promise(() => {}))
    renderizar(sesionAutorizada, fetchMock)
    expect(screen.getByText('Cargando convenios activos…')).toBeTruthy()
    for (const nombre of ['Descargar PDF', 'Descargar Excel']) {
      const boton = screen.getByRole('button', { name: nombre }) as HTMLButtonElement
      expect(boton.disabled).toBe(true)
      expect(screen.queryByRole('link', { name: nombre })).toBeNull()
    }
  })

  it('muestra el estado de error con botón de reintentar y deshabilita las descargas', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'falló' }), { status: 500 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(
      await screen.findByText('No se pudo consultar el reporte de convenios activos.'),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy()
    for (const nombre of ['Descargar PDF', 'Descargar Excel']) {
      const boton = screen.getByRole('button', { name: nombre }) as HTMLButtonElement
      expect(boton.disabled).toBe(true)
      expect(screen.queryByRole('link', { name: nombre })).toBeNull()
    }
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
        { id: 1, titulo: 'Taller', estado: 'REALIZADA', fecha_planificada: null, fecha_ejecucion: '2026-03-02' },
      ],
    }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([conActividades]), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    expect(await screen.findByText('1 registrada(s)')).toBeTruthy()
  })

  it.each([
    { caso: 'con convenios', datos: [convenioEjemplo] },
    { caso: 'sin convenios', datos: [] },
  ])('habilita las descargas a PDF y Excel al cargar el reporte $caso', async ({ datos }) => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(datos), { status: 200 }),
    )
    renderizar(sesionAutorizada, fetchMock)

    const enlacePdf = await screen.findByRole('link', { name: 'Descargar PDF' }) as HTMLAnchorElement
    const enlaceExcel = screen.getByRole('link', { name: 'Descargar Excel' }) as HTMLAnchorElement
    expect(enlacePdf.getAttribute('href')).toBe('/api/convenios/reportes/activos/pdf')
    expect(enlaceExcel.getAttribute('href')).toBe('/api/convenios/reportes/activos/excel')
    expect(screen.queryByRole('button', { name: 'Descargar PDF' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Descargar Excel' })).toBeNull()
  })

it('HT-11: mantiene la estructura de la tabla con textos extensos', async () => {
  const textoLargo =
    'Universidad Internacional de Cooperación Académica y Desarrollo Institucional'

  const convenioLargo: ConvenioReporteActivo = {
    ...convenioEjemplo,
    aliado: textoLargo,
    objeto: textoLargo,
    unidad_organizacional: textoLargo,
    responsable: textoLargo,
  }

  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify([convenioLargo]), { status: 200 }),
  )

  renderizar(sesionAutorizada, fetchMock)

  const tabla = await screen.findByRole('table')
  const contenedor = screen.getByRole('region', {
    name: 'Tabla de convenios activos',
  })

  expect(tabla.classList.contains('reporte-activos-tabla')).toBe(true)
  expect(contenedor.classList.contains('reporte-activos-container')).toBe(true)
  expect(screen.getAllByText(textoLargo).length).toBe(4)
  expect(screen.getAllByRole('columnheader')).toHaveLength(9)
  expect(screen.getByRole('link', { name: 'Ver convenio' })).toBeTruthy()
})

})
