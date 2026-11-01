import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Sesion, useSesion } from '../auth/sesion'
import { HomePage } from '../pages/HomePage'
import { type EstadoGuia, type GuiaUsuario } from '../pages/estadoGuias'
import { HeaderNav } from './HeaderNav'
import { OnboardingSolicitantes } from './OnboardingSolicitantes'
import { TourProvider } from './TourProvider'

const solicitante: Sesion = {
  id: 9, correo: 'solicitante@example.test', nombre_completo: 'Persona de prueba',
  activo: true, tipo_usuario: 'EXTERNO', rol: { codigo: 'SOLICITANTE_EXTERNO', nombre: 'Solicitante externo' },
  permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
}
const CLAVE = ['guias', solicitante.id, 'ONBOARDING_INICIAL']

function Ubicacion() {
  const ubicacion = useLocation()
  return <><span data-testid="ruta">{ubicacion.pathname}{ubicacion.search}{ubicacion.hash}</span><span data-testid="estado">{JSON.stringify(ubicacion.state)}</span></>
}

function Marco({ inicioDiferido = false }: { inicioDiferido?: boolean }) {
  const { sesion } = useSesion()
  const [listo, setListo] = useState(!inicioDiferido)
  return <>
    <Ubicacion />
    <HeaderNav enlaces={[{ to: '/', label: 'Inicio' }, { to: '/solicitudes', label: 'Mis solicitudes' }]} />
    {sesion && <OnboardingSolicitantes key={`${sesion.id}:${sesion.rol.codigo}`} sesion={sesion} />}
    <button data-tour="centro-notificaciones">Notificaciones</button>
    <button onClick={() => setListo(true)}>Preparar Inicio</button>
    <Routes>
      <Route path="/" element={listo ? <HomePage /> : <p>Cargando Inicio</p>} />
      <Route path="*" element={<h1>Módulo autorizado</h1>} />
    </Routes>
  </>
}

function montar(estado: EstadoGuia, ruta = '/', opciones: {
  sesion?: Sesion; erroresGet?: number[]; erroresPut?: number[]; inicioDiferido?: boolean
} = {}) {
  let estadoServidor = estado
  const erroresGet = [...(opciones.erroresGet ?? [])]
  const erroresPut = [...(opciones.erroresPut ?? [])]
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url !== '/api/guias/ONBOARDING_INICIAL') return Response.json([])
    const status = (init?.method === 'PUT' ? erroresPut : erroresGet).shift() ?? 200
    if (status !== 200) return Response.json({ detail: 'Detalle técnico no mostrado' }, { status })
    if (init?.method === 'PUT' && estadoServidor !== 'COMPLETADO') estadoServidor = JSON.parse(String(init.body)).estado
    return Response.json({ guia: 'ONBOARDING_INICIAL', estado: estadoServidor, version: 1, actualizado_en: null })
  })
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, opciones.sesion ?? solicitante)
  const vista = render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[{ pathname: ruta.split('?')[0], search: ruta.includes('?') ? `?${ruta.split('?')[1]}` : '', state: {
        volver: { to: '/solicitudes?estado=BORRADOR', texto: 'Volver a mis solicitudes' }, noPropagar: true,
      } }]}>
        <TourProvider><Marco inicioDiferido={opciones.inicioDiferido} /></TourProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { cliente, fetch, usuario: userEvent.setup(), ...vista }
}

const titulo = () => document.querySelector('.driver-popover-title')?.textContent
const put = (fetch: ReturnType<typeof vi.fn>) => fetch.mock.calls.filter(([, init]) => init?.method === 'PUT')

async function completar() {
  while (!screen.queryByRole('button', { name: 'Finalizar' })) {
    const anterior = titulo()
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(titulo()).not.toBe(anterior))
  }
  fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }))
}

beforeEach(() => {
  // Se simula geometría para probar decisiones del motor, no responsive real.
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
    return { length: this.hasAttribute('data-tour') && !this.closest('[hidden]') ? 1 : 0 } as DOMRectList
  })
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('HU-38: inicio completo y persistencia con driver.js real', () => {
  it.each(['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'] as const)('activa automáticamente el pendiente para %s', async (rol) => {
    montar('PENDIENTE', '/', { sesion: { ...solicitante, rol: { codigo: rol, nombre: rol } } })
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    expect(document.querySelectorAll('.driver-popover')).toHaveLength(1)
  })

  it.each(['/', '/solicitudes?estado=DEVUELTA&pagina=2', '/revisiones-contraparte?pagina=3'])('Ayuda desde %s navega a Inicio y conserva el origen', async (ruta) => {
    const { usuario, fetch } = montar('COMPLETADO', ruta)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', false))
    await usuario.click(screen.getByRole('button', { name: 'Ayuda' }))
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    expect(screen.getByTestId('ruta').textContent).toBe('/')
    await completar()
    expect(put(fetch)).toHaveLength(0)
    if (ruta !== '/') {
      await usuario.click(screen.getByRole('link', { name: 'Volver a la pantalla anterior' }))
      expect(screen.getByTestId('ruta').textContent).toBe(ruta)
      expect(JSON.parse(screen.getByTestId('estado').textContent ?? '{}')).toEqual({ volver: {
        to: '/solicitudes?estado=BORRADOR', texto: 'Volver a mis solicitudes',
      } })
    }
  })

  it('espera los elementos de Inicio antes de activar y evita apertura duplicada', async () => {
    const { usuario, fetch } = montar('PENDIENTE', '/solicitudes', { inicioDiferido: true })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', false))
    await usuario.dblClick(screen.getByRole('button', { name: 'Ayuda' }))
    expect(screen.getByTestId('ruta').textContent).toBe('/')
    expect(document.querySelector('.driver-popover')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Preparar Inicio' }))
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    expect(document.querySelectorAll('.driver-popover')).toHaveLength(1)
    expect(put(fetch)).toHaveLength(0)
  })

  it('no convierte una ruta de origen anómala en un enlace de retorno externo', async () => {
    const { usuario } = montar('COMPLETADO', '//externo.example')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', false))
    await usuario.click(screen.getByRole('button', { name: 'Ayuda' }))
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    fireEvent.click(screen.getByRole('button', { name: 'Omitir recorrido' }))
    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())
    expect(screen.queryByRole('link', { name: 'Volver a la pantalla anterior' })).toBeNull()
    expect(screen.getByTestId('ruta').textContent).toBe('/')
  })

  it.each(['PENDIENTE', 'OMITIDO'] as const)('Finalizar transforma %s en COMPLETADO', async (estado) => {
    const { usuario, fetch, cliente } = montar(estado)
    if (estado === 'OMITIDO') {
      await waitFor(() => expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', false))
      expect(document.querySelector('.driver-popover')).toBeNull()
      await usuario.click(screen.getByRole('button', { name: 'Ayuda' }))
    }
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    await completar()
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(CLAVE)?.estado).toBe('COMPLETADO'))
    expect(put(fetch)).toHaveLength(1)
  })

  it.each(['X', 'Omitir', 'Escape'] as const)('%s omite PENDIENTE y conserva COMPLETADO al reproducir', async (control) => {
    for (const estado of ['PENDIENTE', 'COMPLETADO'] as const) {
      const { usuario, fetch, cliente, unmount } = montar(estado)
      if (estado === 'COMPLETADO') {
        await waitFor(() => expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', false))
        await usuario.click(screen.getByRole('button', { name: 'Ayuda' }))
      }
      await waitFor(() => expect(titulo()).toContain('Bienvenido'))
      if (control === 'Escape') await usuario.keyboard('{Escape}')
      else fireEvent.click(screen.getByRole('button', { name: control === 'X' ? 'Omitir recorrido' : 'Omitir' }))
      await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())
      await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(CLAVE)?.estado).toBe(estado === 'PENDIENTE' ? 'OMITIDO' : 'COMPLETADO'))
      expect(put(fetch)).toHaveLength(estado === 'PENDIENTE' ? 1 : 0)
      unmount()
    }
  })
})

describe('HU-38: errores y ciclo de sesión', () => {
  it('limita la espera de Inicio y permite reintentar sin un ciclo de consultas', async () => {
    vi.useFakeTimers()
    const { fetch } = montar('PENDIENTE', '/', { inicioDiferido: true })
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(screen.getByRole('status').textContent).toContain('No se pudo preparar')
    expect(document.querySelector('.driver-popover')).toBeNull()
    expect(fetch.mock.calls.filter(([url]) => url.includes('/guias/'))).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar recorrido' }))
    fireEvent.click(screen.getByRole('button', { name: 'Preparar Inicio' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(titulo()).toContain('Bienvenido')
  })

  it('un GET fallido no supone PENDIENTE ni bloquea la plataforma y permite reintento explícito', async () => {
    const { usuario, fetch } = montar('PENDIENTE', '/', { erroresGet: [500, 200] })
    expect(await screen.findByRole('status')).toHaveProperty('textContent', expect.stringContaining('No se pudo consultar'))
    expect(document.querySelector('.driver-popover')).toBeNull()
    expect(fetch.mock.calls.filter(([url]) => url.includes('/guias/'))).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveProperty('disabled', true)
    await usuario.click(screen.getByRole('button', { name: 'Preparar Inicio' }))
    await usuario.click(screen.getByRole('button', { name: 'Reintentar consulta' }))
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    expect(fetch.mock.calls.filter(([url]) => url.includes('/guias/'))).toHaveLength(2)
  })

  it('un PUT fallido conserva caché, informa el fallo y reintenta sin abrir otro recorrido', async () => {
    const { usuario, fetch, cliente } = montar('PENDIENTE', '/', { erroresPut: [503, 200] })
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    await completar()
    expect(await screen.findByRole('status')).toHaveProperty('textContent', expect.stringContaining('No se pudo guardar'))
    expect(cliente.getQueryData<GuiaUsuario>(CLAVE)?.estado).toBe('PENDIENTE')
    expect(put(fetch)).toHaveLength(1)
    await usuario.dblClick(screen.getByRole('button', { name: 'Reintentar guardado' }))
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(CLAVE)?.estado).toBe('COMPLETADO'))
    expect(put(fetch)).toHaveLength(2)
    expect(document.querySelector('.driver-popover')).toBeNull()
  })

  it('cerrar sesión y cambiar de cuenta cierran silenciosamente el recorrido anterior', async () => {
    const { cliente, fetch } = montar('PENDIENTE')
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    act(() => { cliente.setQueryData(CLAVE_SESION, null) })
    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())
    expect(put(fetch)).toHaveLength(0)
    act(() => { cliente.setQueryData(CLAVE_SESION, { ...solicitante, id: 10 }) })
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    expect(document.querySelectorAll('.driver-popover')).toHaveLength(1)
    expect(cliente.getQueryData<GuiaUsuario>(['guias', 10, 'ONBOARDING_INICIAL'])?.estado).toBe('PENDIENTE')
  })

  it('una escritura tardía tras cerrar sesión no reconstruye la caché de la cuenta anterior', async () => {
    const { cliente, fetch } = montar('PENDIENTE')
    await waitFor(() => expect(titulo()).toContain('Bienvenido'))
    const responder = fetch.getMockImplementation()!
    let liberar: () => void = () => undefined
    const espera = new Promise<void>((resolve) => { liberar = resolve })
    fetch.mockImplementation(async (url, init) => {
      if (init?.method === 'PUT') await espera
      return responder(url, init)
    })
    await completar()
    await waitFor(() => expect(put(fetch)).toHaveLength(1))
    act(() => {
      cliente.setQueryData(CLAVE_SESION, null)
      cliente.removeQueries({ queryKey: CLAVE })
    })
    await act(async () => {
      liberar()
      await espera
    })
    await waitFor(() => expect(cliente.getMutationCache().getAll()[0]?.state.status).toBe('success'))
    expect(cliente.getQueryData(CLAVE)).toBeUndefined()
    expect(document.querySelector('.driver-popover')).toBeNull()
  })

  it('no consulta ni ofrece onboarding a un rol ORI', async () => {
    const { fetch } = montar('PENDIENTE', '/', { sesion: { ...solicitante, rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor' } } })
    expect(screen.queryByRole('button', { name: 'Ayuda' })).toBeNull()
    expect(fetch.mock.calls.some(([url]) => url.includes('/guias/'))).toBe(false)
  })
})
