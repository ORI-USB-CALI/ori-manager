import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { SolicitudPage } from './SolicitudPage'
import { SolicitudRecibidaPage } from './SolicitudRecibidaPage'
import { SolicitudesRecibidasPage } from './SolicitudesRecibidasPage'
import type { CatalogosSolicitud, EstadoSolicitud, SolicitudRecibida } from './solicitudes'

const solicitud: SolicitudRecibida = {
  id: 41, consecutivo: 'SOL-00000041', solicitante_id: 7, tipo_solicitante: 'INTERNO',
  unidad_organizacional_id: null, solicitante_nombre: 'Ana Solicitante',
  solicitante_correo: 'ana@example.com', solicitante_documento: null,
  solicitante_cargo: 'Docente', solicitante_entidad: null, solicitante_unidad: 'Ingeniería',
  solicitante_programa: null, nombre_aliado_propuesto: 'Universidad Contraparte',
  tipo_identificacion_aliado_propuesto: null, identificacion_aliado_propuesto: null,
  tipo_aliado_propuesto: null, correo_aliado_propuesto: null, pais_aliado_propuesto: null,
  ciudad_aliado_propuesto: null, telefono_aliado_propuesto: null,
  direccion_aliado_propuesto: null, sector_economico_aliado_propuesto: null,
  contacto_contraparte_nombre: null, contacto_contraparte_cargo: null,
  contacto_contraparte_telefono: null, contacto_contraparte_correo: null,
  tipo_convenio_id: null, justificacion: null, objeto: 'Cooperación académica',
  actividades_por_parte: null, metas_esperadas: null, implicacion_financiera: null,
  vigencia_estimada: null, requisitos_renovacion: null, supervisor_usb_nombre: null,
  supervisor_usb_cargo: null, supervisor_usb_telefono: null, supervisor_usb_correo: null,
  supervisor_contraparte_nombre: null, supervisor_contraparte_cargo: null,
  supervisor_contraparte_telefono: null, supervisor_contraparte_correo: null,
  observaciones: null, estado: 'RADICADA', fecha_radicacion: '2026-10-13T13:00:00Z',
  fecha_recibido_ori: '2026-10-13T13:00:00Z', motivo_rechazo: null,
  observaciones_devolucion: null, decidida_por_id: null, fecha_decision: null,
  documentos: [], creado_en: '2026-10-13T12:00:00Z', actualizado_en: '2026-10-13T13:00:00Z',
  convenio_id: null, convenio_estado: null, convenio_etapa: null,
  tipo_convenio_nombre: null, decidida_por_nombre: null,
}

const gestor: Sesion = {
  id: 1, correo: 'gestor@example.com', nombre_completo: 'Gestor ORI', activo: true,
  tipo_usuario: 'INTERNO', rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' },
  permisos: ['solicitudes.ver_recibidas', 'solicitudes.gestionar_recibidas'],
}

const solicitante: Sesion = {
  ...gestor, id: solicitud.solicitante_id, nombre_completo: 'Ana Solicitante',
  rol: { codigo: 'SOLICITANTE_INTERNO', nombre: 'Solicitante interno' },
  permisos: ['solicitudes.ver_propias', 'solicitudes.crear'],
}

const catalogos: CatalogosSolicitud = {
  solicitante: {
    tipo_usuario: 'INTERNO', tipo_unidad: null, nombre: 'Ana Solicitante',
    correo: 'ana@example.com', identificacion: null, entidad: null,
    cargo: 'Docente', unidad: 'Ingeniería', programa: null,
  },
  tipos_convenio: [], tipos_documento: [], requiere_documento_representacion: true,
}

function respuesta(status: number, cuerpo: unknown) {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function Ubicacion() {
  return <output aria-label="Ruta actual">{useLocation().pathname}</output>
}

function montar(ruta = '/ori/solicitudes/41', sesion = gestor) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesion)
  const notify = vi.fn()
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <MemoryRouter initialEntries={[ruta]}>
          <Ubicacion />
          <Routes>
            <Route path="/ori/solicitudes" element={<SolicitudesRecibidasPage />} />
            <Route path="/ori/solicitudes/:solicitudId" element={<SolicitudRecibidaPage />} />
            <Route path="/solicitudes/:solicitudId" element={<SolicitudPage />} />
            <Route path="*" element={<p>Ruta inexistente</p>} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { cliente, notify }
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('HT-01: aprobación completa en ORI', () => {
  it.each(['RADICADA', 'EN_ESTUDIO'] as const)(
    'aprueba una solicitud %s, muestra la respuesta antes del refetch y actualiza la bandeja',
    async (estado) => {
      let persistida = { ...solicitud, estado: estado as EstadoSolicitud }
      let resolverRefetch: (value: Response) => void = () => { throw new Error('Refetch no iniciado') }
      const refetch = new Promise<Response>((resolve) => { resolverRefetch = resolve })
      const peticiones: string[] = []
      const incorrectas: string[] = []
      const fetch = vi.fn(async (url: string, init?: RequestInit) => {
        const peticion = `${init?.method ?? 'GET'} ${url}`
        peticiones.push(peticion)
        if (peticion === 'GET /api/solicitudes/recibidas') {
          return respuesta(200, { items: [persistida], total: 1 })
        }
        if (peticion === 'GET /api/solicitudes/recibidas/41') {
          return persistida.estado === 'APROBADA' ? refetch : respuesta(200, persistida)
        }
        if (peticion === 'POST /api/solicitudes/recibidas/41/aceptar') {
          persistida = {
            ...persistida, estado: 'APROBADA', decidida_por_id: gestor.id,
            decidida_por_nombre: gestor.nombre_completo, fecha_decision: '2026-10-13T14:00:00Z',
          }
          return respuesta(200, persistida)
        }
        incorrectas.push(peticion)
        return respuesta(404, { detail: 'Solicitud no encontrada' })
      })
      vi.stubGlobal('fetch', fetch)
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      const user = userEvent.setup()
      const { cliente, notify } = montar('/ori/solicitudes')
      cliente.setQueryData(['solicitudes', 41], solicitud)
      cliente.setQueryData(['solicitudes', 'mias'], { items: [solicitud], total: 1 })
      await user.click(await screen.findByRole('link', { name: 'Ver' }))
      expect(await screen.findByRole('heading', { name: solicitud.consecutivo })).toBeTruthy()
      expect(screen.getByText(estado.replaceAll('_', ' '))).toBeTruthy()
      await user.click(screen.getByRole('button', { name: 'Aprobar' }))
      expect(confirm).toHaveBeenCalledWith('¿Confirma que aprueba esta solicitud?')

      // Mantener pendiente la consulta posterior prueba que se usa el resultado del POST.
      expect(await screen.findByText('APROBADA')).toBeTruthy()
      await waitFor(() => expect(peticiones.filter(p => p === 'GET /api/solicitudes/recibidas/41')).toHaveLength(2))
      expect(persistida.estado).toBe('APROBADA')
      expect(cliente.getQueryData<SolicitudRecibida>(['solicitudes', 'recibidas', 41])?.estado).toBe('APROBADA')
      expect(screen.getByRole('button', { name: 'Iniciar elaboración' })).toBeTruthy()
      for (const name of ['Aprobar', 'Rechazar', 'Devolver']) {
        expect(screen.queryByRole('button', { name })).toBeNull()
      }
      expect(screen.queryByText(/Solicitud no encontrada/)).toBeNull()
      expect(screen.getByLabelText('Ruta actual').textContent).toBe('/ori/solicitudes/41')

      resolverRefetch(respuesta(200, persistida))
      await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'success', message: 'Solicitud aprobada' }))
      expect(cliente.getQueryState(['solicitudes', 41])?.isInvalidated).toBe(true)
      expect(cliente.getQueryState(['solicitudes', 'mias'])?.isInvalidated).toBe(true)
      expect(screen.getByText('APROBADA')).toBeTruthy()
      expect(screen.getByText('Aprobada')).toBeTruthy()
      expect(screen.getByText(gestor.nombre_completo)).toBeTruthy()
      await user.click(screen.getByRole('link', { name: 'Volver' }))
      const tabla = await screen.findByRole('table', { name: 'Solicitudes recibidas' })
      await waitFor(() => expect(within(tabla).getByText('Aprobada')).toBeTruthy())
      expect(peticiones).toEqual([
        'GET /api/solicitudes/recibidas',
        'GET /api/solicitudes/recibidas/41',
        'POST /api/solicitudes/recibidas/41/aceptar',
        'GET /api/solicitudes/recibidas/41',
        'GET /api/solicitudes/recibidas',
      ])
      expect(incorrectas).toEqual([])
      expect(screen.queryByText(/Solicitud no encontrada|Ruta inexistente|Aceptada/)).toBeNull()
      expect(screen.getByLabelText('Ruta actual').textContent).toBe('/ori/solicitudes')
    },
  )

  it('no aprueba ni navega cuando se cancela la confirmación', async () => {
    const fetch = vi.fn(async () => respuesta(200, solicitud))
    vi.stubGlobal('fetch', fetch)
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    montar()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Aprobar' }))
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(screen.getByText('RADICADA')).toBeTruthy()
    expect(screen.getByLabelText('Ruta actual').textContent).toBe('/ori/solicitudes/41')
  })

  it('conserva el detalle y muestra el error real cuando el POST falla', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? respuesta(409, { detail: 'La solicitud ya no admite decisión' })
        : respuesta(200, solicitud)))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { notify } = montar()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Aprobar' }))
    await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'error', message: 'La solicitud ya no admite decisión' }))
    expect(screen.getByText('RADICADA')).toBeTruthy()
    expect(screen.queryByText('APROBADA')).toBeNull()
    expect(screen.queryByText(/Solicitud no encontrada/)).toBeNull()
  })

  it('muestra en ORI las observaciones anteriores al consultar una solicitud nuevamente radicada', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta(200, {
      ...solicitud, observaciones_devolucion: 'Ajustar la vigencia a 24 meses.',
    })))
    montar()
    expect(await screen.findByText('Ajustar la vigencia a 24 meses.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Observaciones de devolución anterior' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Decisión ORI' })).toBeNull()
  })
})

describe('HT-01: retroalimentación desde el backend en el portal Solicitante', () => {
  it.each(['DEVUELTA', 'RADICADA', 'EN_ESTUDIO', 'RECHAZADA'] as const)(
    'consulta identidad, estado %s y motivo con una caché vacía', async (estado) => {
      const motivo = 'Precisar cláusula 3, NIT 123 y vigencia: 24 meses.'
      const fetch = vi.fn(async (url: string) => {
        if (url === '/api/solicitudes/catalogos') return respuesta(200, catalogos)
        if (url === '/api/solicitudes/41') return respuesta(200, {
          ...solicitud, estado, motivo_rechazo: estado === 'RECHAZADA' ? motivo : null,
          observaciones_devolucion: estado === 'RECHAZADA' ? null : motivo,
        })
        return respuesta(404, { detail: 'Solicitud no encontrada' })
      })
      vi.stubGlobal('fetch', fetch)
      montar('/solicitudes/41', solicitante)
      expect(await screen.findByRole('heading', { name: solicitud.consecutivo })).toBeTruthy()
      expect(screen.getByText(`Estado: ${estado}`)).toBeTruthy()
      expect(screen.getByText(motivo)).toBeTruthy()
      expect((screen.getByRole('textbox', { name: 'Responsable y/o solicitante *' }) as HTMLInputElement).value).toBe('Ana Solicitante')
      expect(fetch.mock.calls.map(([url]) => url).sort()).toEqual(['/api/solicitudes/41', '/api/solicitudes/catalogos'])
      expect(screen.queryByText(/Solicitud no encontrada/)).toBeNull()
    },
  )
})

function tarjeta(titulo: string) {
  const seccion = screen.getByRole('heading', { name: titulo }).closest('section')
  if (!seccion) throw new Error(`No se encontró la tarjeta ${titulo}`)
  return within(seccion)
}

describe('HT-01: decisión vigente y observaciones de una devolución anterior', () => {
  it.each(['APROBADA', 'RECHAZADA'] as const)(
    'consulta en ambos portales una devolución, nueva radicación y decisión final %s',
    async (resultadoFinal) => {
      const observaciones = 'Precisar el objeto y adjuntar el RUT actualizado.'
      const motivoRechazo = 'La contraparte no cumple los requisitos para el convenio.'
      let persistida: SolicitudRecibida = solicitud
      const incorrectas: string[] = []
      const fetch = vi.fn(async (url: string, init?: RequestInit) => {
        if (!init?.method || init.method === 'GET') {
          if (url === '/api/solicitudes/catalogos') return respuesta(200, catalogos)
          if (url === '/api/solicitudes/recibidas/41' || url === '/api/solicitudes/41') {
            return respuesta(200, persistida)
          }
        }
        incorrectas.push(`${init?.method ?? 'GET'} ${url}`)
        return respuesta(404, { detail: 'Solicitud no encontrada' })
      })
      vi.stubGlobal('fetch', fetch)

      const fases: EstadoSolicitud[] = ['DEVUELTA', 'RADICADA', 'EN_ESTUDIO', resultadoFinal]
      for (const estado of fases) {
        const decidida = ['DEVUELTA', 'APROBADA', 'RECHAZADA'].includes(estado)
        persistida = {
          ...solicitud, estado, observaciones_devolucion: observaciones,
          motivo_rechazo: estado === 'RECHAZADA' ? motivoRechazo : null,
          decidida_por_id: decidida ? gestor.id : null,
          decidida_por_nombre: decidida ? gestor.nombre_completo : null,
          fecha_decision: decidida ? '2026-10-13T14:00:00Z' : null,
        }

        // Cada portal consulta la misma respuesta HTTP con una caché nueva.
        cleanup()
        montar()
        await screen.findByRole('heading', { name: solicitud.consecutivo })
        expect(screen.getByText(estado.replaceAll('_', ' '))).toBeTruthy()
        if (decidida) {
          const decision = tarjeta('Decisión ORI')
          expect(decision.getByText(estado === 'DEVUELTA' ? 'Devuelta' : estado === 'APROBADA' ? 'Aprobada' : 'Rechazada')).toBeTruthy()
          expect(decision.queryByText(observaciones)).toBe(estado === 'DEVUELTA' ? screen.getByText(observaciones) : null)
          expect(decision.queryByText(motivoRechazo)).toBe(estado === 'RECHAZADA' ? screen.getByText(motivoRechazo) : null)
        } else {
          expect(screen.queryByRole('heading', { name: 'Decisión ORI' })).toBeNull()
        }
        if (estado === 'DEVUELTA') {
          expect(screen.queryByRole('heading', { name: 'Observaciones de devolución anterior' })).toBeNull()
        } else {
          const anterior = tarjeta('Observaciones de devolución anterior')
          expect(anterior.getByText(observaciones)).toBeTruthy()
          expect(anterior.queryByText(motivoRechazo)).toBeNull()
        }

        cleanup()
        montar('/solicitudes/41', solicitante)
        await screen.findByRole('heading', { name: solicitud.consecutivo })
        expect(screen.getByText(`Estado: ${estado}`)).toBeTruthy()
        const devolucion = tarjeta(estado === 'DEVUELTA' ? 'Observaciones de devolución ORI' : 'Observaciones de devolución anterior')
        expect(devolucion.getByText(observaciones)).toBeTruthy()
        expect(devolucion.queryByText(motivoRechazo)).toBeNull()
        expect(screen.queryByText('Corrija la información y los documentos indicados. Luego vuelva a radicar la solicitud.'))
          .toBe(estado === 'DEVUELTA' ? screen.getByText('Corrija la información y los documentos indicados. Luego vuelva a radicar la solicitud.') : null)
        if (estado === 'RECHAZADA') {
          const rechazo = tarjeta('Motivo del rechazo ORI')
          expect(rechazo.getByText(motivoRechazo)).toBeTruthy()
          expect(rechazo.queryByText(observaciones)).toBeNull()
        } else {
          expect(screen.queryByRole('heading', { name: 'Motivo del rechazo ORI' })).toBeNull()
        }
        expect(screen.queryByText(/Solicitud no encontrada/)).toBeNull()
      }
      expect(fetch).toHaveBeenCalledTimes(12)
      expect(incorrectas).toEqual([])
    },
  )

  it.each(['DEVUELTA', 'APROBADA'] as const)(
    'no presenta un motivo de rechazo residual como parte de la decisión %s en ORI', async (estado) => {
      vi.stubGlobal('fetch', vi.fn(async () => respuesta(200, {
        ...solicitud, estado, fecha_decision: '2026-10-13T14:00:00Z',
        motivo_rechazo: 'Motivo residual que no corresponde a la decisión vigente',
        observaciones_devolucion: 'Observaciones de la devolución',
      })))
      montar()
      await screen.findByRole('heading', { name: 'Decisión ORI' })
      expect(tarjeta('Decisión ORI').queryByText('Motivo del rechazo')).toBeNull()
      expect(screen.queryByText('Motivo residual que no corresponde a la decisión vigente')).toBeNull()
    },
  )
})

describe('HU-23: previsualización de documentos adjuntos en SolicitudRecibidaPage (CA-01, CA-02, CA-03)', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '')
    }
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute('open')
      this.dispatchEvent(new Event('close'))
    }
  })

  it('permite previsualizar un documento adjunto abriendo el modal', async () => {
    const solicitudConDocs: SolicitudRecibida = {
      ...solicitud,
      documentos: [
        {
          id: 101,
          tipo_documento: 'OTRO_SOPORTE',
          nombre_original: 'carta_intencion.pdf',
          tamano_bytes: 1024,
          tipo_mime: 'application/pdf',
          creado_en: '2026-10-13T12:00:00Z',
        },
      ],
    }

    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/carta-mock')
    window.URL.revokeObjectURL = vi.fn()

    const fetch = vi.fn(async (url: string) => {
      if (url.includes('disposicion=inline')) {
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob(['%PDF-1.4 prueba'], { type: 'application/pdf' }),
          headers: new Headers({ 'Content-Type': 'application/pdf' }),
        }
      }
      return respuesta(200, solicitudConDocs)
    })
    vi.stubGlobal('fetch', fetch)

    const user = userEvent.setup()
    montar('/ori/solicitudes/41', gestor)

    expect(await screen.findByRole('heading', { name: solicitud.consecutivo })).toBeTruthy()
    expect(screen.getByText('carta_intencion.pdf')).toBeTruthy()

    const btnPrevisualizar = screen.getByRole('button', { name: 'Previsualizar' })
    await user.click(btnPrevisualizar)

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: 'carta_intencion.pdf' })).toBeTruthy()

    const btnCerrar = screen.getByRole('button', { name: 'Cerrar previsualizador' })
    await user.click(btnCerrar)

    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 2, name: 'carta_intencion.pdf' })).toBeNull()
    })
  })
})
