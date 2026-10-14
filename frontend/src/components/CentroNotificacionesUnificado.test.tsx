import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppLayout } from '../app/AppLayout'
import type { CodigoRol, Permiso, Sesion } from '../auth/sesion'
import { CLAVE_ALERTAS_VENCIMIENTO, useAlertasVencimiento, type AlertaVencimiento } from '../pages/alertasVencimiento'
import { HomePage } from '../pages/HomePage'
import { CLAVE_NOTIFICACIONES, type Notificacion } from '../pages/notificaciones'
import { CentroNotificaciones } from './CentroNotificaciones'
import { AlertasVencimiento } from './AlertasVencimiento'
import {
  adaptarNotificacion, adaptarVencimientos, contarAsuntosPendientes, type FuenteAvisos,
} from './notificaciones/avisos'

const personal: Notificacion = {
  id: 30, tipo: 'SOLICITUD_DEVUELTA', entidad_tipo: 'SOLICITUD', entidad_id: 51,
  mensaje: 'Corrige tu solicitud SOL-51.', leida: false, leida_en: null,
  resuelta: false, resuelta_en: null, creado_en: '2026-10-14T12:00:00Z',
}

function alerta(dias: number, id = dias): AlertaVencimiento {
  return {
    convenio_id: id, codigo: `CON-${id}`, objeto: `Cooperación ${id}`,
    fecha_vencimiento: '2026-11-13', dias_restantes: dias,
    rango_vencimiento: dias <= 30 ? '0_30' : dias <= 60 ? '31_60' : dias <= 90 ? '61_90' : '91_120',
  }
}

class SocketPrueba {
  static instancias: SocketPrueba[] = []
  onmessage: (() => void) | null = null
  onopen: (() => void) | null = null
  onclose: ((evento: { code: number }) => void) | null = null
  close = vi.fn()
  constructor(public url: string) { SocketPrueba.instancias.push(this) }
}

const clientes: QueryClient[] = []

afterEach(() => {
  cleanup()
  clientes.forEach((cliente) => cliente.clear())
  clientes.length = 0
  focusManager.setFocused(undefined)
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function clienteNuevo() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clientes.push(cliente)
  return cliente
}

function preparar({
  rol = 'GESTOR_ORI', notificaciones = [personal], alertas = [alerta(30)], inicio = false,
}: {
  rol?: CodigoRol; notificaciones?: Notificacion[]; alertas?: AlertaVencimiento[]; inicio?: boolean
} = {}) {
  const autorizado = rol === 'GESTOR_ORI' || rol === 'ADMINISTRADOR_ORI'
  const permisos: Permiso[] = autorizado
    ? ['convenios.ver', 'convenios.ver_alertas_vencimiento', 'convenios.gestionar_renovaciones']
    : rol === 'REVISOR_ORI' ? ['convenios.ver', 'convenios.revisar']
      : ['solicitudes.ver_propias', 'convenios.revisar_contraparte_propia']
  const sesion: Sesion = {
    id: 7, correo: 'persona@example.com', nombre_completo: 'Persona', activo: true,
    tipo_usuario: rol === 'SOLICITANTE_EXTERNO' ? 'EXTERNO' : 'INTERNO',
    rol: { codigo: rol, nombre: rol }, permisos,
  }
  const datos = { notificaciones, alertas }
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/auth/me') return Response.json(sesion)
    if (url === '/api/notificaciones') return Response.json(datos.notificaciones)
    if (url === '/api/convenios/alertas-vencimiento') return Response.json(datos.alertas)
    if (url === '/api/notificaciones/ws-ticket') return Response.json({ ticket: 'ticket-personal' })
    if (url === `/api/notificaciones/${personal.id}/leida`) {
      datos.notificaciones = datos.notificaciones.map((item) => ({ ...item, leida: true }))
      return Response.json({ ...personal, leida: true, resuelta: false })
    }
    if (url === '/api/convenios/revisiones-contraparte') return Response.json([])
    throw new Error(`Petición inesperada: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  SocketPrueba.instancias = []
  vi.stubGlobal('WebSocket', SocketPrueba)
  const cliente = clienteNuevo()
  render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={inicio ? <HomePage /> : <h1>Inicio</h1>} />
            <Route path="/solicitudes/:id" element={<h1>Detalle de solicitud</h1>} />
            <Route path="/convenios/:id" element={<h1>Detalle de convenio</h1>} />
            <Route path="/renovaciones" element={<h1>Gestión de renovaciones</h1>} />
            <Route path="/revisiones-contraparte" element={<h1>Revisiones propias</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const usuario = userEvent.setup()
  const abrir = async () => {
    const boton = await screen.findByRole('button', { name: /^Centro de notificaciones/ })
    await usuario.click(boton)
    return screen.getByRole('region', { name: 'Centro de notificaciones' })
  }
  const llamadas = (url: string) => fetchMock.mock.calls.filter(([destino]) => destino === url).length
  return { usuario, cliente, fetchMock, datos, abrir, llamadas }
}

describe('Centro unificado en AppLayout', () => {
  it('renderiza una sola campana y suma pendientes sin duplicar ni contar resueltos', async () => {
    const { abrir } = preparar({
      notificaciones: [personal, personal, { ...personal, id: 31, leida: true },
        { ...personal, id: 32, resuelta: true }],
      alertas: [alerta(30), alerta(30), alerta(120), alerta(121), alerta(-1)],
    })
    await screen.findByRole('button', { name: 'Centro de notificaciones: 4 asuntos pendientes de atención' })
    expect(document.querySelectorAll('.bandeja-notificaciones-trigger')).toHaveLength(1)
    const panel = await abrir()
    expect(within(panel).getByText('4 asuntos pendientes de atención')).toBeTruthy()
    expect(within(panel).getAllByRole('article')).toHaveLength(5)
    expect(within(panel).getAllByText('Atendida')).toHaveLength(1)
  })

  it('filtra categorías y conserva el contador combinado', async () => {
    const { abrir, usuario } = preparar()
    const panel = await abrir()
    await within(panel).findByText('CON-30')
    await usuario.click(within(panel).getByRole('button', { name: 'Acciones pendientes' }))
    expect(within(panel).getByText(personal.mensaje)).toBeTruthy()
    expect(within(panel).queryByText('CON-30')).toBeNull()
    await usuario.click(within(panel).getByRole('button', { name: 'Vencimientos' }))
    expect(within(panel).getByText('CON-30')).toBeTruthy()
    expect(within(panel).queryByText(personal.mensaje)).toBeNull()
    expect(within(panel).getByText('2 asuntos pendientes de atención')).toBeTruthy()
    await usuario.click(within(panel).getByRole('button', { name: 'Todos' }))
    expect(within(panel).getAllByRole('article')).toHaveLength(2)
  })

  it.each<CodigoRol>(['ADMINISTRADOR_ORI', 'GESTOR_ORI', 'REVISOR_ORI', 'SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'])(
    'respeta permisos y consulta notificaciones personales para %s', async (rol) => {
      const autorizado = rol === 'ADMINISTRADOR_ORI' || rol === 'GESTOR_ORI'
      const { abrir, llamadas, usuario } = preparar({ rol, inicio: true })
      const panel = await abrir()
      await within(panel).findByText(personal.mensaje)
      expect(within(panel).queryByRole('button', { name: 'Vencimientos' }) !== null).toBe(autorizado)
      expect(screen.queryByRole('heading', { name: 'Próximos vencimientos' }) !== null).toBe(autorizado)
      expect(llamadas('/api/convenios/alertas-vencimiento') > 0).toBe(autorizado)
      expect(llamadas('/api/notificaciones')).toBeGreaterThan(0)
      await usuario.click(within(panel).getByRole('button', { name: 'Actualizar avisos' }))
      expect(llamadas('/api/convenios/alertas-vencimiento') > 0).toBe(autorizado)
      if (!autorizado) expect(within(panel).queryByText('CON-30')).toBeNull()
    },
  )

  it('marcar leída actualiza lectura, conserva pendiente y no llama a resolver', async () => {
    const { abrir, usuario, cliente, fetchMock } = preparar({ alertas: [] })
    const panel = await abrir()
    await usuario.click(await within(panel).findByRole('button', { name: 'Marcar como leída' }))
    await within(panel).findByText('Leída')
    expect(within(panel).getByText('1 asunto pendiente de atención')).toBeTruthy()
    expect(within(panel).queryByText('Atendida')).toBeNull()
    expect(cliente.getQueryData<Notificacion[]>(CLAVE_NOTIFICACIONES)?.[0]).toMatchObject({ leida: true, resuelta: false })
    expect(fetchMock.mock.calls.map(([url]) => url).filter((url) => url.includes('resolver'))).toEqual([])
  })

  it('refresca ambas fuentes al abrir, reabrir y consultar manualmente', async () => {
    const { abrir, usuario, datos, llamadas } = preparar()
    await screen.findByRole('button', { name: /2 asuntos pendientes/ })
    const antes = llamadas('/api/convenios/alertas-vencimiento')
    datos.alertas = [alerta(60)]
    let panel = await abrir()
    await within(panel).findByText('CON-60')
    expect(llamadas('/api/convenios/alertas-vencimiento')).toBeGreaterThan(antes)
    await usuario.click(within(panel).getByRole('button', { name: 'Cerrar centro de notificaciones' }))
    datos.alertas = [] // El servidor excluye un convenio renovado o cuya fecha cambió.
    datos.notificaciones = []
    panel = await abrir()
    await within(panel).findByText('No tienes notificaciones pendientes')
    datos.alertas = [alerta(120)]
    await usuario.click(within(panel).getByRole('button', { name: 'Actualizar avisos' }))
    await within(panel).findByText('CON-120')
    expect(llamadas('/api/notificaciones')).toBeGreaterThanOrEqual(4)
  })

  it('recupera datos del servidor al regresar a la aplicación', async () => {
    const { abrir, datos } = preparar()
    const panel = await abrir()
    await within(panel).findByText('CON-30')
    act(() => focusManager.setFocused(false))
    datos.alertas = [alerta(90)]
    act(() => focusManager.setFocused(true))
    await within(panel).findByText('CON-90')
    expect(within(panel).queryByText('CON-30')).toBeNull()
  })

  it('el evento WebSocket existente recupera creación y resolución sin duplicados', async () => {
    const { abrir, datos } = preparar({ alertas: [] })
    const panel = await abrir()
    await within(panel).findByText(personal.mensaje)
    await waitFor(() => expect(SocketPrueba.instancias).toHaveLength(1))
    const socket = SocketPrueba.instancias[0]
    expect(socket.url).toContain('/api/notificaciones/ws?ticket=ticket-personal')
    datos.notificaciones = [{ ...personal, resuelta: true }, { ...personal, id: 40, mensaje: 'Nueva tarea' }]
    act(() => socket.onmessage?.())
    await within(panel).findByText('Nueva tarea')
    expect(within(panel).getByText('Atendida')).toBeTruthy()
    expect(within(panel).getByText('1 asunto pendiente de atención')).toBeTruthy()
    act(() => socket.onmessage?.())
    await waitFor(() => expect(within(panel).getAllByRole('article')).toHaveLength(2))
    datos.notificaciones = []
    act(() => socket.onopen?.()) // También recupera eventos perdidos al reconectar.
    await within(panel).findByText('No tienes notificaciones pendientes')
  })

  it.each([
    ['SOLICITUD_DEVUELTA', 'Detalle de solicitud'],
    ['REVISION_JURIDICA_PENDIENTE', 'Detalle de convenio'],
    ['DEVOLUCION_REVISION', 'Detalle de convenio'],
    ['REVISION_CONTRAPARTE_PENDIENTE', 'Revisiones propias'],
  ] as const)('navega desde %s y cierra el panel', async (tipo, destino) => {
    const { abrir, usuario } = preparar({ notificaciones: [{ ...personal, tipo, leida: true }] })
    const panel = await abrir()
    await usuario.click(await within(panel).findByRole('link', { name: 'Ver' }))
    await screen.findByRole('heading', { name: destino })
    expect(screen.queryByRole('region', { name: 'Centro de notificaciones' })).toBeNull()
  })

  it('dirige cada vencimiento a su gestión de renovación', async () => {
    const { abrir, usuario } = preparar()
    const panel = await abrir()
    const enlace = await within(panel).findByRole('link', { name: 'Gestionar renovación' })
    expect(enlace.getAttribute('href')).toBe('/renovaciones?estado=PENDIENTE_DE_DECISION&convenio_id=30')
    await usuario.click(enlace)
    await screen.findByRole('heading', { name: 'Gestión de renovaciones' })
  })

  it('cierra el panel al pulsar fuera de él', async () => {
    const { abrir, usuario } = preparar()
    await abrir()
    await usuario.click(screen.getByRole('heading', { name: 'Inicio' }))
    expect(screen.queryByRole('region', { name: 'Centro de notificaciones' })).toBeNull()
  })

  it('permite abrir, filtrar y cerrar con teclado, y devuelve el foco', async () => {
    const { usuario } = preparar()
    const campana = await screen.findByRole('button', { name: /^Centro de notificaciones/ })
    campana.focus()
    await usuario.keyboard('{Enter}')
    const panel = screen.getByRole('region', { name: 'Centro de notificaciones' })
    await usuario.tab()
    expect(document.activeElement).toBe(within(panel).getByRole('button', { name: /Cerrar centro/ }))
    await usuario.tab()
    expect(document.activeElement).toBe(within(panel).getByRole('button', { name: 'Todos' }))
    await usuario.tab()
    await usuario.keyboard(' ')
    expect(within(panel).getByRole('button', { name: 'Acciones pendientes' }).getAttribute('aria-pressed')).toBe('true')
    await usuario.keyboard('{Escape}')
    expect(document.activeElement).toBe(campana)
    expect(campana.getAttribute('aria-expanded')).toBe('false')
  })
})

describe('Adaptadores, rangos y estados por fuente', () => {
  function renderFuentes(fuentes: FuenteAvisos[]) {
    render(<QueryClientProvider client={clienteNuevo()}><MemoryRouter>
      <CentroNotificaciones fuentes={fuentes} />
    </MemoryRouter></QueryClientProvider>)
    return userEvent.setup()
  }

  it.each([
    [0, 'Urgente'], [30, 'Urgente'], [31, 'Prioritario'], [60, 'Prioritario'],
    [61, 'Atención'], [90, 'Atención'], [91, 'Seguimiento'], [120, 'Seguimiento'],
  ] as const)('representa %i días como %s sin lectura ni creación artificiales', (dias, prioridad) => {
    const avisos = adaptarVencimientos([alerta(dias)])
    renderFuentes([{ categoria: 'vencimientos', avisos, cargando: false, error: false }])
    expect(screen.getByText(prioridad)).toBeTruthy()
    expect(screen.getByText(new RegExp(`${dias} días restantes`))).toBeTruthy()
    expect(avisos[0].lectura).toBeUndefined()
    expect(avisos[0].fecha).toEqual({ valor: '2026-11-13', etiqueta: 'Vence', formato: 'fecha' })
    expect(screen.getByRole('time').getAttribute('datetime')).toBe('2026-11-13')
    expect(screen.queryByRole('button', { name: 'Marcar como leída' })).toBeNull()
  })

  it('excluye vencidos y mayores a 120; separa IDs coincidentes de ambas fuentes', () => {
    const avisos = adaptarVencimientos([alerta(-1), alerta(121), alerta(120), alerta(120)])
    expect(avisos).toHaveLength(1)
    expect(contarAsuntosPendientes([...avisos, adaptarNotificacion({ ...personal, id: 120 })])).toBe(2)
  })

  it('muestra un vacío único en Todos y el correspondiente en cada filtro', async () => {
    const usuario = renderFuentes([
      { categoria: 'acciones', avisos: [], cargando: false, error: false },
      { categoria: 'vencimientos', avisos: [], cargando: false, error: false },
    ])
    expect(screen.getAllByText('No tienes notificaciones pendientes')).toHaveLength(1)
    await usuario.click(screen.getByRole('button', { name: 'Acciones pendientes' }))
    expect(screen.getByText('No tienes acciones pendientes')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Vencimientos' }))
    expect(screen.getByText('No tienes vencimientos pendientes')).toBeTruthy()
  })

  it('un error parcial no oculta la otra fuente ni simula un vacío', async () => {
    const usuario = renderFuentes([
      { categoria: 'acciones', avisos: [adaptarNotificacion(personal)], cargando: false, error: false },
      { categoria: 'vencimientos', avisos: [], cargando: false, error: true },
    ])
    expect(screen.getByText(personal.mensaje)).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('vencimiento')
    expect(screen.queryByText('No tienes notificaciones pendientes')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Acciones pendientes' }))
    expect(screen.queryByRole('alert')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Vencimientos' }))
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.queryByText('No tienes vencimientos pendientes')).toBeNull()
  })

  it('la carga parcial conserva los avisos ya disponibles y no muestra vacío', () => {
    renderFuentes([
      { categoria: 'acciones', avisos: [], cargando: true, error: false },
      { categoria: 'vencimientos', avisos: adaptarVencimientos([alerta(30)]), cargando: false, error: false },
    ])
    expect(screen.getByText('Consultando notificaciones…')).toBeTruthy()
    expect(screen.getByText('CON-30')).toBeTruthy()
    expect(screen.queryByText('No tienes notificaciones pendientes')).toBeNull()
  })

  it('un fallo de lectura se anuncia y permite reintentar sin resolver', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ detail: 'Error temporal' }, { status: 503 }))
      .mockResolvedValueOnce(Response.json({ ...personal, leida: true }))
    vi.stubGlobal('fetch', fetchMock)
    const usuario = renderFuentes([{
      categoria: 'acciones', avisos: [adaptarNotificacion(personal)], cargando: false, error: false,
    }])
    await usuario.click(screen.getByRole('button', { name: 'Marcar como leída' }))
    expect((await screen.findByRole('alert')).textContent).toContain('No fue posible marcar')
    await usuario.click(screen.getByRole('button', { name: 'Marcar como leída' }))
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.getByText('1 asunto pendiente de atención')).toBeTruthy()
  })

  it('identifica convenios sin código y conserva el objeto y el día singular', () => {
    const avisos = adaptarVencimientos([{ ...alerta(1), codigo: null, objeto: 'Convenio sin código' }])
    expect(avisos[0].entidad.identificacion).toBe('Convenio sin código')
    expect(avisos[0].descripcion).toBe('Convenio sin código · 1 día restante')
    expect(adaptarVencimientos([{ ...alerta(0), codigo: null, objeto: null }])[0].entidad.identificacion)
      .toBe('Convenio #0')
  })
})

describe('Resumen de vencimientos en Inicio', () => {
  it.each([
    { cargando: true, error: false, mensaje: 'Consultando vencimientos…' },
    { cargando: false, error: true, mensaje: 'No fue posible consultar los avisos de vencimiento.' },
    { cargando: false, error: false, mensaje: 'No tienes vencimientos pendientes' },
  ])('muestra carga, error o vacío: $mensaje', ({ mensaje, ...estado }) => {
    render(<MemoryRouter><AlertasVencimiento alertas={[]} {...estado} /></MemoryRouter>)
    expect(screen.getByText(mensaje)).toBeTruthy()
    expect(screen.queryByRole('list')).toBeNull()
    if (estado.error || estado.cargando) expect(screen.queryByText('No tienes vencimientos pendientes')).toBeNull()
  })

  it('reutiliza la caché, limita el resumen a tres e incluye el total y renovación', async () => {
    const { cliente } = preparar({ inicio: true, alertas: [alerta(30), alerta(60), alerta(90), alerta(120)] })
    const resumen = await screen.findByRole('region', { name: 'Próximos vencimientos' })
    await within(resumen).findByText('4 convenios próximos a vencer')
    expect(within(resumen).getAllByRole('listitem')).toHaveLength(3)
    expect(within(resumen).getAllByRole('link', { name: 'Gestionar renovación' })).toHaveLength(3)
    expect(within(resumen).getByRole('link', { name: 'Ver gestión de renovaciones' }).getAttribute('href'))
      .toBe('/renovaciones?estado=PENDIENTE_DE_DECISION')
    act(() => cliente.setQueryData(CLAVE_ALERTAS_VENCIMIENTO, []))
    await within(resumen).findByText('No tienes vencimientos pendientes')
    expect(within(resumen).queryByRole('list')).toBeNull()
  })
})

describe('Refresco dinámico HU-30', () => {
  it('vuelve a consultar al avanzar el tiempo y recibe los días calculados por el servidor', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json([alerta(31)]))
      .mockResolvedValueOnce(Response.json([alerta(30)]))
    vi.stubGlobal('fetch', fetchMock)
    const cliente = clienteNuevo()
    const { result } = renderHook(() => useAlertasVencimiento(true), {
      wrapper: ({ children }) => <QueryClientProvider client={cliente}>{children}</QueryClientProvider>,
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(result.current.data?.[0].dias_restantes).toBe(31)
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
    expect(result.current.data?.[0].dias_restantes).toBe(30)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('una fuente deshabilitada no consulta aunque avance el tiempo', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const cliente = clienteNuevo()
    renderHook(() => useAlertasVencimiento(false), {
      wrapper: ({ children }) => <QueryClientProvider client={cliente}>{children}</QueryClientProvider>,
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000) })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
