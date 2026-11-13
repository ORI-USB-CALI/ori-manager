import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConvenioDetallePage } from './ConvenioDetallePage'
import { ConvenioHistorialPage } from './ConvenioHistorialPage'
import type { Convenio, HistorialConvenio } from './epica02'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
    this.querySelector('button')?.focus()
  }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
  window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/mock-preview')
  window.URL.revokeObjectURL = vi.fn()
})

const convenio: Convenio = {
  id: 41, codigo: 'CON-041', solicitud_id: 1, origen: 'SOLICITUD', aliado_id: null, aliado: null,
  tipo_convenio_id: null, etapa_actual_id: null, plantilla_origen_id: null,
  version_actual: 3, estado: 'VIGENTE', objeto: 'Movilidad académica', alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null,
  fecha_inicio: '2025-01-01', fecha_vencimiento: '2027-03-01', fecha_firma: '2025-01-01',
  duracion_meses: 24, porcentaje_avance: 100, convenio_origen_id: null, numero_renovacion: null,
  creado_por_id: 1, creado_por: { id: 1, nombre_completo: 'Gestor', correo: 'gestor@example.com' },
  creado_en: '2025-01-01T12:00:00Z', actualizado_en: '2026-10-08T05:00:00Z',
}

const historial: HistorialConvenio = { revisiones: [], cambios_etapa: [] }

const sesion: Sesion = {
  id: 1, correo: 'usuario@example.com', nombre_completo: 'Usuario', activo: true, tipo_usuario: 'INTERNO',
  rol: { codigo: 'REVISOR_ORI', nombre: 'Revisor ORI' }, permisos: ['convenios.ver'],
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function Ubicacion() {
  const { pathname, search } = useLocation()
  return (
    <>
      <output data-testid="ubicacion">{search}</output>
      <output data-testid="ruta-actual">{pathname}{search}</output>
    </>
  )
}

function preparar({
  ruta = '/convenios/41',
  lineaTiempoDisponible = true,
  datos = convenio,
  historialSolicitudStatus = 200,
  documentoStatus = 200,
  sesionUsuario = sesion,
  elaboracionData = null,
  revisionData = null,
  estado = undefined,
}: {
  ruta?: string
  lineaTiempoDisponible?: boolean
  datos?: Convenio
  historialSolicitudStatus?: number
  documentoStatus?: number
  sesionUsuario?: Sesion
  elaboracionData?: unknown
  revisionData?: unknown
  estado?: unknown
} = {}) {
  const notify = vi.fn()
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/aprobar') && init?.method === 'POST') {
      return respuesta(200, { id: 1, estado: 'RESUELTA', resultado: 'APROBADA' })
    }
    if (url.endsWith('/devolver') && init?.method === 'POST') {
      return respuesta(200, { id: 1, estado: 'RESUELTA', resultado: 'DEVUELTA' })
    }
    if (url === '/api/convenios/41/revisiones') return respuesta(200, historial)
    if (url === '/api/solicitudes/recibidas/1/historial') {
      return historialSolicitudStatus === 200
        ? respuesta(200, { solicitud_id: 1, consecutivo: 'SOL-00000001', estado: 'APROBADA', versiones: [{ numero: 1, radicada_en: '2026-10-01T15:00:00Z', devolucion: null }] })
        : respuesta(historialSolicitudStatus, { detail: 'Acceso denegado' })
    }
    if (url === '/api/convenios/41/linea-tiempo' && lineaTiempoDisponible) {
      return respuesta(200, [{ codigo: 'ACTIVACION', nombre: 'Activación', fecha: null, estado: 'PENDIENTE' }])
    }
    if (url === '/api/convenios/41/elaboracion') {
      return respuesta(200, elaboracionData ?? { etapa_actual: null })
    }
    if (url === '/api/convenios/41/revision') {
      return revisionData ? respuesta(200, revisionData) : respuesta(404, { detail: 'Not Found' })
    }
    if (url.includes('disposicion=inline')) {
      if (documentoStatus !== 200) {
        return {
          ok: false,
          status: documentoStatus,
          statusText: 'Error',
          text: async () => JSON.stringify({ detail: 'Error de acceso al documento' }),
        } as unknown as Response
      }
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4 prueba'], { type: 'application/pdf' }),
        headers: new Headers({ 'Content-Type': 'application/pdf' }),
      } as unknown as Response
    }
    return respuesta(404, { detail: 'Not Found' })
  })
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesionUsuario)
  cliente.setQueryData(['convenio', datos.id], datos)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <MemoryRouter initialEntries={[estado === undefined ? ruta : { pathname: ruta, state: estado }]}>
          <Routes>
            <Route path="/convenios/:convenioId" element={<><ConvenioDetallePage /><Ubicacion /></>} />
            <Route path="/convenios/:convenioId/historial" element={<><ConvenioHistorialPage /><Ubicacion /></>} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { fetch, notify, usuario: userEvent.setup() }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('pestañas del detalle del convenio', () => {
  it('ubica Volver antes del encabezado y regresa al listado desde el que se abrió (HT-12)', () => {
    preparar({ estado: { volver: { to: '/revisiones-juridicas', texto: 'Volver a revisiones jurídicas' } } })
    const volver = screen.getByRole('link', { name: 'Volver a revisiones jurídicas' })
    expect(volver.getAttribute('href')).toBe('/revisiones-juridicas')
    expect(volver.compareDocumentPosition(screen.getByRole('heading', { level: 1 })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByRole('link', { name: /^Volver/ })).toHaveLength(1)
  })

  it('muestra el historial manual sin consultar solicitudes y vuelve al tablero', async () => {
    const { fetch, usuario } = preparar({
      ruta: '/convenios/41?pestana=historial',
      datos: { ...convenio, origen: 'MANUAL_ORI', solicitud_id: null, estado: 'EN_TRAMITE', fecha_firma: null },
    })
    expect(await screen.findByRole('region', { name: 'Observaciones jurídicas' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Volver al tablero de convenios' }).getAttribute('href'))
      .toBe('/convenios/tablero')
    expect(fetch.mock.calls.some(([url]) => url.includes('/solicitudes/'))).toBe(false)
    expect(screen.queryByRole('region', { name: 'Versiones de la solicitud' })).toBeNull()
    await usuario.click(screen.getByRole('tab', { name: 'Resumen' }))
    expect(screen.getByText('Creado directamente por ORI')).toBeTruthy()
  })

  it('conserva las observaciones y los hitos cuando no se autoriza el historial de solicitud', async () => {
    preparar({ ruta: '/convenios/41?pestana=historial', historialSolicitudStatus: 403 })
    expect(await screen.findByRole('region', { name: 'Observaciones jurídicas' })).toBeTruthy()
    expect(await screen.findByText('Activación')).toBeTruthy()
    await waitFor(() => expect(screen.queryByText('Cargando versiones de la solicitud…')).toBeNull())
    expect(screen.queryByRole('region', { name: 'Versiones de la solicitud' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Volver a la consulta de convenios' }).getAttribute('href'))
      .toBe('/convenios')
  })

  it('abre en Resumen sin la línea de tiempo, sin consultar el historial ni mostrar el enlace anterior', () => {
    const { fetch } = preparar()

    const resumen = screen.getByRole('tab', { name: 'Resumen' })
    expect(resumen.getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tab', { name: 'Historial' }).getAttribute('aria-selected')).toBe('false')
    const panel = screen.getByRole('tabpanel', { name: 'Resumen' })
    expect(within(panel).getByRole('heading', { name: 'Información base' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Ver historial y trazabilidad' })).toBeNull()
    expect(fetch).not.toHaveBeenCalledWith('/api/convenios/41/revisiones', expect.anything())
    expect(screen.queryByRole('region', { name: 'Línea de tiempo' })).toBeNull()
    expect(fetch).not.toHaveBeenCalledWith('/api/convenios/41/linea-tiempo', expect.anything())
    expect(fetch).not.toHaveBeenCalledWith('/api/solicitudes/recibidas/1/historial', expect.anything())
  })

  it('cambia a Historial, lo refleja en la URL y muestra la línea de tiempo antes de las observaciones', async () => {
    const { usuario } = preparar()

    await usuario.click(screen.getByRole('tab', { name: 'Historial' }))

    expect(screen.getByRole('tab', { name: 'Historial' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByTestId('ubicacion').textContent).toBe('?pestana=historial')
    const panel = screen.getByRole('tabpanel', { name: 'Historial' })
    expect(screen.queryByRole('tabpanel', { name: 'Resumen' })).toBeNull()
    const lineaTiempo = within(panel).getByRole('region', { name: 'Línea de tiempo' })
    expect(await within(lineaTiempo).findByText('Activación')).toBeTruthy()
    const observaciones = await within(panel).findByRole('region', { name: 'Observaciones jurídicas' })
    expect(lineaTiempo.compareDocumentPosition(observaciones) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const versiones = await within(panel).findByRole('region', { name: 'Versiones de la solicitud' })
    expect(observaciones.compareDocumentPosition(versiones) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(await within(versiones).findByText('Solo existe la radicación inicial; no hay cambios que comparar.')).toBeTruthy()
  })

  it('abre directamente en Historial con ?pestana=historial y vuelve a Resumen con el teclado', async () => {
    const { usuario } = preparar({ ruta: '/convenios/41?pestana=historial', lineaTiempoDisponible: false })

    const historialTab = screen.getByRole('tab', { name: 'Historial' })
    expect(historialTab.getAttribute('aria-selected')).toBe('true')
    expect(historialTab.tabIndex).toBe(0)
    expect(await screen.findByText('No fue posible consultar la línea de tiempo del convenio.')).toBeTruthy()
    expect(await screen.findByRole('region', { name: 'Observaciones jurídicas' })).toBeTruthy()

    historialTab.focus()
    await usuario.keyboard('{ArrowLeft}')

    const resumen = screen.getByRole('tab', { name: 'Resumen' })
    await waitFor(() => expect(resumen.getAttribute('aria-selected')).toBe('true'))
    expect(document.activeElement).toBe(resumen)
    expect(screen.getByTestId('ubicacion').textContent).toBe('')
    expect(screen.getByRole('tabpanel', { name: 'Resumen' })).toBeTruthy()
  })
})

describe('HU-23: previsualización de documentos asociados en revisión jurídica (CA-01, CA-02, CA-03)', () => {
  it('permite al revisor previsualizar un documento adjunto en modal y regresar al contexto', async () => {
    const sesionRevisor: Sesion = {
      ...sesion,
      permisos: ['convenios.ver', 'convenios.revisar'],
    }
    const elaboracionConEtapa = {
      ...convenio,
      etapa_actual: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
    }
    const revisionConDocs = {
      version_actual: {
        numero: 1,
        contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Texto del convenio' }] }] },
      },
      version_recibida: { numero: 1 },
      revision_pendiente: {
        id: 1,
        instancia_juridica: 1,
        numero_ronda: 1,
        creado_en: '2026-10-20T10:00:00Z',
        observaciones: [],
      },
      documentos: [
        {
          id: 1,
          tipo: 'PROPUESTA_CONVENIO',
          nombre_archivo: 'propuesta_academica.pdf',
          tipo_mime: 'application/pdf',
          tamano_bytes: 2048,
          creado_en: '2026-10-20T10:00:00Z',
        },
      ],
    }

    const { usuario } = preparar({
      sesionUsuario: sesionRevisor,
      elaboracionData: elaboracionConEtapa,
      revisionData: revisionConDocs,
    })

    expect(await screen.findByRole('heading', { name: 'Documentos asociados' })).toBeTruthy()
    expect(screen.getByText(/propuesta_academica\.pdf/)).toBeTruthy()

    const btnVer = screen.getByRole('link', { name: 'Ver' })
    await usuario.click(btnVer)

    // Se abre el modal con el documento
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: 'propuesta_academica.pdf' })).toBeTruthy()

    // Botón de cierre
    const btnCerrar = screen.getByRole('button', { name: 'Cerrar previsualizador' })
    await usuario.click(btnCerrar)

    // Se cierra y regresa a la revisión
    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 2, name: 'propuesta_academica.pdf' })).toBeNull()
    })
    expect(screen.getByRole('heading', { name: 'Documentos asociados' })).toBeTruthy()
  })

  it('CA-03 y CA-05 (HU23-TC06): conserva el foco y el scroll al cerrar el visor en revisión jurídica sin forzar descarga', async () => {
    const sesionRevisor: Sesion = {
      ...sesion,
      permisos: ['convenios.ver', 'convenios.revisar'],
    }
    const elaboracionConEtapa = {
      ...convenio,
      etapa_actual: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
    }
    const revisionConDocs = {
      version_actual: {
        numero: 1,
        contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Texto del convenio' }] }] },
      },
      version_recibida: { numero: 1 },
      revision_pendiente: {
        id: 1,
        instancia_juridica: 1,
        numero_ronda: 1,
        creado_en: '2026-10-20T10:00:00Z',
        observaciones: [],
      },
      documentos: [
        {
          id: 1,
          tipo: 'PROPUESTA_CONVENIO',
          nombre_archivo: 'propuesta_academica.pdf',
          tipo_mime: 'application/pdf',
          tamano_bytes: 2048,
          creado_en: '2026-10-20T10:00:00Z',
        },
      ],
    }

    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation((x, y) => {
      vi.stubGlobal('scrollX', x)
      vi.stubGlobal('scrollY', y)
    })
    vi.stubGlobal('scrollX', 0)
    vi.stubGlobal('scrollY', 420)

    try {
      const { fetch, usuario } = preparar({
        sesionUsuario: sesionRevisor,
        elaboracionData: elaboracionConEtapa,
        revisionData: revisionConDocs,
      })

      const btnVer = await screen.findByRole('link', { name: 'Ver' })
      btnVer.focus()
      await usuario.click(btnVer)

      // Simular que el navegador desplazó la ventana al abrir el modal
      vi.stubGlobal('scrollX', 0)
      vi.stubGlobal('scrollY', 0)

      expect(await screen.findByTestId('preview-iframe')).toBeTruthy()
      expect(fetch.mock.calls.some(([url]) => String(url).includes('disposicion=attachment'))).toBe(false)

      await usuario.click(screen.getByRole('button', { name: 'Cerrar previsualizador' }))

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).toBeNull()
      })
      expect(document.activeElement).toBe(btnVer)
      expect(scrollTo).toHaveBeenCalledWith(0, 420)
      expect(fetch.mock.calls.filter(([url]) => String(url).includes('disposicion=inline'))).toHaveLength(1)
    } finally {
      scrollTo.mockRestore()
    }
  })

  it.each([
    [403, 'No tiene permiso para consultar este documento.'],
    [404, 'El documento solicitado no fue encontrado o no está vigente.'],
  ])('CA-05 (HU23-TC06): maneja respuesta %i en el visor durante revisión jurídica y restaura el foco al cerrar', async (codigo, mensajeEsperado) => {
    const sesionRevisor: Sesion = {
      ...sesion,
      permisos: ['convenios.ver', 'convenios.revisar'],
    }
    const elaboracionConEtapa = {
      ...convenio,
      etapa_actual: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
    }
    const revisionConDocs = {
      version_actual: {
        numero: 1,
        contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Texto del convenio' }] }] },
      },
      version_recibida: { numero: 1 },
      revision_pendiente: {
        id: 1,
        instancia_juridica: 1,
        numero_ronda: 1,
        creado_en: '2026-10-20T10:00:00Z',
        observaciones: [],
      },
      documentos: [
        {
          id: 1,
          tipo: 'PROPUESTA_CONVENIO',
          nombre_archivo: 'propuesta_academica.pdf',
          tipo_mime: 'application/pdf',
          tamano_bytes: 2048,
          creado_en: '2026-10-20T10:00:00Z',
        },
      ],
    }

    const { usuario } = preparar({
      sesionUsuario: sesionRevisor,
      elaboracionData: elaboracionConEtapa,
      revisionData: revisionConDocs,
      documentoStatus: codigo,
    })

    const btnVer = await screen.findByRole('link', { name: 'Ver' })
    btnVer.focus()
    await usuario.click(btnVer)

    expect(await screen.findByTestId('preview-error')).toBeTruthy()
    expect(screen.getByText(mensajeEsperado)).toBeTruthy()
    expect(screen.queryByTestId('preview-iframe')).toBeNull()

    await usuario.click(screen.getByRole('button', { name: 'Cerrar' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
    expect(document.activeElement).toBe(btnVer)
    expect(screen.getByRole('heading', { name: 'Documentos asociados' })).toBeTruthy()
  })

  it('CA-04: restringe las acciones visibles en el detalle según los permisos del perfil ORI', async () => {
    const sesionGestor: Sesion = {
      ...sesion,
      rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' },
      permisos: ['convenios.ver', 'convenios.editar', 'convenios.gestionar_soportes'],
    }
    const { fetch } = preparar({
      datos: { ...convenio, estado: 'EN_TRAMITE', fecha_firma: null },
      sesionUsuario: sesionGestor,
      elaboracionData: {
        ...convenio,
        estado: 'EN_TRAMITE',
        etapa_actual: { codigo: 'ELABORACION', nombre: 'Elaboración' },
      },
    })

    expect(await screen.findByRole('link', { name: 'Continuar elaboración' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Aprobar revisión' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Enviar a revisión de contraparte' })).toBeNull()
    expect(fetch.mock.calls.some(([url]) => url === '/api/convenios/41/revision')).toBe(false)
  })
})

describe('CA-01 (#176): redirección posterior a la aprobación jurídica de convenios', () => {
  const sesionRevisor: Sesion = {
    ...sesion,
    permisos: ['convenios.ver', 'convenios.revisar'],
  }

  function datosRevision(instancia: 1 | 2) {
    return {
      version_actual: {
        numero: 1,
        contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Cláusula única' }] }] },
      },
      version_recibida: { numero: 1 },
      revision_pendiente: {
        id: 15,
        instancia_juridica: instancia,
        numero_ronda: 1,
        creado_en: '2026-10-20T10:00:00Z',
        observaciones: [],
      },
      documentos: [],
    }
  }

  it('redirige al historial del convenio tras aprobar un convenio manual sin intentar cargar una solicitud inexistente', async () => {
    const convenioManual: Convenio = {
      ...convenio,
      origen: 'MANUAL_ORI',
      solicitud_id: null,
      estado: 'EN_TRAMITE',
      fecha_firma: null,
    }
    const { fetch, notify, usuario } = preparar({
      datos: convenioManual,
      sesionUsuario: sesionRevisor,
      elaboracionData: {
        ...convenioManual,
        etapa_actual: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
      },
      revisionData: datosRevision(1),
      estado: { volver: { to: '/revisiones-juridicas', texto: 'Volver a revisiones jurídicas' } },
    })

    const btnAprobar = await screen.findByRole('button', { name: 'Aprobar revisión' })
    await usuario.click(btnAprobar)

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith({
        type: 'success',
        message: 'Primera revisión aprobada. Se habilitó la segunda revisión.',
      })
    })
    await waitFor(() => {
      expect(screen.getByTestId('ruta-actual').textContent).toBe('/convenios/41/historial')
    })
    expect(await screen.findByRole('heading', { level: 1, name: 'Historial y trazabilidad' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Volver a revisiones jurídicas' }).getAttribute('href'))
      .toBe('/revisiones-juridicas')
    expect(fetch.mock.calls.some(([url]) => String(url).includes('/solicitudes/'))).toBe(false)
    expect(fetch.mock.calls.some(([url]) => url === '/api/convenios/41')).toBe(false)
  })

  it('redirige a una vista válida correspondiente al flujo tras aprobar un convenio derivado de solicitud', async () => {
    const convenioSolicitud: Convenio = {
      ...convenio,
      origen: 'SOLICITUD',
      solicitud_id: 1,
      estado: 'EN_TRAMITE',
      fecha_firma: null,
    }
    const { fetch, notify, usuario } = preparar({
      datos: convenioSolicitud,
      sesionUsuario: sesionRevisor,
      elaboracionData: {
        ...convenioSolicitud,
        etapa_actual: { codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión y aval jurídico' },
      },
      revisionData: datosRevision(2),
    })

    const btnAprobar = await screen.findByRole('button', { name: 'Aprobar revisión' })
    await usuario.click(btnAprobar)

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith({
        type: 'success',
        message: 'Segunda revisión aprobada. El proyecto quedó habilitado para contraparte.',
      })
    })
    await waitFor(() => {
      expect(screen.getByTestId('ruta-actual').textContent).toBe('/convenios/41/historial')
    })
    expect(await screen.findByRole('heading', { level: 1, name: 'Historial y trazabilidad' })).toBeTruthy()
    expect(fetch.mock.calls.some(([url]) => url === '/api/convenios/41')).toBe(false)
  })
})
