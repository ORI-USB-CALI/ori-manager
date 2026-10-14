import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Permiso, type Sesion } from '../auth/sesion'
import { BitacoraPage } from './BitacoraPage'
import type { PaginaBitacora } from './bitacora'

function sesion(permisos: Permiso[]): Sesion {
  return {
    id: 1,
    correo: 'admin@example.com',
    nombre_completo: 'Administradora ORI',
    activo: true,
    tipo_usuario: 'INTERNO',
    rol: { codigo: 'ADMINISTRADOR_ORI', nombre: 'Administrador ORI' },
    permisos,
  }
}

const gestora = { id: 3, nombre_completo: 'Gestora ORI', correo: 'gestora@example.com' }

const pagina: PaginaBitacora = {
  items: [
    {
      id: 7,
      fecha_hora: '2026-10-01T15:00:00Z',
      usuario: gestora,
      rol: 'GESTOR_ORI',
      entidad: 'solicitud',
      registro_id: 15,
      accion: 'UPDATE',
      campo: 'estado',
      valor_anterior: 'RADICADA',
      valor_nuevo: 'APROBADA',
      contexto: 'Decisión de la solicitud',
    },
    {
      id: 6,
      fecha_hora: '2026-09-30T15:00:00Z',
      usuario: gestora,
      rol: null,
      entidad: 'convenio',
      registro_id: 4,
      accion: 'INSERT',
      campo: null,
      valor_anterior: null,
      valor_nuevo: null,
      contexto: null,
    },
  ],
  total: 2,
}

const vacia: PaginaBitacora = { items: [], total: 0 }

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function simularApi(auditoria: () => Response) {
  const fetch = vi.fn(async (url: string) => (
    url.startsWith('/api/auditoria?') ? auditoria() : respuesta(404, { detail: 'Not Found' })
  ))
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function renderizar(permisos: Permiso[] = ['auditoria.ver']) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesion(permisos))
  render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <BitacoraPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function urlsAuditoria(fetch: ReturnType<typeof simularApi>): string[] {
  return fetch.mock.calls.map(([url]) => url).filter((url) => url.startsWith('/api/auditoria?'))
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('BitacoraPage', () => {
  it('muestra los registros en la tabla', async () => {
    simularApi(() => respuesta(200, pagina))
    renderizar()

    const tabla = await screen.findByRole('table', { name: 'Bitácora de cambios' })
    const filas = within(tabla).getAllByRole('row')
    expect(filas).toHaveLength(3)
    expect(within(filas[1]).getByText('solicitud #15')).toBeTruthy()
    expect(within(filas[1]).getByText('Gestor ORI')).toBeTruthy()
    expect(within(filas[1]).getByText('gestora@example.com')).toBeTruthy()
    expect(within(filas[1]).getByText('Modificación')).toBeTruthy()
    expect(within(filas[1]).getByText('RADICADA')).toBeTruthy()
    expect(within(filas[1]).getByText('APROBADA')).toBeTruthy()
    expect(within(filas[1]).getByText('Decisión de la solicitud')).toBeTruthy()
    expect(within(filas[2]).getByText('Creación')).toBeTruthy()
    // Rol, campo, valor anterior, valor nuevo y contexto vacíos.
    expect(within(filas[2]).getAllByText('—')).toHaveLength(5)
    expect(screen.getByText('Página 1 de 1')).toBeTruthy()
  })

  it('envía los filtros elegidos con el contrato de /auditoria', async () => {
    const fetch = simularApi(() => respuesta(200, pagina))
    const usuario = userEvent.setup()
    renderizar()
    await screen.findByRole('table', { name: 'Bitácora de cambios' })
    expect(Object.fromEntries(new URL(urlsAuditoria(fetch)[0], 'http://localhost').searchParams)).toEqual({
      orden: 'desc',
      limite: '25',
      desplazamiento: '0',
    })

    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-09-01' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-09-30' } })
    await usuario.type(screen.getByLabelText('Entidad'), 'solicitud')
    await usuario.selectOptions(screen.getByLabelText('Rol'), 'GESTOR_ORI')
    await usuario.selectOptions(screen.getByLabelText('Acción'), 'UPDATE')
    await usuario.type(screen.getByLabelText('N.º de registro'), '15')
    await usuario.type(screen.getByLabelText('ID de usuario'), '3')
    await usuario.selectOptions(screen.getByLabelText('Orden'), 'asc')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => expect(urlsAuditoria(fetch)).toHaveLength(2))
    const url = urlsAuditoria(fetch)[1]
    expect(url).toContain('desde=2026-09-01T00%3A00%3A00-05%3A00')
    expect(Object.fromEntries(new URL(url, 'http://localhost').searchParams)).toEqual({
      desde: '2026-09-01T00:00:00-05:00',
      hasta: '2026-09-30T23:59:59.999-05:00',
      entidad: 'solicitud',
      rol: 'GESTOR_ORI',
      accion: 'UPDATE',
      registro_id: '15',
      usuario_id: '3',
      orden: 'asc',
      limite: '25',
      desplazamiento: '0',
    })
  })

  it('pide la siguiente página con el desplazamiento correspondiente', async () => {
    const fetch = simularApi(() => respuesta(200, { ...pagina, total: 60 }))
    const usuario = userEvent.setup()
    renderizar()
    await screen.findByText('Página 1 de 3')

    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }))

    expect(await screen.findByText('Página 2 de 3')).toBeTruthy()
    const parametros = new URL(urlsAuditoria(fetch).at(-1)!, 'http://localhost').searchParams
    expect(parametros.get('limite')).toBe('25')
    expect(parametros.get('desplazamiento')).toBe('25')
  })

  it('muestra el estado vacío', async () => {
    simularApi(() => respuesta(200, vacia))
    renderizar()

    expect(await screen.findByText('Aún no hay registros en la bitácora.')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('muestra acceso denegado sin llamar a la API a quien no tiene permiso', () => {
    const fetch = simularApi(() => respuesta(200, pagina))
    renderizar(['convenios.ver'])

    expect(screen.getByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.getByText('No tiene permiso para consultar la bitácora de cambios.')).toBeTruthy()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('muestra acceso denegado cuando el servidor responde 403', async () => {
    simularApi(() => respuesta(403, { detail: 'No tiene permiso para esta operación' }))
    renderizar()

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Volver al inicio' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('deshabilita Buscar si el rango de fechas está invertido', async () => {
    const fetch = simularApi(() => respuesta(200, pagina))
    renderizar()
    await screen.findByRole('table', { name: 'Bitácora de cambios' })

    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-05' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-10-01' } })

    expect(screen.getByRole('alert').textContent).toContain('no puede ser posterior')
    expect((screen.getByRole('button', { name: 'Buscar' }) as HTMLButtonElement).disabled).toBe(true)
    expect(urlsAuditoria(fetch)).toHaveLength(1)
  })
})
