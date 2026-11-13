import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type CodigoRol, ETIQUETAS_ROL, type Permiso, type Sesion } from '../auth/sesion'
import type { ElementoNav } from '../components/HeaderNav'
import { crearNavegacion } from './navigation'
import { NotificationProvider } from './notifications/Notifications'
import { router } from './router'

/**
 * HT-18 CA-04: navegación y permisos por perfil sobre el router real.
 *
 * El frontend no conoce la matriz rol → permisos (llega en la sesión), así que
 * se copia aquí la de `backend/src/backend/core/permisos.py` (PERMISOS_POR_ROL).
 * Si esa matriz cambia, esta copia debe actualizarse con ella.
 */
const PERMISOS_SOLICITANTE: Permiso[] = [
  'solicitudes.crear',
  'solicitudes.ver_propias',
  'solicitudes.editar_propias',
  'solicitudes.radicar',
  'convenios.revisar_contraparte_propia',
]

const PERMISOS_GESTOR: Permiso[] = [
  'aliados.ver',
  'aliados.editar',
  'aliados.cambiar_estado',
  'aliados.corregir_identificacion',
  'convenios.ver',
  'convenios.crear',
  'convenios.editar',
  'solicitudes.ver_recibidas',
  'solicitudes.gestionar_recibidas',
  'convenios.ver_alertas_vencimiento',
  'convenios.gestionar_renovaciones',
  'convenios.gestionar_revision_contraparte',
  'convenios.gestionar_firmas',
  'convenios.evaluar',
  'convenios.gestionar_soportes',
  'convenios.ver_reportes',
]

const PERMISOS_POR_ROL: Record<CodigoRol, Permiso[]> = {
  ADMINISTRADOR_ORI: [
    ...PERMISOS_GESTOR,
    'usuarios.ver',
    'usuarios.crear',
    'usuarios.editar',
    'usuarios.cambiar_rol',
    'usuarios.cambiar_estado',
    'auditoria.ver',
  ],
  GESTOR_ORI: PERMISOS_GESTOR,
  REVISOR_ORI: ['aliados.ver', 'convenios.ver', 'convenios.revisar'],
  SOLICITANTE_INTERNO: PERMISOS_SOLICITANTE,
  SOLICITANTE_EXTERNO: PERMISOS_SOLICITANTE,
}

const ROLES = Object.keys(PERMISOS_POR_ROL) as CodigoRol[]
const ROLES_ORI: CodigoRol[] = ['ADMINISTRADOR_ORI', 'GESTOR_ORI', 'REVISOR_ORI']
const GESTION_ORI: CodigoRol[] = ['ADMINISTRADOR_ORI', 'GESTOR_ORI']
const SOLICITANTES: CodigoRol[] = ['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO']

const MENSAJE_DENEGADO = 'No tiene permiso para consultar esta sección.'

// Rutas del convenio y su documentación, con los roles que pueden abrirlas.
const RUTAS: Array<{ ruta: string; permitidos: CodigoRol[] }> = [
  { ruta: '/convenios', permitidos: ROLES_ORI },
  { ruta: '/convenios/41', permitidos: ROLES_ORI },
  { ruta: '/convenios/41/historial', permitidos: ROLES_ORI },
  { ruta: '/convenios/41/versiones/1', permitidos: ROLES_ORI },
  { ruta: '/convenios/41/firmas/documento-aprobado', permitidos: GESTION_ORI },
  { ruta: '/ori/solicitudes/5', permitidos: GESTION_ORI },
  { ruta: '/revisiones-juridicas', permitidos: ['REVISOR_ORI'] },
  { ruta: '/admin/bitacora', permitidos: ['ADMINISTRADOR_ORI'] },
  { ruta: '/solicitudes', permitidos: SOLICITANTES },
  { ruta: '/solicitudes/5/historial', permitidos: SOLICITANTES },
  { ruta: '/revisiones-contraparte', permitidos: SOLICITANTES },
]

const CASOS = ROLES.flatMap((rol) =>
  RUTAS.map(({ ruta, permitidos }) => ({ rol, ruta, permitido: permitidos.includes(rol) })),
)

class SocketPrueba {
  close = vi.fn()
  constructor(public url: string) {}
}

function sesionDe(rol: CodigoRol): Sesion {
  return {
    id: 7, correo: 'persona@usb.edu.co', nombre_completo: 'Persona de prueba', activo: true,
    tipo_usuario: rol === 'SOLICITANTE_EXTERNO' ? 'EXTERNO' : 'INTERNO',
    rol: { codigo: rol, nombre: ETIQUETAS_ROL[rol] },
    permisos: PERMISOS_POR_ROL[rol],
  }
}

function montar(sesion: Sesion | null, ruta: string) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesion)
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/notificaciones')) return Response.json([])
    if (url.endsWith('/notificaciones/ws-ticket')) return Response.json({ ticket: 'ticket-prueba' })
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  vi.stubGlobal('WebSocket', SocketPrueba)
  const enrutador = createMemoryRouter(router.routes, { initialEntries: [ruta] })
  render(
    <QueryClientProvider client={cliente}>
      <NotificationProvider>
        <RouterProvider router={enrutador} />
      </NotificationProvider>
    </QueryClientProvider>,
  )
  return { enrutador, fetch }
}

function etiquetas(navegacion: ElementoNav[]): string[] {
  return navegacion.flatMap((elemento) =>
    'enlaces' in elemento ? elemento.enlaces.map((enlace) => enlace.label) : [elemento.label],
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('HT-18 CA-04: rutas del convenio y su documentación por perfil', () => {
  it.each(CASOS.filter((caso) => caso.permitido))('$rol puede abrir $ruta', async ({ rol, ruta }) => {
    const { enrutador } = montar(sesionDe(rol), ruta)

    const contenido = await waitFor(() => {
      const principal = document.querySelector('main.page')
      expect(principal?.textContent).toBeTruthy()
      return principal as HTMLElement
    })
    expect(enrutador.state.location.pathname).toBe(ruta)
    expect(contenido.textContent).not.toContain(MENSAJE_DENEGADO)
    expect(contenido.textContent).not.toContain('La página solicitada no existe.')
  })

  it.each(CASOS.filter((caso) => !caso.permitido))('$rol no puede abrir $ruta', async ({ rol, ruta }) => {
    const { enrutador, fetch } = montar(sesionDe(rol), ruta)

    expect(await screen.findByRole('heading', { level: 1, name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.getByText(MENSAJE_DENEGADO)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Volver al inicio' }).getAttribute('href')).toBe('/')
    expect(enrutador.state.location.pathname).toBe(ruta)
    // La página restringida no llega a montarse: no pide sus datos a la API.
    expect(fetch.mock.calls.some(([url]) => url.startsWith(`/api${ruta}`))).toBe(false)
    expect(fetch.mock.calls.some(([url]) => url.startsWith('/api/auditoria'))).toBe(false)
  })

  it('sin sesión redirige al inicio de sesión en lugar de mostrar el convenio', async () => {
    const { enrutador } = montar(null, '/convenios/41')

    await waitFor(() => expect(enrutador.state.location.pathname).toBe('/login'))
    expect(screen.queryByText(MENSAJE_DENEGADO)).toBeNull()
  })
})

describe('HT-18 CA-04: opciones del menú por perfil', () => {
  const MENU_GESTOR = [
    'Inicio', 'Aliados', 'Solicitudes recibidas',
    'Consulta de convenios', 'Tablero de convenios', 'Crear convenio manual',
    'Renovaciones', 'Reportes', 'Estadísticas',
  ]
  const MENU_SOLICITANTE = ['Inicio', 'Mis solicitudes']

  it.each<[CodigoRol, string[]]>([
    ['ADMINISTRADOR_ORI', [...MENU_GESTOR, 'Usuarios', 'Bitácora']],
    ['GESTOR_ORI', MENU_GESTOR],
    ['REVISOR_ORI', ['Inicio', 'Aliados', 'Consulta de convenios', 'Tablero de convenios', 'Revisiones jurídicas']],
    ['SOLICITANTE_INTERNO', MENU_SOLICITANTE],
    ['SOLICITANTE_EXTERNO', MENU_SOLICITANTE],
  ])('%s recibe exactamente sus opciones', (rol, esperadas) => {
    const navegacion = crearNavegacion((permiso) => PERMISOS_POR_ROL[rol].includes(permiso))

    expect(etiquetas(navegacion)).toEqual(esperadas)
  })
})
