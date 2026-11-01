import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConsultaConveniosPage } from './ConsultaConveniosPage'
import { ConvenioDetallePage } from './ConvenioDetallePage'
import { ConvenioElaboracionPage } from './ConvenioElaboracionPage'
import { ConvenioHistorialPage } from './ConvenioHistorialPage'
import { ConvenioVersionPage } from './ConvenioVersionPage'
import { DocumentoAprobadoFirmaPage } from './DocumentoAprobadoFirmaPage'
import { RenovacionesPage } from './RenovacionesPage'
import { RevisionesJuridicasPage } from './RevisionesJuridicasPage'
import { TableroConveniosPage } from './TableroConveniosPage'
import type { ElaboracionConvenio } from './epica02'

// Se prueban las páginas y sus enlaces reales; solo el editor visual y HTTP se simulan.
vi.mock('../components/ConvenioEditor', () => ({ ConvenioEditor: () => <p>Documento de prueba</p> }))

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  Element.prototype.scrollIntoView = vi.fn()
})

const AUTOR = { id: 1, nombre_completo: 'Gestora ORI', correo: 'gestor@example.com' }
const ETAPA = { id: 1, orden: 1, codigo: 'ELABORACION', nombre: 'Elaboración' }
const proyecto: ElaboracionConvenio = {
  id: 41, codigo: null, solicitud_id: null, origen: 'MANUAL_ORI', aliado_id: null, aliado: null,
  tipo_convenio_id: null, etapa_actual_id: 1, plantilla_origen_id: null,
  version_actual: 1, estado: 'EN_TRAMITE', objeto: 'Movilidad académica', alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null,
  fecha_inicio: null, fecha_vencimiento: null, fecha_firma: null,
  duracion_meses: null, porcentaje_avance: null, convenio_origen_id: null, numero_renovacion: null,
  creado_por_id: 1, creado_por: AUTOR,
  creado_en: '2026-10-20T12:00:00Z', actualizado_en: '2026-10-20T12:00:00Z',
  solicitud: null, etapa_actual: ETAPA, tipo_convenio: null, unidad_organizacional: null, plantilla_origen: null,
  contenido: { type: 'doc', content: [] }, revision_borrador: 0, borrador_guardado_en: null,
}
const version = {
  id: 11, numero: 1, autor: AUTOR, etapa: ETAPA, contexto: 'INICIALIZACION',
  creado_en: proyecto.creado_en, plantilla: null, contenido: proyecto.contenido, snapshot_metadata: {},
}
const itemConsulta = {
  id: 41, codigo: null, objeto: proyecto.objeto, estado: 'VIGENTE', etapa: ETAPA,
  tipo_convenio: null, contraparte: { nombre: 'Universidad', tipo: 'UNIVERSIDAD', identificacion: '123', es_aliado_formal: true },
  programa: null, fecha_inicio: null, fecha_vencimiento: null, fecha_formalizacion: null,
}
const sesion: Sesion = {
  id: 1, correo: AUTOR.correo, nombre_completo: AUTOR.nombre_completo, activo: true, tipo_usuario: 'INTERNO',
  rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' },
  permisos: ['convenios.ver', 'convenios.editar', 'convenios.gestionar_renovaciones', 'convenios.gestionar_firmas'],
}

function Ubicacion() {
  const { pathname, search, state } = useLocation()
  return <><output data-testid="ruta">{pathname}{search}</output><output data-testid="estado">{JSON.stringify(state)}</output></>
}

function preparar(entrada: string | { pathname: string; state: unknown }, opciones: {
  historico?: boolean; errorProyecto?: number; firmas?: boolean; errorDocumento?: number
} = {}) {
  let errorProyecto = opciones.errorProyecto
  let renovada = false
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    let status = 200
    let datos: unknown
    if (url === '/api/convenios/41/renovaciones' && init?.method === 'POST') {
      renovada = true
      datos = { convenio_origen_id: 41, convenio_renovacion_id: 42, codigo: null, numero_renovacion: 1, estado: 'EN_TRAMITE', etapa: 'ELABORACION' }
    } else if (url === '/api/convenios/41') datos = proyecto
    else if (url === '/api/convenios/41/elaboracion') {
      status = errorProyecto ?? 200
      datos = status !== 200 ? { detail: 'Traceback: detalle técnico reservado' }
        : opciones.firmas ? { ...proyecto, etapa_actual: { ...ETAPA, codigo: 'APROBACION_FIRMAS' } } : proyecto
    } else if (url === '/api/convenios/41/versiones') datos = [version]
    else if (url === '/api/convenios/41/versiones/1') datos = version
    else if (url === '/api/convenios/41/revisiones') datos = { revisiones: [], cambios_etapa: [] }
    else if (url === '/api/convenios/41/linea-tiempo') datos = []
    else if (url === '/api/convenios/catalogos/elaboracion') datos = { tipos_convenio: [], unidades_organizacionales: [] }
    else if (url === '/api/convenios/catalogos/consulta') datos = { estados: ['VIGENTE'], tipos_contraparte: ['UNIVERSIDAD'], programas: [] }
    else if (url.startsWith('/api/convenios?')) datos = { items: [{ ...itemConsulta, puede_ver_detalle: !opciones.historico }], total: 1 }
    else if (url.startsWith('/api/aliados')) datos = { items: [], total: 0 }
    else if (url === '/api/convenios/tablero') datos = { etapas: [ETAPA], convenios: [{ ...proyecto, responsable: AUTOR, puede_ver_detalle: true }] }
    else if (url === '/api/convenios/renovaciones') datos = [{
      convenio_id: 41, codigo: null, objeto: proyecto.objeto, aliado: null,
      fecha_inicio: null, fecha_vencimiento: null, estado_convenio: 'POR_VENCER',
      estado_seguimiento: renovada ? 'RENOVACION_INICIADA' : 'PENDIENTE_DE_DECISION', tipo_convenio: null,
      convenio_renovacion_id: renovada ? 42 : null, codigo_renovacion: null, numero_renovacion: null, etapa_renovacion: null,
    }]
    else if (url === '/api/convenios/revisiones-juridicas/pendientes') datos = [{
      revision_id: 1, convenio_id: 41, codigo_convenio: null, solicitud_consecutivo: null,
      objeto: proyecto.objeto, tipo_convenio: { id: 1, nombre: 'Marco' }, responsable: AUTOR,
      fecha_recepcion: proyecto.creado_en, instancia_juridica: 1, numero_ronda: 1, version_numero: 1,
    }]
    else if (url === '/api/convenios/41/firmas') datos = { id: 1, estado: 'CONFIGURACION', version_convenio_id: 11, version_numero: 1, firmas: [] }
    else if (url === '/api/convenios/41/firmas/documento-aprobado') {
      status = opciones.errorDocumento ?? 200
      datos = { convenio_id: 41, version_numero: 1, contenido: proyecto.contenido }
    } else { status = 404; datos = { detail: 'No encontrado' } }
    return new Response(JSON.stringify(datos), { status, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, opciones.historico
    ? { ...sesion, rol: { codigo: 'REVISOR_ORI', nombre: 'Revisor ORI' }, permisos: ['convenios.ver'] }
    : sesion)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={vi.fn()}>
        <MemoryRouter initialEntries={[entrada]}>
          <Ubicacion />
          <Routes>
            <Route path="/convenios" element={<ConsultaConveniosPage />} />
            <Route path="/convenios/tablero" element={<TableroConveniosPage />} />
            <Route path="/renovaciones" element={<RenovacionesPage />} />
            <Route path="/revisiones-juridicas" element={<RevisionesJuridicasPage />} />
            <Route path="/convenios/:convenioId" element={<ConvenioDetallePage />} />
            <Route path="/convenios/:convenioId/elaboracion" element={<ConvenioElaboracionPage />} />
            <Route path="/convenios/:convenioId/historial" element={<ConvenioHistorialPage />} />
            <Route path="/convenios/:convenioId/versiones/:numero" element={<ConvenioVersionPage />} />
            <Route path="/convenios/:convenioId/firmas/documento-aprobado" element={<DocumentoAprobadoFirmaPage />} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { usuario: userEvent.setup(), fetch, fallarProyecto: () => {
    errorProyecto = 503
    cliente.removeQueries({ queryKey: ['convenios', 41, 'elaboracion'] })
  } }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

async function comprobarRuta(ruta: string) {
  await waitFor(() => expect(screen.getByTestId('ruta').textContent).toBe(ruta))
}

describe('HT-12: retorno de varios niveles con las páginas reales', () => {
  it('el enlace de renovación recién creada regresa al panel con el filtro actualizado', async () => {
    const { usuario } = preparar('/renovaciones?extra=conservar')
    await usuario.click(await screen.findByRole('button', { name: 'Iniciar renovación' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Iniciar renovación' }))
    const enlace = await screen.findByRole('link', { name: 'Ver renovación creada' })
    const origen = '/renovaciones?extra=conservar&estado=RENOVACION_INICIADA&convenio_id=41'
    await comprobarRuta(origen)
    await usuario.click(enlace)
    await comprobarRuta('/convenios/42')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al panel de renovaciones' }))
    await comprobarRuta(origen)
  })

  it.each([
    ['/renovaciones?estado=PENDIENTE_DE_DECISION&extra=conservar', 'Ver convenio', 'Volver al panel de renovaciones'],
    ['/convenios/tablero', 'Ver detalle', 'Volver al tablero de convenios'],
    ['/revisiones-juridicas?buscar=Movilidad&tipo=Marco&responsable=1&extra=conservar', 'Revisar', 'Volver a revisiones jurídicas'],
  ])('%s → Detalle → Elaboración → Detalle → origen sin ciclos', async (origen, enlace, volverOrigen) => {
    const { usuario } = preparar(origen)
    await usuario.click(await screen.findByRole('link', { name: enlace }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: 'Continuar elaboración' }))
    await comprobarRuta('/convenios/41/elaboracion')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al convenio' }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: volverOrigen }))
    await comprobarRuta(origen)
    expect(screen.queryByRole('link', { name: /^Volver/ })).toBeNull()
    expect(screen.getByTestId('estado').textContent).toBe('null')
    if (origen.startsWith('/revisiones')) {
      expect(screen.getByRole('searchbox')).toHaveProperty('value', 'Movilidad')
      expect(screen.getByLabelText('Tipo convenio')).toHaveProperty('value', 'Marco')
      expect(screen.getByLabelText('Responsable')).toHaveProperty('value', '1')
    }
  })

  it.each([false, true])('Consulta filtrada → %s (historial independiente) → versión → origen', async (historico) => {
    const origen = '/convenios?buscar=movilidad&estado=VIGENTE&pagina=2'
    const { usuario, fetch } = preparar(origen, { historico })
    await usuario.click(await screen.findByRole('link', { name: historico ? 'Ver historial' : 'Ver' }))
    if (!historico) await usuario.click(await screen.findByRole('tab', { name: 'Historial' }))
    const historial = historico ? '/convenios/41/historial' : '/convenios/41?pestana=historial'
    await comprobarRuta(historial)
    await usuario.click(await screen.findByRole('link', { name: 'Ver contenido de la versión 1' }))
    await comprobarRuta('/convenios/41/versiones/1')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al historial del convenio' }))
    await comprobarRuta(historial)
    await usuario.click(await screen.findByRole('link', { name: 'Volver a la consulta de convenios' }))
    await comprobarRuta(origen)
    if (historico) expect(fetch.mock.calls.some(([url]) => /^\/api\/convenios\/41(?:\/elaboracion)?$/.test(url))).toBe(false)
  })

  it('elimina el ciclo al visitar de nuevo Elaboración desde su versión histórica', async () => {
    const { usuario } = preparar('/convenios/tablero')
    await usuario.click(await screen.findByRole('link', { name: 'Ver detalle' }))
    await usuario.click(await screen.findByRole('link', { name: 'Continuar elaboración' }))
    await usuario.click(await screen.findByRole('link', { name: 'Ver contenido de la versión 1' }))
    await usuario.click(await screen.findByRole('link', { name: 'Ir al proyecto de convenio' }))
    await comprobarRuta('/convenios/41/elaboracion')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al convenio' }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al tablero de convenios' }))
    await comprobarRuta('/convenios/tablero')
  })

  it.each([undefined, 409])('Detalle → documento aprobado (%s) → Detalle conserva el origen', async (errorDocumento) => {
    const origen = '/convenios?buscar=movilidad'
    const { usuario } = preparar(origen, { firmas: true, errorDocumento })
    await usuario.click(await screen.findByRole('link', { name: 'Ver' }))
    await usuario.click(await screen.findByRole('link', { name: /Ver documento aprobado/ }))
    await comprobarRuta('/convenios/41/firmas/documento-aprobado')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al convenio' }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: 'Volver a la consulta de convenios' }))
    await comprobarRuta(origen)
  })

  it.each(['/convenios/41/historial', '/convenios/41/versiones/1', '/convenios/41/firmas/documento-aprobado'])('Revisor por URL directa %s vuelve a Consulta', async (ruta) => {
    const { usuario, fetch } = preparar(ruta, { historico: true })
    await usuario.click(await screen.findByRole('link', { name: 'Volver a la consulta de convenios' }))
    await comprobarRuta('/convenios')
    expect(fetch.mock.calls.some(([url]) => url === '/api/convenios/41')).toBe(false)
  })

  it('Elaboración por URL directa → Detalle → Tablero usa alternativos seguros', async () => {
    const { usuario } = preparar('/convenios/41/elaboracion')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al convenio' }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al tablero de convenios' }))
    await comprobarRuta('/convenios/tablero')
  })
})

describe('HT-12 H-02: error HTTP al consultar el proyecto', () => {
  it.each([403, 404, 500])('acceso directo con HTTP %s muestra Volver sin detalles técnicos', async (errorProyecto) => {
    const { usuario } = preparar('/convenios/41/elaboracion', { errorProyecto })
    const encabezado = await screen.findByRole('heading', { name: 'No se pudo consultar el proyecto de convenio' })
    const volver = screen.getByRole('link', { name: 'Volver al convenio' })
    expect(volver.className).toBe('btn accion-volver')
    expect(volver.compareDocumentPosition(encabezado) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText(/Traceback/)).toBeNull()
    await usuario.tab()
    expect(document.activeElement).toBe(volver)
    await usuario.tab({ shift: true })
    await usuario.tab()
    expect(document.activeElement).toBe(volver)
    await usuario.keyboard('{Enter}')
    await comprobarRuta('/convenios/41')
  })

  it('un Revisor sin contexto en un error de Elaboración vuelve a Consulta', async () => {
    const { usuario } = preparar('/convenios/41/elaboracion', { historico: true, errorProyecto: 403 })
    await usuario.click(await screen.findByRole('link', { name: 'Volver a la consulta de convenios' }))
    await comprobarRuta('/convenios')
  })

  it('un error desde Detalle permite volver a Detalle y luego al origen filtrado', async () => {
    const origen = '/renovaciones?estado=PENDIENTE_DE_DECISION'
    const { usuario, fallarProyecto } = preparar(origen)
    await usuario.click(await screen.findByRole('link', { name: 'Ver convenio' }))
    const continuar = await screen.findByRole('link', { name: 'Continuar elaboración' })
    fallarProyecto()
    await usuario.click(continuar)
    await screen.findByRole('heading', { name: 'No se pudo consultar el proyecto de convenio' })
    await usuario.click(screen.getByRole('link', { name: 'Volver al convenio' }))
    await comprobarRuta('/convenios/41')
    await usuario.click(await screen.findByRole('link', { name: 'Volver al panel de renovaciones' }))
    await comprobarRuta(origen)
  })
})
