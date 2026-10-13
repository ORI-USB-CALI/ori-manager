import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type CodigoRol, type Permiso, type Sesion } from '../auth/sesion'
import type { ActividadUtilizacion } from '../pages/actividadesUtilizacion'
import type { EstadoConvenio } from '../pages/epica02'
import { ActividadesUtilizacionConvenio } from './ActividadesUtilizacionConvenio'

const actividad: ActividadUtilizacion = {
  id: 7,
  convenio_id: 41,
  estado: 'REALIZADA',
  fecha_ejecucion: '2026-09-15',
  titulo: 'Movilidad académica de dos estudiantes de Ingeniería',
  descripcion: 'Participación en intercambio académico durante el semestre 2026-2',
  responsable_nombre: 'Facultad de Ingeniería',
  observaciones: null,
  registrado_por_id: 1,
  creado_en: '2026-10-13T15:00:00Z',
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function respuestaJson(cuerpo: unknown, status = 200) {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function preparar({
  estado = 'VIGENTE',
  rol = 'GESTOR_ORI',
  listado = [],
  registro = respuestaJson(actividad, 201),
}: {
  estado?: EstadoConvenio
  rol?: CodigoRol
  listado?: ActividadUtilizacion[]
  registro?: Response
} = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const permisos: Permiso[] = rol === 'GESTOR_ORI' || rol === 'ADMINISTRADOR_ORI'
    ? ['convenios.ver', 'convenios.editar']
    : ['convenios.ver']
  const sesion: Sesion = {
    id: 1, correo: 'usuario@example.com', nombre_completo: 'Usuario', activo: true,
    tipo_usuario: 'INTERNO', rol: { codigo: rol, nombre: rol }, permisos,
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  let consultas = 0
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url !== '/api/convenios/41/actividades-utilizacion') return Promise.resolve(respuestaJson({}, 404))
    if (init?.method === 'POST') return Promise.resolve(registro)
    consultas += 1
    return Promise.resolve(respuestaJson(consultas === 1 ? listado : [actividad, ...listado]))
  })
  vi.stubGlobal('fetch', fetch)
  const notify = vi.fn()
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <ActividadesUtilizacionConvenio convenioId={41} estado={estado} />
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { fetch, notify, usuario: userEvent.setup() }
}

async function completarFormulario(usuario: ReturnType<typeof userEvent.setup>) {
  await usuario.type(screen.getByLabelText('Fecha *'), '2026-09-15')
  await usuario.type(screen.getByLabelText('Responsable *'), '  Facultad de Ingeniería ')
  await usuario.type(screen.getByLabelText('Actividad *'), actividad.titulo)
  await usuario.type(screen.getByLabelText('Descripción *'), actividad.descripcion)
}

describe('actividades de utilización del convenio', () => {
  it('registra una actividad y refresca el listado', async () => {
    const { fetch, notify, usuario } = preparar()
    expect(await screen.findByText('No hay actividades de utilización registradas.')).toBeTruthy()

    await completarFormulario(usuario)
    await usuario.click(screen.getByRole('button', { name: 'Registrar actividad' }))

    await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'success', message: 'Actividad de utilización registrada correctamente.' }))
    const envio = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(envio?.[0]).toBe('/api/convenios/41/actividades-utilizacion')
    expect(JSON.parse(String(envio?.[1]?.body))).toEqual({
      fecha_ejecucion: '2026-09-15',
      titulo: actividad.titulo,
      descripcion: actividad.descripcion,
      responsable_nombre: 'Facultad de Ingeniería',
      observaciones: null,
    })
    expect(await screen.findByText(actividad.titulo)).toBeTruthy()
    expect((screen.getByLabelText('Actividad *') as HTMLInputElement).value).toBe('')
  })

  it('muestra el error del servidor y conserva lo escrito', async () => {
    const detalle = 'La fecha de la actividad debe estar dentro del período de vigencia del convenio'
    const { notify, usuario } = preparar({ registro: respuestaJson({ detail: detalle }, 422) })
    await completarFormulario(usuario)

    await usuario.click(screen.getByRole('button', { name: 'Registrar actividad' }))

    await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'error', message: detalle }))
    expect((screen.getByLabelText('Actividad *') as HTMLInputElement).value).toBe(actividad.titulo)
  })

  it('no envía el formulario si faltan campos obligatorios', async () => {
    const { fetch, usuario } = preparar()
    await screen.findByText('No hay actividades de utilización registradas.')

    await usuario.click(screen.getByRole('button', { name: 'Registrar actividad' }))

    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it.each<EstadoConvenio>(['VIGENTE', 'POR_VENCER'])('ofrece el registro en %s', (estado) => {
    preparar({ estado })
    expect(screen.getByRole('button', { name: 'Registrar actividad' })).toBeTruthy()
  })

  it.each<EstadoConvenio>(['EN_TRAMITE', 'VENCIDO', 'RENOVADO', 'FINALIZADO', 'CANCELADO'])('oculta el registro en %s', (estado) => {
    preparar({ estado })
    expect(screen.queryByRole('button', { name: 'Registrar actividad' })).toBeNull()
  })

  it.each<CodigoRol>(['REVISOR_ORI', 'SOLICITANTE_INTERNO'])('oculta el registro a %s', (rol) => {
    preparar({ rol })
    expect(screen.queryByRole('button', { name: 'Registrar actividad' })).toBeNull()
  })

  it('consulta actividades históricas de un convenio finalizado', async () => {
    preparar({ estado: 'FINALIZADO', listado: [actividad] })

    expect(await screen.findByText(actividad.titulo)).toBeTruthy()
    expect(screen.getByText('Facultad de Ingeniería')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Registrar actividad' })).toBeNull()
  })
})
