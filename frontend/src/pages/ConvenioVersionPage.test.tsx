import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { RequierePermiso } from '../auth/RequierePermiso'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConvenioElaboracionPage } from './ConvenioElaboracionPage'
import { ConvenioVersionPage } from './ConvenioVersionPage'
import type { ElaboracionConvenio, VersionConvenioDetalle, VersionConvenioResumen } from './epica02'

vi.mock('../components/ConvenioEditor', () => ({
  ConvenioEditor: ({ contenido, editable }: { contenido: Record<string, unknown>; editable: boolean }) => (
    <output data-testid="documento" data-editable={String(editable)}>{JSON.stringify(contenido)}</output>
  ),
}))

const DOCUMENTO_V1 = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Texto de la versión 1' }] }] }
const BORRADOR = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Borrador en curso' }] }] }
const AUTOR = { id: 1, nombre_completo: 'Gestora ORI', correo: 'gestor@example.com' }
const ETAPA = { id: 1, orden: 1, codigo: 'ELABORACION', nombre: 'Elaboración' }

const resumenV1: VersionConvenioResumen = {
  id: 11, numero: 1, autor: AUTOR, etapa: ETAPA, contexto: 'INICIALIZACION',
  creado_en: '2026-10-20T12:00:00Z', plantilla: { id: 3, codigo: 'BASE', nombre: 'Plantilla base' },
}
const resumenV2: VersionConvenioResumen = {
  ...resumenV1, id: 12, numero: 2, contexto: 'FINALIZACION', creado_en: '2026-10-22T12:00:00Z',
  etapa: { id: 2, orden: 2, codigo: 'REVISION_JURIDICA', nombre: 'Revisión jurídica' },
}
const versionV1: VersionConvenioDetalle = {
  ...resumenV1,
  contenido: DOCUMENTO_V1,
  snapshot_metadata: { objeto: 'Objeto congelado', duracion_meses: 24, fecha_inicio: '2026-01-01', unidad_organizacional_id: null },
}
// Versión creada por un guardado antes de HT-13: sin plantilla ni datos congelados.
const versionLegado: VersionConvenioDetalle = {
  ...resumenV1, id: 9, numero: 3, contexto: 'GUARDADO', plantilla: null,
  contenido: DOCUMENTO_V1, snapshot_metadata: {},
}

const elaboracion: ElaboracionConvenio = {
  id: 7, codigo: null, solicitud_id: null, origen: 'MANUAL_ORI', aliado_id: null, aliado: null,
  tipo_convenio_id: null, etapa_actual_id: 1, plantilla_origen_id: null,
  version_actual: 2, estado: 'EN_TRAMITE', objeto: 'Cooperación académica', alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null,
  fecha_inicio: null, fecha_vencimiento: null, fecha_firma: null,
  duracion_meses: null, porcentaje_avance: null, convenio_origen_id: null, numero_renovacion: null,
  creado_por_id: 1, creado_por: AUTOR,
  creado_en: '2026-10-20T12:00:00Z', actualizado_en: '2026-10-20T12:00:00Z',
  solicitud: null, etapa_actual: ETAPA,
  tipo_convenio: null, unidad_organizacional: null, plantilla_origen: null,
  contenido: BORRADOR, revision_borrador: 3, borrador_guardado_en: '2026-10-24T15:00:00Z',
}

function sesion(permisos: string[]): Sesion {
  return {
    id: 1, correo: 'gestor@example.com', nombre_completo: 'Gestora ORI', activo: true, tipo_usuario: 'INTERNO',
    rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos,
  } as Sesion
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function preparar(ruta: string, opciones: { permisos?: string[]; detalle?: Response } = {}) {
  const peticiones: Array<{ url: string; metodo: string }> = []
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    // La sesión se valida aparte; solo interesan las peticiones de convenios.
    if (url.startsWith('/api/convenios')) peticiones.push({ url, metodo: init?.method ?? 'GET' })
    if (init?.method && init.method !== 'GET') return respuesta(500, { detail: 'No esperado' })
    if (url === '/api/convenios/7/versiones/1') return opciones.detalle ?? respuesta(200, versionV1)
    if (url === '/api/convenios/7/versiones/3') return respuesta(200, versionLegado)
    if (url.startsWith('/api/convenios/7/versiones/')) return respuesta(404, { detail: 'Versión de convenio no encontrada' })
    if (url === '/api/convenios/7/versiones') return respuesta(200, [resumenV2, resumenV1])
    if (url === '/api/convenios/7/elaboracion') return respuesta(200, elaboracion)
    if (url === '/api/convenios/7/revisiones') return respuesta(200, { revisiones: [], cambios_etapa: [] })
    if (url === '/api/convenios/catalogos/elaboracion') {
      return respuesta(200, { tipos_convenio: [], unidades_organizacionales: [] })
    }
    if (url.startsWith('/api/aliados')) return respuesta(200, { items: [], total: 0 })
    return respuesta(404, { detail: 'Not Found' })
  })
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  cliente.setQueryData(CLAVE_SESION, sesion(opciones.permisos ?? ['convenios.ver', 'convenios.editar']))
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={vi.fn()}>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route element={<RequierePermiso permiso="convenios.ver" />}>
              <Route path="/convenios/:convenioId/elaboracion" element={<ConvenioElaboracionPage />} />
              <Route path="/convenios/:convenioId/versiones/:numero" element={<ConvenioVersionPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { cliente, peticiones, usuario: userEvent.setup() }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HT-05 - consultar versiones anteriores del convenio', () => {
  it('abre una versión desde el historial sin modificar el borrador (CA-01, CA-06)', async () => {
    const { peticiones, usuario } = preparar('/convenios/7/elaboracion')

    const historial = (await screen.findByRole('heading', { name: 'Historial de versiones' })).closest('section') as HTMLElement
    expect(within(historial).getByText(/guardar avances no agrega versiones/)).toBeTruthy()
    const enlaces = await within(historial).findAllByRole('link', { name: /Ver contenido de la versión/ })
    expect(enlaces.map((enlace) => enlace.getAttribute('href'))).toEqual([
      '/convenios/7/versiones/2', '/convenios/7/versiones/1',
    ])

    await usuario.click(within(historial).getByRole('link', { name: 'Ver contenido de la versión 1' }))

    expect(await screen.findByRole('heading', { name: 'Versión 1 del convenio' })).toBeTruthy()
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_V1))
    expect(screen.queryByText(/Borrador en curso/)).toBeNull()
    // Solo lecturas: abrir la versión no guarda, no finaliza ni envía nada.
    expect(peticiones.every((peticion) => peticion.metodo === 'GET')).toBe(true)
    expect(peticiones.filter((peticion) => peticion.url === '/api/convenios/7/versiones/1')).toHaveLength(1)
  })

  it('muestra el contenido y los metadatos del snapshot en solo lectura (CA-02, CA-03, CA-04)', async () => {
    const { peticiones } = preparar('/convenios/7/versiones/1')

    expect(await screen.findByRole('heading', { name: 'Versión 1 del convenio' })).toBeTruthy()
    const documento = screen.getByTestId('documento')
    expect(documento.textContent).toBe(JSON.stringify(DOCUMENTO_V1))
    expect(documento.dataset.editable).toBe('false')
    expect(screen.getAllByText(/Solo lectura/).length).toBeGreaterThan(0)

    const datos = (screen.getByRole('heading', { name: 'Datos de la versión' }).closest('section')) as HTMLElement
    const valor = (etiqueta: string) => within(datos).getByText(etiqueta).nextElementSibling?.textContent
    expect(valor('Número de versión')).toBe('1')
    expect(valor('Autor')).toBe('Gestora ORI')
    expect(valor('Fecha')).toBe(new Date(versionV1.creado_en).toLocaleString())
    expect(valor('Etapa')).toBe('Elaboración')
    expect(valor('Contexto de generación')).toBe('Creación del proyecto')
    expect(valor('Plantilla utilizada')).toBe('Plantilla base')

    const snapshot = (screen.getByRole('heading', { name: 'Datos del convenio en esta versión' }).closest('section')) as HTMLElement
    const campo = (etiqueta: string) => within(snapshot).getByText(etiqueta).nextElementSibling?.textContent
    expect(campo('Objeto')).toBe('Objeto congelado')
    expect(campo('Duración (meses)')).toBe('24')
    expect(campo('Fecha de inicio')).toBe('2026-01-01')
    expect(campo('Unidad / programa (ID)')).toBe('—')

    expect(screen.queryByRole('button', { name: /Guardar|Finalizar|Restaurar|Editar/ })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(peticiones).toEqual([{ url: '/api/convenios/7/versiones/1', metodo: 'GET' }])
  })

  it('consulta versiones previas a HT-13 sin plantilla ni datos congelados (CA-08)', async () => {
    preparar('/convenios/7/versiones/3')

    expect(await screen.findByRole('heading', { name: 'Versión 3 del convenio' })).toBeTruthy()
    expect(screen.getByText('Avance guardado')).toBeTruthy()
    expect(screen.getByText('Sin plantilla asociada')).toBeTruthy()
    expect(screen.getByText('Esta versión no registró datos del convenio.')).toBeTruthy()
  })

  it('informa de forma controlada cuando la versión no existe (CA-07)', async () => {
    preparar('/convenios/7/versiones/99')

    expect(await screen.findByRole('heading', { name: 'Versión no encontrada' })).toBeTruthy()
    expect(screen.queryByTestId('documento')).toBeNull()
    expect(screen.getByRole('link', { name: 'Volver al historial del convenio' }).getAttribute('href'))
      .toBe('/convenios/7?pestana=historial')
  })

  it.each(['abc', '1.5', '0', '-1', 'NaN', 'Infinity'])('no consulta el servidor si convenioId es %s (CA-07)', async (convenioId) => {
    const { peticiones } = preparar(`/convenios/${convenioId}/versiones/1`)

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Versión no encontrada' })).toBeTruthy()
    expect(screen.queryByText('Cargando versión…')).toBeNull()
    expect(screen.queryByTestId('documento')).toBeNull()
    expect(peticiones).toEqual([])
  })

  it.each(['abc', '1.5', '0', '-1', 'NaN', 'Infinity'])('no consulta el servidor si el número de versión es %s (CA-07)', async (numero) => {
    const { peticiones } = preparar(`/convenios/7/versiones/${numero}`)

    expect(await screen.findByRole('heading', { name: 'Versión no encontrada' })).toBeTruthy()
    expect(screen.queryByText('Cargando versión…')).toBeNull()
    expect(screen.queryByTestId('documento')).toBeNull()
    expect(peticiones).toEqual([])
  })

  it('muestra el error del servidor sin exponer contenido (CA-07)', async () => {
    preparar('/convenios/7/versiones/1', { detalle: respuesta(503, { detail: 'Servicio no disponible' }) })

    expect(await screen.findByRole('heading', { name: 'No se pudo consultar la versión' })).toBeTruthy()
    expect(screen.getByText('Servicio no disponible')).toBeTruthy()
    expect(screen.queryByTestId('documento')).toBeNull()
  })

  it('niega el acceso por URL a quien no puede ver convenios (CA-07)', async () => {
    const { peticiones } = preparar('/convenios/7/versiones/1', { permisos: ['solicitudes.ver_propias'] })

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.queryByTestId('documento')).toBeNull()
    await waitFor(() => expect(peticiones.some((peticion) => peticion.url.includes('/versiones'))).toBe(false))
  })
})
