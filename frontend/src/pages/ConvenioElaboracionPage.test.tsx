import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConvenioElaboracionPage } from './ConvenioElaboracionPage'
import type { ElaboracionConvenio } from './epica02'

vi.mock('../components/ConvenioEditor', () => ({
  ConvenioEditor: ({ contenido, onChange }: {
    contenido: Record<string, unknown>
    onChange: (nuevo: Record<string, unknown>) => void
  }) => (
    <div>
      <output data-testid="documento">{JSON.stringify(contenido)}</output>
      <button type="button" onClick={() => onChange(DOCUMENTO_EDITADO)}>Editar documento</button>
    </div>
  ),
}))

const DOCUMENTO = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Versión 1' }] }] }
const DOCUMENTO_EDITADO = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Avance nuevo' }] }] }

const elaboracion: ElaboracionConvenio = {
  id: 7, codigo: null, solicitud_id: null, origen: 'MANUAL_ORI', aliado_id: null, aliado: null,
  tipo_convenio_id: null, etapa_actual_id: 1, plantilla_origen_id: null,
  version_actual: 1, estado: 'EN_TRAMITE', objeto: 'Cooperación académica', alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null,
  fecha_inicio: null, fecha_vencimiento: null, fecha_firma: null,
  duracion_meses: null, porcentaje_avance: null, convenio_origen_id: null, numero_renovacion: null,
  creado_por_id: 1, creado_por: { id: 1, nombre_completo: 'Gestor', correo: 'gestor@example.com' },
  creado_en: '2026-10-20T12:00:00Z', actualizado_en: '2026-10-20T12:00:00Z',
  solicitud: null,
  etapa_actual: { id: 1, orden: 1, codigo: 'ELABORACION', nombre: 'Elaboración' },
  tipo_convenio: null, unidad_organizacional: null, plantilla_origen: null,
  contenido: DOCUMENTO, revision_borrador: 0, borrador_guardado_en: null,
}

const sesion: Sesion = {
  id: 1, correo: 'gestor@example.com', nombre_completo: 'Gestor', activo: true, tipo_usuario: 'INTERNO',
  rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos: ['convenios.ver', 'convenios.editar'],
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function preparar(guardado: () => Response, datos: ElaboracionConvenio = elaboracion) {
  const guardados: Array<Record<string, unknown>> = []
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/convenios/7/elaboracion' && init?.method === 'PATCH') {
      guardados.push(JSON.parse(String(init.body)))
      return guardado()
    }
    if (url === '/api/convenios/7/elaboracion') return respuesta(200, datos)
    if (url === '/api/convenios/catalogos/elaboracion') {
      return respuesta(200, { tipos_convenio: [], unidades_organizacionales: [] })
    }
    if (url.startsWith('/api/aliados')) return respuesta(200, { items: [], total: 0 })
    if (url === '/api/convenios/7/versiones') return respuesta(200, [])
    if (url === '/api/convenios/7/revisiones') return respuesta(200, { revisiones: [], cambios_etapa: [] })
    return respuesta(404, { detail: 'Not Found' })
  })
  vi.stubGlobal('fetch', fetch)
  const notify = vi.fn()
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  cliente.setQueryData(CLAVE_SESION, sesion)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <MemoryRouter initialEntries={['/convenios/7/elaboracion']}>
          <Routes>
            <Route path="/convenios/:convenioId/elaboracion" element={<ConvenioElaboracionPage />} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { guardados, notify, usuario: userEvent.setup() }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HT-13 - guardar avances del convenio', () => {
  it('distingue el borrador guardado del número de versión formal (RN-09)', async () => {
    preparar(() => respuesta(200, elaboracion), {
      ...elaboracion, revision_borrador: 2, borrador_guardado_en: '2026-10-24T15:00:00Z',
    })

    const resumen = await screen.findByRole('heading', { name: 'Proyecto de convenio' })
    const panel = resumen.closest('section') as HTMLElement
    expect(within(panel).getByText('Versión formal')).toBeTruthy()
    expect(within(panel).getByText(/pendiente de enviar a revisión/)).toBeTruthy()
    expect(screen.getByText('Borrador guardado')).toBeTruthy()
  })

  it('guarda el avance con la revisión del borrador sin anunciar una versión nueva (CA-01)', async () => {
    const guardadoServidor = {
      ...elaboracion, contenido: DOCUMENTO_EDITADO, revision_borrador: 1,
      borrador_guardado_en: '2026-10-24T15:00:00Z',
    }
    const { guardados, notify, usuario } = preparar(() => respuesta(200, guardadoServidor))

    expect(await screen.findByText('Sin avances guardados desde la versión formal')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    expect(screen.getByText('Cambios sin guardar')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))

    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toMatchObject({ contenido: DOCUMENTO_EDITADO, expected_revision: 0 })
    expect(guardados[0]).not.toHaveProperty('expected_version')
    await waitFor(() => expect(notify).toHaveBeenCalledWith({
      type: 'success',
      message: 'Avance guardado. La versión formal se crea al enviar el proyecto a revisión jurídica.',
    }))
  })

  it('avisa cuando no había cambios por guardar (CA-07)', async () => {
    const { notify, usuario } = preparar(() => respuesta(200, elaboracion))

    await usuario.click(await screen.findByRole('button', { name: 'Guardar avance' }))

    await waitFor(() => expect(notify).toHaveBeenCalledWith({
      type: 'warning', message: 'No había cambios por guardar.',
    }))
  })

  it('conserva los cambios locales y explica el conflicto cuando otra persona guardó antes (CA-06)', async () => {
    const { notify, usuario } = preparar(() => respuesta(409, {
      detail: { message: 'Otra persona guardó el borrador', expected_revision: 0, current_revision: 1 },
    }))

    await usuario.click(await screen.findByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))

    await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.objectContaining({
      type: 'error',
      message: expect.stringContaining('Otra persona guardó el borrador mientras lo editabas'),
    })))
    expect(screen.getByText('Cambios sin guardar')).toBeTruthy()
    expect(screen.getByTestId('documento').textContent).toContain('Avance nuevo')
  })
})
