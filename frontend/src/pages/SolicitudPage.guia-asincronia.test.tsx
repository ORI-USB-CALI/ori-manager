import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationProvider } from '../app/notifications/Notifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { TourProvider } from '../components/TourProvider'
import { claveGuia, type EstadoGuia, type GuiaUsuario } from './estadoGuias'
import { DESTINOS_SECCIONES_SOLICITUD, PASOS_SECCIONES_SOLICITUD } from './guiaRadicacion'
import { SolicitudPage } from './SolicitudPage'

const sesion: Sesion = {
  id: 1, correo: 'persona@example.test', nombre_completo: 'Persona', activo: true, tipo_usuario: 'INTERNO',
  rol: { codigo: 'SOLICITANTE_INTERNO', nombre: 'Solicitante interno' },
  permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
}
const estadoGuia = (estado: EstadoGuia): GuiaUsuario => ({ guia: 'GUIA_RADICACION', estado, version: 1, actualizado_en: null })
interface Peticion { usuarioId: number; responder: (estado: EstadoGuia, status?: number) => void }

function montar({ externo = false, retenerPut = false, rolOri = false, estadoSolicitud }: {
  externo?: boolean; retenerPut?: boolean; rolOri?: boolean; estadoSolicitud?: 'BORRADOR' | 'DEVUELTA' | 'RADICADA'
} = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const persona = externo ? { ...sesion, tipo_usuario: 'EXTERNO' as const,
    rol: { codigo: 'SOLICITANTE_EXTERNO' as const, nombre: 'Solicitante externo' } } : sesion
  cliente.setQueryData(CLAVE_SESION, rolOri ? { ...persona, rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor' } } : persona)
  const lecturas: Peticion[] = []
  const escrituras: Peticion[] = []
  const perfil = { tipo_usuario: externo ? 'EXTERNO' : 'INTERNO', tipo_unidad: externo ? null : 'FACULTAD',
    nombre: 'Persona', correo: persona.correo, identificacion: externo ? 'ABC-123' : null,
    entidad: externo ? 'Entidad' : null, cargo: externo ? null : 'Docente', unidad: externo ? null : 'Facultad', programa: null }
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const usuarioId = cliente.getQueryData<Sesion>(CLAVE_SESION)?.id ?? 0
    if (url.endsWith('/solicitudes/catalogos')) return Response.json({ solicitante: perfil,
      tipos_convenio: [], tipos_documento: [{ codigo: 'CAMARA_COMERCIO', nombre: 'Cámara de Comercio', es_representacion_legal: true }],
      requiere_documento_representacion: true })
    if (url.endsWith('/guias/GUIA_RADICACION')) {
      if (init?.method === 'PUT' && !retenerPut) return Response.json(estadoGuia(JSON.parse(String(init.body)).estado))
      return new Promise<Response>((resolve) => {
        const peticion = { usuarioId, responder: (estado: EstadoGuia, status = 200) =>
          resolve(status === 200 ? Response.json(estadoGuia(estado)) : Response.json({ detail: 'Error técnico reservado' }, { status })) }
        if (init?.method === 'PUT') escrituras.push(peticion)
        else lecturas.push(peticion)
      })
    }
    if (url.endsWith('/solicitudes/9')) return Response.json({ id: 9, consecutivo: 'SOL-9', estado: estadoSolicitud,
      tipo_solicitante: perfil.tipo_usuario, solicitante_nombre: perfil.nombre, solicitante_correo: perfil.correo,
      solicitante_documento: perfil.identificacion, solicitante_entidad: perfil.entidad, solicitante_unidad: perfil.unidad,
      solicitante_programa: null, solicitante_cargo: perfil.cargo, documentos: [],
      observaciones_devolucion: estadoSolicitud === 'DEVUELTA' ? 'Corregir el objeto' : null })
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  const vista = render(<QueryClientProvider client={cliente}><NotificationProvider><TourProvider>
    <MemoryRouter initialEntries={[estadoSolicitud ? '/solicitudes/9' : '/solicitudes/nueva']}><Routes>
      <Route path="/solicitudes/nueva" element={<SolicitudPage />} /><Route path="/solicitudes/:solicitudId" element={<SolicitudPage />} />
    </Routes></MemoryRouter>
  </TourProvider></NotificationProvider></QueryClientProvider>)
  const puts = () => fetch.mock.calls.filter(([url, init]) => url.includes('/guias/') && init?.method === 'PUT')
  return { cliente, lecturas, escrituras, fetch, puts, usuario: userEvent.setup(), ...vista }
}

const titulo = () => document.querySelector('.driver-popover-title')?.textContent
async function abrir() {
  await screen.findByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' })
  fireEvent.click(screen.getByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' }))
  await waitFor(() => expect(titulo()).toBe('1. Información del solicitante'))
}
async function completar() {
  for (let paso = 0; paso < 20 && !screen.queryByRole('button', { name: 'Finalizar' }); paso++) {
    const anterior = titulo()
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(titulo()).not.toBe(anterior))
  }
  fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }))
}
beforeEach(() => {
  // Prueba de decisiones y eventos del motor; no sustituye layout en navegador.
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
    return { length: (this.hasAttribute('data-tour') || this.closest('.driver-popover')) && !this.closest('[hidden]') ? 1 : 0 } as DOMRectList
  })
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('HU-39 H-02/H-03: estado desconocido y respuestas asíncronas', () => {
  it.each(['Omitir', 'X', 'Escape'])('%s antes del GET conserva la intención y sincroniza OMITIDO al recibir PENDIENTE', async (control) => {
    const { lecturas, puts, cliente, usuario } = montar()
    await abrir()
    await waitFor(() => expect(lecturas).toHaveLength(1))
    if (control === 'Escape') await usuario.keyboard('{Escape}')
    else fireEvent.click(screen.getByRole('button', { name: control === 'X' ? 'Omitir recorrido' : 'Omitir' }))
    expect(document.querySelector('.driver-popover')).toBeNull()
    expect(puts()).toHaveLength(0)
    expect(cliente.getQueryData(claveGuia(1, 'GUIA_RADICACION'))).toBeUndefined()
    await act(async () => { lecturas[0].responder('PENDIENTE') })
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(JSON.parse(String(puts()[0][1]?.body))).toEqual({ estado: 'OMITIDO', version: 1 })
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(claveGuia(1, 'GUIA_RADICACION'))?.estado).toBe('OMITIDO'))
  })

  it('un GET tardío COMPLETADO impide escribir una omisión del cierre inmediato', async () => {
    const { lecturas, puts, cliente } = montar()
    await abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Omitir recorrido' }))
    await act(async () => { lecturas[0].responder('COMPLETADO') })
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(claveGuia(1, 'GUIA_RADICACION'))?.estado).toBe('COMPLETADO'))
    expect(puts()).toHaveLength(0)
  })

  it.each(['PENDIENTE', 'OMITIDO'] as const)('Finalizar después del GET tardío %s guarda COMPLETADO', async (estado) => {
    const { lecturas, puts } = montar()
    await abrir()
    await act(async () => { lecturas[0].responder(estado) })
    await completar()
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(JSON.parse(String(puts()[0][1]?.body))).toEqual({ estado: 'COMPLETADO', version: 1 })
  })

  it('Finalizar antes del GET también sincroniza cuando llega la respuesta', async () => {
    const { lecturas, puts } = montar()
    await abrir()
    await completar()
    expect(puts()).toHaveLength(0)
    await act(async () => { lecturas[0].responder('PENDIENTE') })
    await waitFor(() => expect(puts()).toHaveLength(1))
  })

  it('GET fallido deja el estado desconocido, permite trabajar y reintenta sin perder el cierre', async () => {
    const { lecturas, puts, usuario } = montar()
    await abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await act(async () => { lecturas[0].responder('PENDIENTE', 503) })
    expect(await screen.findByText(/No se pudo consultar el estado/)).toBeTruthy()
    expect(puts()).toHaveLength(0)
    expect(lecturas).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Guardar borrador' })).toHaveProperty('disabled', false)
    await usuario.click(screen.getByRole('button', { name: 'Reintentar consulta de la guía' }))
    await waitFor(() => expect(lecturas).toHaveLength(2))
    await act(async () => { lecturas[1].responder('PENDIENTE') })
    await waitFor(() => expect(puts()).toHaveLength(1))
  })

  it('PUT fallido no actualiza caché; el reintento duplica cero solicitudes aunque se pulse dos veces', async () => {
    const { lecturas, escrituras, puts, cliente, usuario } = montar({ retenerPut: true })
    await abrir()
    await act(async () => { lecturas[0].responder('PENDIENTE') })
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(escrituras).toHaveLength(1))
    await act(async () => { escrituras[0].responder('OMITIDO', 503) })
    expect(await screen.findByText(/No se pudo guardar el estado/)).toBeTruthy()
    expect(cliente.getQueryData<GuiaUsuario>(claveGuia(1, 'GUIA_RADICACION'))?.estado).toBe('PENDIENTE')
    await usuario.dblClick(screen.getByRole('button', { name: 'Reintentar guardado de la guía' }))
    await waitFor(() => expect(escrituras).toHaveLength(2))
    await act(async () => { escrituras[1].responder('OMITIDO') })
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(claveGuia(1, 'GUIA_RADICACION'))?.estado).toBe('OMITIDO'))
    expect(puts()).toHaveLength(2)
  })

  it.each(['GET', 'PUT'])('una respuesta %s fuera de orden no rebaja el estado más reciente', async (tardia) => {
    const { lecturas, escrituras, cliente } = montar({ retenerPut: true })
    const clave = claveGuia(1, 'GUIA_RADICACION')
    await abrir()
    await act(async () => { lecturas[0].responder('PENDIENTE') })
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(escrituras).toHaveLength(1))
    let recarga: Promise<void>
    act(() => { recarga = cliente.refetchQueries({ queryKey: clave, exact: true }) })
    await waitFor(() => expect(lecturas).toHaveLength(2))
    if (tardia === 'GET') {
      await act(async () => { escrituras[0].responder('OMITIDO') })
      await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(clave)?.estado).toBe('OMITIDO'))
      await act(async () => { lecturas[1].responder('PENDIENTE'); await recarga! })
      expect(cliente.getQueryData<GuiaUsuario>(clave)?.estado).toBe('OMITIDO')
    } else {
      await act(async () => { lecturas[1].responder('COMPLETADO'); await recarga! })
      await act(async () => { escrituras[0].responder('OMITIDO') })
      await waitFor(() => expect(cliente.getMutationCache().getAll()[0]?.state.status).toBe('success'))
      expect(cliente.getQueryData<GuiaUsuario>(clave)?.estado).toBe('COMPLETADO')
    }
  })

  it('logout durante PUT no reconstruye caché; cambiar de cuenta conserva claves independientes', async () => {
    const { lecturas, escrituras, cliente } = montar({ retenerPut: true })
    await abrir()
    await act(async () => { lecturas[0].responder('PENDIENTE') })
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(escrituras).toHaveLength(1))
    act(() => {
      cliente.setQueryData(CLAVE_SESION, null)
      cliente.removeQueries({ queryKey: claveGuia(1, 'GUIA_RADICACION') })
    })
    await act(async () => { escrituras[0].responder('OMITIDO') })
    await waitFor(() => expect(cliente.getMutationCache().getAll()[0]?.state.status).toBe('success'))
    expect(cliente.getQueryData(claveGuia(1, 'GUIA_RADICACION'))).toBeUndefined()
    act(() => { cliente.setQueryData(CLAVE_SESION, { ...sesion, id: 2 }) })
    await abrir()
    await waitFor(() => expect(lecturas).toHaveLength(2))
    expect(lecturas[1].usuarioId).toBe(2)
    await act(async () => { lecturas[1].responder('COMPLETADO') })
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(claveGuia(2, 'GUIA_RADICACION'))?.estado).toBe('COMPLETADO'))
    expect(escrituras).toHaveLength(1)
  })

  it('un GET de la cuenta anterior no contamina la nueva ni el onboarding', async () => {
    const { lecturas, cliente } = montar()
    cliente.setQueryData(claveGuia(2, 'ONBOARDING_INICIAL'), { ...estadoGuia('OMITIDO'), guia: 'ONBOARDING_INICIAL' })
    await abrir()
    act(() => { cliente.setQueryData(CLAVE_SESION, { ...sesion, id: 2 }) })
    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())
    await abrir()
    await waitFor(() => expect(lecturas).toHaveLength(2))
    await act(async () => { lecturas[1].responder('OMITIDO'); lecturas[0].responder('COMPLETADO') })
    await waitFor(() => expect(cliente.getQueryData<GuiaUsuario>(claveGuia(2, 'GUIA_RADICACION'))?.estado).toBe('OMITIDO'))
    expect(cliente.getQueryData<GuiaUsuario>(claveGuia(2, 'ONBOARDING_INICIAL'))?.estado).toBe('OMITIDO')
    expect(cliente.getQueryData(['guias', 'GUIA_RADICACION'])).toBeUndefined()
  })
})

describe('HU-39 H-04/H-06: guía y formulario real', () => {
  it('conserva el contenido esencial si una sección real está oculta', async () => {
    montar()
    await screen.findByRole('button', { name: /Ayuda: cómo/ })
    const seccion = document.querySelector('[data-tour="solicitud-contraparte"]') as HTMLElement
    seccion.hidden = true
    await abrir()
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(titulo()).toBe('2. Información de la contraparte'))
    expect(screen.getByText('2 de 13')).toBeTruthy()
    expect(seccion.classList.contains('driver-active-element')).toBe(false)
  })

  it('Tab, Shift+Tab y Enter controlan el recorrido sin escribir ni enviar el formulario', async () => {
    const { usuario, fetch } = montar()
    const campo = await screen.findByRole('textbox', { name: 'Observaciones' })
    await usuario.type(campo, 'Información que debe conservarse')
    await abrir()
    const siguiente = screen.getByRole('button', { name: 'Siguiente' })
    siguiente.focus()
    await usuario.keyboard('{Enter}')
    await waitFor(() => expect(titulo()).toBe('2. Información de la contraparte'))
    await usuario.tab()
    expect(document.querySelector('.driver-popover')?.contains(document.activeElement)).toBe(true)
    await usuario.tab({ shift: true })
    expect(document.querySelector('.driver-popover')?.contains(document.activeElement)).toBe(true)
    await usuario.keyboard('{Escape}')
    expect((campo as HTMLTextAreaElement).value).toBe('Información que debe conservarse')
    expect(fetch.mock.calls.some(([, init]) => ['POST', 'PATCH', 'DELETE'].includes(init?.method ?? ''))).toBe(false)
  })

  it.each([false, true])('los pasos corresponden a campos y tipos de control existentes (externo=%s)', async (externo) => {
    montar({ externo })
    await abrir()
    const rol = externo ? 'SOLICITANTE_EXTERNO' : 'SOLICITANTE_INTERNO'
    const pasos = PASOS_SECCIONES_SOLICITUD.filter((paso) => !paso.roles || paso.roles.includes(rol))
    expect(pasos).toHaveLength(8)
    for (const paso of pasos) {
      const seccion = document.querySelector(`[data-tour="${paso.destino}"]`) as HTMLElement
      expect(seccion).toBeTruthy()
      expect(within(seccion).getByRole('heading').textContent).toContain(paso.titulo)
      expect(seccion.querySelectorAll('input, select, textarea').length).toBeGreaterThan(0)
    }
    const solicitante = document.querySelector(`[data-tour="${DESTINOS_SECCIONES_SOLICITUD.solicitante}"]`) as HTMLElement
    const contraparte = document.querySelector(`[data-tour="${DESTINOS_SECCIONES_SOLICITUD.contraparte}"]`) as HTMLElement
    expect(contraparte.querySelector('[name="pais_aliado_propuesto_id"]')?.tagName).toBe('SELECT')
    expect(contraparte.querySelector('[name="ciudad_aliado_propuesto"]')?.tagName).toBe('INPUT')
    expect(contraparte.querySelector('[name="tipo_identificacion_aliado_propuesto"]')?.tagName).toBe('SELECT')
    expect(document.querySelector('[name*="digito"], [name*="verificacion"]')).toBeNull()
    if (externo) {
      expect(solicitante.querySelector('[name="solicitante_tipo_documento"]')?.tagName).toBe('SELECT')
      expect(solicitante.querySelector('[name="solicitante_documento"]')?.tagName).toBe('INPUT')
      expect(solicitante.querySelector('[name="solicitante_unidad"]')).toBeNull()
      expect(pasos[0].descripcion).toContain(within(solicitante).getByText('Empresa / Entidad *').textContent?.replace(' / ', ' o ').replace(' *', '') ?? '')
    } else {
      expect(solicitante.querySelector('[name="solicitante_tipo_documento"]')).toBeNull()
      expect(solicitante.querySelector('[name="solicitante_cargo"]')).toBeTruthy()
      expect(solicitante.querySelector('[name="solicitante_entidad"]')).toBeNull()
    }
    expect(pasos[1].descripcion).toContain('país se elige de la lista')
    expect(pasos[6].descripcion).toContain('10 MB')
    expect(within(document.querySelector('[data-tour="solicitud-documentacion"]') as HTMLElement).getAllByText(/Formatos permitidos: PDF, JPG y PNG/).length).toBeGreaterThan(0)
  })

  it.each(['BORRADOR', 'DEVUELTA', 'RADICADA'] as const)('solo ofrece acciones y guía si la solicitud %s es editable', async (estadoSolicitud) => {
    montar({ estadoSolicitud })
    await screen.findByRole('heading', { name: 'SOL-9' })
    if (estadoSolicitud === 'RADICADA') expect(screen.queryByRole('button', { name: /Ayuda: cómo/ })).toBeNull()
    else {
      expect(screen.getByRole('button', { name: /Ayuda: cómo/ })).toBeTruthy()
      expect(screen.getByRole('button', { name: estadoSolicitud === 'DEVUELTA' ? 'Volver a radicar' : 'Radicar solicitud' })).toBeTruthy()
    }
  })

  it('no ofrece la guía a un rol ORI aunque se altere el permiso en el cliente', async () => {
    montar({ rolOri: true })
    await screen.findByRole('heading', { name: 'Nueva solicitud' })
    expect(screen.queryByRole('button', { name: /Ayuda: cómo/ })).toBeNull()
  })
})
