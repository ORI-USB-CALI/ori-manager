import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { RevisionFinalConvenio } from './RevisionFinalConvenio'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
  window.URL.createObjectURL = vi.fn().mockReturnValue('blob:http://localhost/revision-final-mock')
  window.URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const datosRevisionFinal = {
  convenio: {
    id: 10,
    codigo: 'CON-010',
    solicitud_id: null,
    origen: 'MANUAL_ORI',
    aliado_id: 1,
    aliado: { id: 1, nombre: 'Universidad Aliada' },
    tipo_convenio_id: 1,
    tipo_convenio: { id: 1, codigo: 'MARCO', nombre: 'Convenio Marco' },
    etapa_actual_id: 5,
    etapa_actual: { id: 5, codigo: 'REVISION_FINAL', nombre: 'Revisión final' },
    plantilla_origen_id: null,
    version_actual: 2,
    estado: 'EN_TRAMITE',
    objeto: 'Cooperación institucional',
    alcance: null,
    unidad_organizacional_id: null,
    implicacion_financiera: null,
    fecha_inicio: null,
    fecha_vencimiento: null,
    fecha_firma: null,
    duracion_meses: 12,
    porcentaje_avance: 70,
    convenio_origen_id: null,
    numero_renovacion: null,
    creado_por_id: 1,
    creado_en: '2026-10-01T10:00:00Z',
    actualizado_en: '2026-10-15T12:00:00Z',
    solicitud: null,
    unidad_organizacional: null,
    plantilla_origen: null,
    contenido: null,
    revision_borrador: 0,
    borrador_guardado_en: null,
  },
  documentos: [
    {
      id: 201,
      tipo: 'ANEXO_TECNICO',
      nombre_archivo: 'anexo_tecnico_aprobado.pdf',
      tipo_mime: 'application/pdf',
      tamano_bytes: 4096,
      creado_en: '2026-10-14T10:00:00Z',
    },
  ],
  revision_pendiente: {
    id: 15,
    tipo: 'REVISION_FINAL',
    estado: 'PENDIENTE',
    instancia_juridica: 2,
    numero_ronda: 1,
    creado_en: '2026-10-15T10:00:00Z',
    resuelta_en: null,
    version_convenio_id: 2,
    version_resultado_id: null,
    version_convenio: { id: 2, numero: 2 },
    version_resultado: null,
    observaciones: [],
    invitaciones_contraparte: [],
    respuesta_contraparte: null,
  },
  version_aprobada_contraparte: {
    id: 2,
    numero: 2,
    autor: { id: 1, nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' },
    etapa: { id: 4, codigo: 'REVISION_CONTRAPARTE', nombre: 'Revisión por contraparte' },
    contexto: 'FINALIZACION',
    creado_en: '2026-10-14T15:00:00Z',
    plantilla: null,
    contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Convenio formal' }] }] },
    snapshot_metadata: {},
  },
  revisiones_juridicas: [],
  revision_contraparte: {
    id: 14,
    tipo: 'CONTRAPARTE',
    estado: 'APROBADA',
    instancia_juridica: 1,
    numero_ronda: 1,
    creado_en: '2026-10-12T10:00:00Z',
    resuelta_en: '2026-10-14T14:00:00Z',
    version_convenio_id: 1,
    version_resultado_id: 2,
    version_convenio: { id: 1, numero: 1 },
    version_resultado: { id: 2, numero: 2 },
    observaciones: [],
    invitaciones_contraparte: [],
    respuesta_contraparte: null,
  },
  observaciones_pendientes: [],
  revision_final_aprobada: false,
  proceso_firmas_abierto: false,
}

function renderizar() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const notify = vi.fn()
  return render(
    <NotificationsContext.Provider value={notify}>
      <QueryClientProvider client={cliente}>
        <RevisionFinalConvenio convenioId={10} />
      </QueryClientProvider>
    </NotificationsContext.Provider>,
  )
}

describe('RevisionFinalConvenio (HU-23: CA-01, CA-02, CA-03)', () => {
  it('permite previsualizar un documento asociado abriendo el modal y cerrándolo', async () => {
    const user = userEvent.setup()

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('disposicion=inline')) {
          return {
            ok: true,
            status: 200,
            blob: async () => new Blob(['%PDF-1.4 prueba final'], { type: 'application/pdf' }),
            headers: new Headers({ 'Content-Type': 'application/pdf' }),
          }
        }
        return {
          ok: true,
          status: 200,
          json: async () => datosRevisionFinal,
        }
      }),
    )

    renderizar()

    // Esperar a que cargue la sección de documentos asociados
    expect(await screen.findByRole('heading', { name: 'Documentos asociados' })).toBeTruthy()
    expect(screen.getByText(/anexo_tecnico_aprobado\.pdf/)).toBeTruthy()

    const btnVer = screen.getByRole('link', { name: 'Ver' })
    expect(btnVer.getAttribute('href')).toBe('/api/convenios/10/documentos/201/contenido?disposicion=inline')

    // Clic en Ver abre el modal
    await user.click(btnVer)

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: 'anexo_tecnico_aprobado.pdf' })).toBeTruthy()

    // Cierre
    const btnCerrar = screen.getByRole('button', { name: 'Cerrar previsualizador' })
    await user.click(btnCerrar)

    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 2, name: 'anexo_tecnico_aprobado.pdf' })).toBeNull()
    })
    expect(screen.getByRole('heading', { name: 'Documentos asociados' })).toBeTruthy()
  })

  it('muestra mensaje informativo cuando no hay documentos asociados', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...datosRevisionFinal, documentos: [] }),
      }),
    )

    renderizar()

    expect(await screen.findByText('No hay documentos vigentes asociados.')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Ver' })).toBeNull()
  })
})

