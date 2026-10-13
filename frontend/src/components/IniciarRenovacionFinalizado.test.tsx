import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type CodigoRol, type Sesion } from '../auth/sesion'
import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { type Convenio } from '../pages/epica02'
import { IniciarRenovacionFinalizado } from './IniciarRenovacionFinalizado'

const convenio: Convenio = {
  id: 41, codigo: 'CON-FINALIZADO', solicitud_id: 1, aliado_id: null, aliado: null,
  tipo_convenio_id: null, etapa_actual_id: null, plantilla_origen_id: null,
  version_actual: 3, estado: 'FINALIZADO', objeto: 'Movilidad académica', alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null,
  fecha_inicio: '2025-01-01', fecha_vencimiento: '2026-10-07', fecha_firma: '2025-01-01',
  duracion_meses: 24, porcentaje_avance: 100, convenio_origen_id: null, numero_renovacion: null,
  creado_por_id: 1, creado_por: { id: 1, nombre_completo: 'Gestor', correo: 'gestor@example.com' },
  creado_en: '2025-01-01T12:00:00Z', actualizado_en: '2026-10-08T05:00:00Z',
}

beforeAll(() => {
  // jsdom no implementa las operaciones nativas de <dialog>.
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function NuevaElaboracion() {
  return <h1>Nueva elaboración #{useParams().convenioId}</h1>
}

function PaginaPrueba({ datos, detalle }: { datos: Convenio; detalle: boolean }) {
  if (useParams().convenioId !== '41') return <NuevaElaboracion />
  return detalle ? <ConvenioDetallePage /> : <IniciarRenovacionFinalizado convenio={datos} />
}

function preparar({ rol = 'GESTOR_ORI', datos = convenio, detalle = false }: {
  rol?: CodigoRol; datos?: Convenio; detalle?: boolean
} = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const autorizado = rol === 'GESTOR_ORI' || rol === 'ADMINISTRADOR_ORI'
  const sesion: Sesion = {
    id: 1, correo: 'usuario@example.com', nombre_completo: 'Usuario', activo: true,
    tipo_usuario: rol === 'SOLICITANTE_EXTERNO' ? 'EXTERNO' : 'INTERNO',
    rol: { codigo: rol, nombre: rol }, permisos: autorizado ? ['convenios.gestionar_renovaciones'] : [],
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  cliente.setQueryData(['convenio', datos.id], datos)
  const notify = vi.fn()
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ convenio_renovacion_id: 42 }), { status: 201 }))
  vi.stubGlobal('fetch', fetch)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <MemoryRouter initialEntries={['/convenios/41']}>
          <Routes>
            <Route path="/convenios/:convenioId" element={<PaginaPrueba datos={datos} detalle={detalle} />} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { cliente, notify, fetch, usuario: userEvent.setup() }
}

describe('renovación tardía desde el detalle', () => {
  it.each<CodigoRol>(['GESTOR_ORI', 'ADMINISTRADOR_ORI'])('ofrece la acción a %s', (rol) => {
    preparar({ rol, detalle: true })
    expect(screen.getByRole('button', { name: 'Iniciar renovación' })).toBeTruthy()
  })

  it.each<CodigoRol>(['REVISOR_ORI', 'SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'])('oculta la acción a %s', (rol) => {
    const { fetch } = preparar({ rol })
    expect(screen.queryByRole('button', { name: 'Iniciar renovación' })).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })

  it.each<Convenio['estado']>(['VIGENTE', 'POR_VENCER', 'VENCIDO', 'RENOVADO', 'CANCELADO', 'EN_TRAMITE'])('no añade acción tardía en %s', (estado) => {
    preparar({ datos: { ...convenio, estado } })
    expect(screen.queryByRole('button', { name: 'Iniciar renovación' })).toBeNull()
  })

  it.each([{ fecha_vencimiento: null }, { version_actual: 0 }])('deshabilita con antecedente incompleto: %s', (cambios) => {
    preparar({ datos: { ...convenio, ...cambios } })
    expect((screen.getByRole('button', { name: 'Iniciar renovación' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('cancelar la confirmación no ejecuta POST', async () => {
    const { usuario, fetch } = preparar()
    await usuario.click(screen.getByRole('button', { name: 'Iniciar renovación' }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar' }))
    expect(fetch).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('confirma un único POST existente y navega a la elaboración hija', async () => {
    const { usuario, fetch, notify } = preparar()
    let resolver!: (respuesta: Response) => void
    fetch.mockReturnValue(new Promise<Response>((resolve) => { resolver = resolve }))
    await usuario.click(screen.getByRole('button', { name: 'Iniciar renovación' }))
    const boton = within(screen.getByRole('dialog')).getByRole('button', { name: 'Iniciar renovación' })
    fireEvent.click(boton)
    fireEvent.click(boton)
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    expect(fetch).toHaveBeenCalledWith('/api/convenios/41/renovaciones', expect.objectContaining({ method: 'POST', credentials: 'include' }))
    expect((screen.getByRole('button', { name: 'Registrando…' }) as HTMLButtonElement).disabled).toBe(true)
    resolver(new Response(JSON.stringify({ convenio_renovacion_id: 42 }), { status: 201 }))
    expect(await screen.findByRole('heading', { name: 'Nueva elaboración #42' })).toBeTruthy()
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }))
  })

  it.each([
    [401, 'Tu sesión ha expirado. Inicia sesión nuevamente.'],
    [403, 'No tienes permiso para gestionar renovaciones.'],
    [409, 'Ya existe una renovación activa'],
    [500, 'No se pudo completar la acción. Comprueba tu conexión y vuelve a intentarlo.'],
  ])('trata error %s sin navegar ni reintentar automáticamente', async (status, mensaje) => {
    const { usuario, fetch, notify } = preparar()
    fetch.mockResolvedValue(new Response(JSON.stringify({ detail: status === 409 ? mensaje : 'Error' }), { status: Number(status) }))
    await usuario.click(screen.getByRole('button', { name: 'Iniciar renovación' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Iniciar renovación' }))
    await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'error', message: mensaje }))
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('heading', { name: 'Nueva elaboración #42' })).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
