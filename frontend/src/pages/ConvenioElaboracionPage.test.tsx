import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { ConvenioElaboracionPage } from './ConvenioElaboracionPage'
import type { ElaboracionConvenio } from './epica02'
import ejemploBase from './fixtures/hu12_base_solicitud.json'

vi.mock('../components/ConvenioEditor', () => ({
  ConvenioEditor: ({ contenido, onChange, editable }: {
    contenido: Record<string, unknown>
    editable: boolean
    onChange: (nuevo: Record<string, unknown>) => void
  }) => (
    <div>
      <output data-testid={editable ? 'documento' : 'copia-documento'}>{JSON.stringify(contenido)}</output>
      {editable && <button type="button" onClick={() => onChange(DOCUMENTO_EDITADO)}>Editar documento</button>}
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

const DOCUMENTO_REMOTO = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Documento de B' }] }] }
const METADATOS_INICIALES = {
  aliado_id: null, tipo_convenio_id: null, objeto: elaboracion.objeto, alcance: null,
  unidad_organizacional_id: null, implicacion_financiera: null, duracion_meses: null,
  fecha_inicio: null, fecha_vencimiento: null,
}
const METADATOS_REMOTOS = {
  aliado_id: 6, tipo_convenio_id: 3, objeto: 'Objeto guardado por B', alcance: 'PROGRAMA' as const,
  unidad_organizacional_id: 5, implicacion_financiera: 'Aporte de B', duracion_meses: 12,
  fecha_inicio: '2099-01-01', fecha_vencimiento: '2099-12-31',
}
const remotoCompleto: ElaboracionConvenio = {
  ...elaboracion, ...METADATOS_REMOTOS, contenido: DOCUMENTO_REMOTO,
  revision_borrador: 1, borrador_guardado_en: '2026-10-24T15:00:00Z',
}

function comprobarMetadatos(valores: Record<string, string | number | null>, incluirAliado = true) {
  const etiquetas = {
    aliado_id: /Aliado \/ contraparte/, tipo_convenio_id: 'Tipo de convenio', objeto: 'Objeto',
    alcance: 'Alcance', unidad_organizacional_id: 'Unidad / programa',
    implicacion_financiera: 'Implicación financiera', duracion_meses: 'Duración (meses)',
    fecha_inicio: 'Fecha de inicio', fecha_vencimiento: 'Fecha de vencimiento',
  }
  for (const [campo, etiqueta] of Object.entries(etiquetas)) {
    if (campo === 'aliado_id' && !incluirAliado) continue
    expect((screen.getByLabelText(etiqueta) as HTMLInputElement).value, campo).toBe(String(valores[campo] ?? ''))
  }
}

const sesion: Sesion = {
  id: 1, correo: 'gestor@example.com', nombre_completo: 'Gestor', activo: true, tipo_usuario: 'INTERNO',
  rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos: ['convenios.ver', 'convenios.editar'],
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function preparar(
  guardado: () => Response | Promise<Response>,
  inicial: ElaboracionConvenio = elaboracion,
  revisiones: unknown = { revisiones: [], cambios_etapa: [] },
) {
  let datos = inicial
  let falloLectura = false
  const guardados: Array<Record<string, unknown>> = []
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/convenios/7/elaboracion' && init?.method === 'PATCH') {
      guardados.push(JSON.parse(String(init.body)))
      const resultado = await guardado()
      if (resultado.ok) datos = await resultado.clone().json()
      return resultado
    }
    if (url === '/api/convenios/7/elaboracion') {
      return falloLectura ? respuesta(503, { detail: 'Servicio no disponible' }) : respuesta(200, datos)
    }
    if (url === '/api/convenios/catalogos/elaboracion') {
      return respuesta(200, {
        tipos_convenio: [{ id: 2, nombre: 'Marco' }, { id: 3, nombre: 'Específico' }],
        unidades_organizacionales: [{ id: 4, nombre: 'Derecho' }, { id: 5, nombre: 'Ingeniería' }],
      })
    }
    if (url.startsWith('/api/aliados')) {
      return respuesta(200, { items: [{ id: 6, nombre: 'Universidad B' }], total: 1 })
    }
    if (url === '/api/convenios/7/versiones') return respuesta(200, [])
    if (url === '/api/convenios/7/revisiones') return respuesta(200, revisiones)
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
  return {
    cliente, guardados, notify, usuario: userEvent.setup(),
    actualizarServidor: (nuevo: ElaboracionConvenio) => { datos = nuevo },
    fallarLectura: () => { falloLectura = true },
  }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('finalización y consulta de etapas posteriores', () => {
  it.each(['REVISION_AVAL_JURIDICO', 'REVISION_CONTRAPARTE', 'REVISION_FINAL', 'APROBACION_FIRMAS', 'FIRMA_ARCHIVO_SEGUIMIENTO'])('muestra solo consulta en %s', async (codigo) => {
    preparar(() => respuesta(200, elaboracion), {
      ...elaboracion, etapa_actual: { id: 2, orden: 2, codigo, nombre: codigo },
    })
    expect(await screen.findByText(/Documento de solo lectura/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Continuar trámite' }).getAttribute('href')).toBe('/convenios/7')
    expect(screen.queryByText(/Edita libremente/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Editar documento|Guardar avance|Finalizar elaboración/ })).toBeNull()
    expect((screen.getByRole('textbox', { name: 'Objeto' }) as HTMLTextAreaElement).disabled).toBe(true)
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Consulta · Convenio provisional #7')
  })

  it.each([false, true])('actualiza el estado tras finalizar y conserva conflictos reales (409: %s)', async (conflicto) => {
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
    HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
    const { usuario, actualizarServidor, notify, cliente } = preparar(() => respuesta(200, remotoCompleto), remotoCompleto)
    cliente.setQueryData(['solicitudes', 'recibidas'], { items: [] })
    cliente.setQueryData(['convenio', 7], elaboracion)
    const original = globalThis.fetch
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/elaboracion/finalizar')) {
        if (conflicto) return Promise.resolve(respuesta(409, { detail: { expected_revision: 1, current_revision: 2 } }))
        const finalizado = { ...remotoCompleto, contenido: DOCUMENTO_EDITADO,
          version_actual: 2, revision_borrador: 0, borrador_guardado_en: null,
          etapa_actual: { id: 2, orden: 2, codigo: 'REVISION_AVAL_JURIDICO', nombre: 'Revisión jurídica' },
        }
        actualizarServidor(finalizado)
        return Promise.resolve(respuesta(200, finalizado))
      }
      return original(url, init)
    }))
    await usuario.click(await screen.findByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Finalizar elaboración' }))
    expect(screen.queryByRole('button', { name: 'Editar documento' })).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Confirmar y enviar a Jurídica' }))
    if (conflicto) {
      expect(await screen.findByRole('button', { name: 'Cargar el borrador más reciente' })).toBeTruthy()
      expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_EDITADO))
      comprobarMetadatos(METADATOS_REMOTOS)
      expect(notify).not.toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }))
    } else {
      await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' })))
      expect(screen.queryByRole('alert')).toBeNull()
      expect(screen.queryByText('Cambios sin guardar')).toBeNull()
      expect(screen.queryByText('Borrador guardado')).toBeNull()
      expect(screen.queryByText(/Edita libremente/)).toBeNull()
      expect(screen.getByTestId('copia-documento').textContent).toBe(JSON.stringify(DOCUMENTO_EDITADO))
      expect(screen.getByRole('link', { name: 'Continuar trámite' })).toBeTruthy()
      expect(cliente.getQueryState(['solicitudes', 'recibidas'])?.isInvalidated).toBe(true)
      expect(cliente.getQueryState(['convenio', 7])?.isInvalidated).toBe(true)
    }
  })
})

describe('recuperación explícita de antecedentes antiguos', () => {
  it('permite redactar y finalizar después del reemplazo explícito', async () => {
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
    HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
    const inicial = { ...remotoCompleto, contiene_antecedentes_iniciales: true }
    const { usuario, notify } = preparar(() => respuesta(200, inicial), inicial)
    const original = globalThis.fetch
    const enviados: unknown[] = []
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/elaboracion/finalizar')) {
        enviados.push(JSON.parse(String(init?.body)))
        return Promise.resolve(respuesta(200, inicial))
      }
      return original(url, init)
    }))
    await usuario.click(await screen.findByRole('button', { name: 'Empezar documento contractual limpio' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar reemplazo del documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Finalizar elaboración' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar y enviar a Jurídica' }))
    await waitFor(() => expect(notify).toHaveBeenCalledWith({ type: 'success', message: 'Elaboración finalizada. El convenio quedó en revisión jurídica.' }))
    expect(enviados).toEqual([expect.objectContaining({ contenido: DOCUMENTO_EDITADO, expected_revision: 1 })])
    expect(screen.getByTestId('copia-documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
  })

  it.each([false, true])('conserva copia y revisión al reemplazar (conflicto: %s)', async (conflicto) => {
    const inicial = { ...remotoCompleto, contiene_antecedentes_iniciales: true }
    const vacio = { type: 'doc', content: [{ type: 'paragraph' }] }
    const { usuario, guardados } = preparar(() => conflicto
      ? respuesta(409, { detail: { expected_revision: 1, current_revision: 2 } })
      : respuesta(200, { ...inicial, contenido: vacio, revision_borrador: 2, contiene_antecedentes_iniciales: false }), inicial)
    const empezar = await screen.findByRole('button', { name: 'Empezar documento contractual limpio' })
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
    expect(guardados).toHaveLength(0)
    await usuario.click(empezar)
    await usuario.click(screen.getByRole('button', { name: 'Conservar documento actual' }))
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
    await usuario.click(empezar)
    expect(screen.getByText(/Se reemplazará todo el contenido editable actual/)).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Confirmar reemplazo del documento' }))
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(vacio))
    expect(screen.getByTestId('copia-documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
    expect(guardados).toHaveLength(0)
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toMatchObject({ contenido: vacio, expected_revision: 1 })
    if (conflicto) {
      expect(await screen.findByRole('button', { name: 'Cargar el borrador más reciente' })).toBeTruthy()
      expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(vacio))
    } else {
      await screen.findByText('Borrador guardado')
    }
    expect(screen.getByTestId('copia-documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
  })
})

describe('HT-15, Tarea 7 - marca "obliga a corregir" en el editor', () => {
  it('muestra si cada observación jurídica pendiente obliga o no a corregir', async () => {
    preparar(() => respuesta(200, elaboracion), elaboracion, {
      revisiones: [{
        id: 10, tipo: 'JURIDICA', instancia_juridica: 1, numero_ronda: 1,
        estado: 'RESUELTA', resultado: 'DEVUELTA',
        version_convenio_id: null, version_resultado_id: null, version_convenio: null,
        version_resultado: null, snapshot_datos: null, creada_por: elaboracion.creado_por,
        resuelta_por: elaboracion.creado_por, creado_en: '2026-10-20T12:00:00Z',
        resuelta_en: '2026-10-20T13:00:00Z',
        observaciones: [
          {
            id: 200, origen: 'REVISOR_ORI', descripcion: 'Falta la cláusula de vigencia',
            requiere_correccion: true, respuesta: null, estado: 'PENDIENTE',
            registrada_por: elaboracion.creado_por, responsable: null, atendida_por: null,
            fecha_atencion: null, creado_en: '2026-10-20T12:00:00Z',
          },
          {
            id: 201, origen: 'REVISOR_ORI', descripcion: 'Sugerencia de redacción',
            requiere_correccion: false, respuesta: null, estado: 'PENDIENTE',
            registrada_por: elaboracion.creado_por, responsable: null, atendida_por: null,
            fecha_atencion: null, creado_en: '2026-10-20T12:05:00Z',
          },
        ],
        invitaciones_contraparte: [], respuesta_contraparte: null,
      }],
      cambios_etapa: [],
    })

    const seccion = (await screen.findByRole('heading', { name: 'Observaciones jurídicas pendientes' })).closest('section') as HTMLElement
    const obligatoria = within(seccion).getByText('Falta la cláusula de vigencia').closest('article') as HTMLElement
    const informativa = within(seccion).getByText('Sugerencia de redacción').closest('article') as HTMLElement
    expect(within(obligatoria).getByText('Obliga a corregir')).toBeTruthy()
    expect(within(informativa).getByText('No obliga a corregir')).toBeTruthy()
  })
})

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

  it('indica que aún no hay versión formal en un convenio nuevo (HT-15)', async () => {
    preparar(() => respuesta(200, elaboracion), {
      ...elaboracion, version_actual: 0, revision_borrador: 1, borrador_guardado_en: '2026-10-24T15:00:00Z',
    })

    expect(await screen.findByText(/Sin versión formal/)).toBeTruthy()
    expect(screen.queryByText(/Versión formal 0/)).toBeNull()
    expect(await screen.findByText(/La primera se crea al enviar el proyecto a revisión jurídica/)).toBeTruthy()
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

  it('conserva lo escrito cuando otra persona guarda mientras se edita y guarda contra la revisión de partida', async () => {
    const { cliente, guardados, usuario } = preparar(() => respuesta(409, {
      detail: { message: 'Otra persona guardó el borrador', expected_revision: 0, current_revision: 1 },
    }))

    await usuario.click(await screen.findByRole('button', { name: 'Editar documento' }))
    cliente.setQueryData(['convenios', 7, 'elaboracion'], {
      ...elaboracion, revision_borrador: 1, borrador_guardado_en: '2026-10-24T15:00:00Z',
      contenido: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'De otra persona' }] }] },
    })

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByTestId('documento').textContent).toContain('Avance nuevo')
    expect(screen.getByText('Cambios sin guardar')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toMatchObject({ expected_revision: 0, contenido: DOCUMENTO_EDITADO })
  })

  it('descarta lo escrito solo cuando se pide cargar el borrador más reciente', async () => {
    const { usuario } = preparar(() => respuesta(409, {
      detail: { message: 'Otra persona guardó el borrador', expected_revision: 0, current_revision: 1 },
    }))

    await usuario.click(await screen.findByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await usuario.click(await screen.findByRole('button', { name: 'Cargar el borrador más reciente' }))

    await waitFor(() => expect(screen.getByTestId('documento').textContent).toContain('Versión 1'))
    expect(screen.queryByText('Cambios sin guardar')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cargar el borrador más reciente' })).toBeNull()
  })

  it('recupera documento y todos los metadatos tras 409 y reenvía exactamente lo recuperado', async () => {
    const remoto = {
      ...elaboracion, revision_borrador: 1, contenido: DOCUMENTO_REMOTO,
      borrador_guardado_en: '2026-10-24T15:00:00Z', ...METADATOS_REMOTOS,
    }
    let intento = 0
    const { usuario, guardados, actualizarServidor, notify } = preparar(() => ++intento === 1
      ? respuesta(409, { detail: { expected_revision: 0, current_revision: 1 } })
      : respuesta(200, remoto))

    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    await usuario.clear(objeto)
    await usuario.type(objeto, 'Cambios locales de A')
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    actualizarServidor(remoto) // B guardó desde la misma revisión que abrió A.
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))

    const cargar = await screen.findByRole('button', { name: 'Cargar el borrador más reciente' })
    expect((objeto as HTMLTextAreaElement).value).toBe('Cambios locales de A')
    expect(screen.getByTestId('documento').textContent).toContain('Avance nuevo')
    await usuario.click(cargar)

    await waitFor(() => expect(screen.getByTestId('documento').textContent).toContain('Documento de B'))
    comprobarMetadatos(METADATOS_REMOTOS)
    expect(screen.queryByText('Cambios sin guardar')).toBeNull()
    expect(screen.getByText('Borrador guardado')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(2))
    expect(guardados[1]).toEqual({ ...METADATOS_REMOTOS, contenido: DOCUMENTO_REMOTO, expected_revision: 1 })
    await waitFor(() => expect(notify).toHaveBeenCalledWith({
      type: 'warning', message: 'No había cambios por guardar.',
    }))
  })

  it('distingue documento, metadatos, ambos y sincronización al editar y deshacer', async () => {
    const { usuario } = preparar(() => respuesta(200, elaboracion), {
      ...elaboracion, revision_borrador: 2, borrador_guardado_en: '2026-10-24T15:00:00Z',
    })
    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    expect(screen.getByText('Borrador guardado')).toBeTruthy()
    await usuario.type(objeto, ' ampliada')
    expect(screen.getByText(/Metadatos modificados/)).toBeTruthy()
    expect(screen.queryByText('Borrador guardado')).toBeNull()
    await usuario.clear(objeto)
    await usuario.type(objeto, elaboracion.objeto!)
    expect(screen.queryByText('Cambios sin guardar')).toBeNull()
    expect(screen.getByText('Borrador guardado')).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    expect(screen.getByText(/Documento modificado/)).toBeTruthy()
    await usuario.type(objeto, ' ampliada')
    expect(screen.getByText(/Documento y metadatos modificados/)).toBeTruthy()
    expect(screen.queryByText('Borrador guardado')).toBeNull()
  })

  it('guarda solo metadatos y establece una base limpia para guardar de nuevo', async () => {
    const remoto = {
      ...elaboracion, objeto: 'Objeto corregido', revision_borrador: 1,
      borrador_guardado_en: '2026-10-24T15:00:00Z',
    }
    const { usuario, guardados } = preparar(() => respuesta(200, remoto))
    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    await usuario.clear(objeto)
    await usuario.type(objeto, remoto.objeto)
    expect(screen.getByText(/Metadatos modificados/)).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await screen.findByText('Borrador guardado')
    expect(guardados[0]).toMatchObject({ objeto: remoto.objeto, contenido: DOCUMENTO, expected_revision: 0 })
    expect(screen.queryByText('Cambios sin guardar')).toBeNull()
    expect((objeto as HTMLTextAreaElement).value).toBe(remoto.objeto)
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(2))
    expect(guardados[1]).toMatchObject({ objeto: remoto.objeto, contenido: DOCUMENTO, expected_revision: 1 })
  })

  it('sincroniza una pantalla sin cambios durante un refetch, incluidos todos los metadatos', async () => {
    const { cliente, actualizarServidor, usuario, guardados } = preparar(() => respuesta(200, remotoCompleto))
    await screen.findByRole('textbox', { name: 'Objeto' })
    actualizarServidor(remotoCompleto)
    await act(async () => { await cliente.refetchQueries({ queryKey: ['convenios', 7, 'elaboracion'] }) })

    await waitFor(() => comprobarMetadatos(METADATOS_REMOTOS))
    expect(screen.getByTestId('documento').textContent).toContain('Documento de B')
    expect(screen.queryByText('Cambios sin guardar')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toEqual({ ...METADATOS_REMOTOS, contenido: DOCUMENTO_REMOTO, expected_revision: 1 })
  })

  it.each([false, true])('protege metadatos locales y revisión ante refetch (documento editado: %s)', async (editarDocumento) => {
    const { cliente, actualizarServidor, usuario, guardados } = preparar(() => respuesta(409, {
      detail: { expected_revision: 0, current_revision: 1 },
    }))
    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    await usuario.type(objeto, ' de A')
    if (editarDocumento) await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    actualizarServidor(remotoCompleto)
    await act(async () => { await cliente.refetchQueries({ queryKey: ['convenios', 7, 'elaboracion'] }) })

    expect((objeto as HTMLTextAreaElement).value).toBe(`${elaboracion.objeto} de A`)
    comprobarMetadatos({ ...METADATOS_INICIALES, objeto: `${elaboracion.objeto} de A` })
    expect(screen.getByTestId('documento').textContent).toContain(editarDocumento ? 'Avance nuevo' : 'Versión 1')
    expect(screen.getByText('Cambios sin guardar')).toBeTruthy()
    expect(screen.queryByText('Borrador guardado')).toBeNull()
    expect((await screen.findByRole('alert')).textContent).toContain('se reemplazarán el documento y todos los metadatos')
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toEqual({
      ...METADATOS_INICIALES, objeto: `${elaboracion.objeto} de A`, expected_revision: 0,
      contenido: editarDocumento ? DOCUMENTO_EDITADO : DOCUMENTO,
    })
  })

  it('conserva documento y metadatos si falla la carga explícita y permite reintentar', async () => {
    const { usuario, fallarLectura, notify } = preparar(() => respuesta(409, {
      detail: { expected_revision: 0, current_revision: 1 },
    }))
    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    await usuario.type(objeto, ' de A')
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    fallarLectura()
    await usuario.click(await screen.findByRole('button', { name: 'Cargar el borrador más reciente' }))

    await waitFor(() => expect(notify).toHaveBeenCalledWith({
      type: 'error', message: 'No fue posible cargar el borrador más reciente. Tus cambios siguen en pantalla.',
    }))
    expect((objeto as HTMLTextAreaElement).value).toBe(`${elaboracion.objeto} de A`)
    expect(screen.getByTestId('documento').textContent).toContain('Avance nuevo')
    expect(screen.getByText('Cambios sin guardar')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Cargar el borrador más reciente' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it.each([' y posterior', ' '])('conserva las ediciones posteriores al envío cuando termina el guardado y usa la nueva revisión (%j)', async (posterior) => {
    let completar!: (respuesta: Response) => void
    const pendiente = new Promise<Response>((resolve) => { completar = resolve })
    const { usuario, guardados } = preparar(() => pendiente)
    const objeto = await screen.findByRole('textbox', { name: 'Objeto' })
    await usuario.type(objeto, ' enviado')
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    await usuario.type(objeto, posterior)
    await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    await act(async () => completar(respuesta(200, {
      ...elaboracion, objeto: `${elaboracion.objeto} enviado`, revision_borrador: 1,
      borrador_guardado_en: '2026-10-24T15:00:00Z',
    })))

    await waitFor(() => expect((screen.getByRole('button', { name: 'Guardar avance' }) as HTMLButtonElement).disabled).toBe(false))
    expect((objeto as HTMLTextAreaElement).value).toBe(`${elaboracion.objeto} enviado${posterior}`)
    expect(screen.getByTestId('documento').textContent).toContain('Avance nuevo')
    expect(screen.getByText(/Documento y metadatos modificados/)).toBeTruthy()
    expect(screen.queryByText('Borrador guardado')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(2))
    expect(guardados[1]).toMatchObject({
      objeto: `${elaboracion.objeto} enviado${posterior}`.trim(), contenido: DOCUMENTO_EDITADO, expected_revision: 1,
    })
  })
})


it.each(['input', 'change'] as const)('HT17: %s sincroniza fechas al guardar y finalizar en ambos ordenes', async (evento) => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  for (const fechaPrimero of [true, false]) {
    const persistido = { ...elaboracion, fecha_inicio: '2099-10-31', duracion_meses: 4, fecha_vencimiento: '2100-02-28', revision_borrador: 1 }
    const { usuario, guardados, cliente } = preparar(() => respuesta(200, persistido))
    const original = globalThis.fetch
    const finales: Record<string, unknown>[] = []
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/elaboracion/finalizar')) {
        finales.push(JSON.parse(String(init?.body)))
        return Promise.resolve(respuesta(422, { detail: { message: 'Proyecto incompleto', faltantes: [{ campo: 'objeto', motivo: 'Otro dato pendiente' }] } }))
      }
      return original(url, init)
    }))
    const inicio = await screen.findByLabelText('Fecha de inicio') as HTMLInputElement
    const cambiarFecha = () => fireEvent[evento](inicio, { target: { value: '2099-10-31' } })
    const cambiarDuracion = () => fireEvent.change(screen.getByLabelText('Duración (meses)'), { target: { value: '4' } })
    if (fechaPrimero) { cambiarFecha(); cambiarDuracion() } else { cambiarDuracion(); cambiarFecha() }
    const fechas = { fecha_inicio: '2099-10-31', duracion_meses: 4, fecha_vencimiento: '2100-02-28' }
    expect(inicio.value).toBe(fechas.fecha_inicio)
    expect((screen.getByLabelText('Fecha de vencimiento') as HTMLInputElement).value).toBe(fechas.fecha_vencimiento)
    // Primer intento inmediato, sin corregir la fecha ni desenfocar el campo.
    fireEvent.click(screen.getByRole('button', { name: 'Finalizar elaboración' }))
    await usuario.click(screen.getByRole('button', { name: 'Confirmar y enviar a Jurídica' }))
    await waitFor(() => expect(finales).toHaveLength(1))
    expect(finales[0]).toMatchObject(fechas)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await waitFor(() => expect(guardados).toHaveLength(1))
    expect(guardados[0]).toMatchObject(fechas)
    await waitFor(() => expect(cliente.getQueryData<ElaboracionConvenio>(['convenios', 7, 'elaboracion'])?.revision_borrador).toBe(1))
    cleanup()
    // Nueva consulta/montaje desde la respuesta persistida, sin estado local previo.
    preparar(() => respuesta(200, persistido), persistido)
    expect((await screen.findByLabelText('Fecha de inicio') as HTMLInputElement).value).toBe(fechas.fecha_inicio)
    expect((screen.getByLabelText('Fecha de vencimiento') as HTMLInputElement).value).toBe(fechas.fecha_vencimiento)
    cleanup()
  }
})

it('HT17 conserva el vencimiento historico al abrir y calcula solo al editar', async () => {
  const historico = { ...elaboracion, fecha_inicio: '2099-01-01', duracion_meses: 12, fecha_vencimiento: '2100-01-01' }
  const { usuario, guardados } = preparar(() => respuesta(200, historico), historico)
  const vencimiento = await screen.findByLabelText('Fecha de vencimiento') as HTMLInputElement
  expect(vencimiento.readOnly).toBe(true)
  expect(vencimiento.value).toBe('2100-01-01')
  await usuario.type(screen.getByRole('textbox', { name: 'Objeto' }), ' ajustado')
  await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
  await waitFor(() => expect(guardados).toHaveLength(1))
  expect(guardados[0].fecha_vencimiento).toBe('2100-01-01')
  const inicio = screen.getByLabelText('Fecha de inicio')
  fireEvent.change(inicio, { target: { value: '2099-01-31' } })
  expect(vencimiento.value).toBe('2100-01-31')
})


it.each([false, true])('muestra el rechazo de documento vacío y conserva otros errores (otros campos: %s)', async (otrosCampos) => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  const { usuario, guardados, notify } = preparar(() => respuesta(200, remotoCompleto), remotoCompleto)
  const peticionOriginal = globalThis.fetch
  const motivo = 'El documento no puede estar vacío'
  const faltantes = [
    { campo: 'contenido', motivo },
    ...(otrosCampos ? [
      { campo: 'objeto', motivo: 'Es obligatorio para finalizar la elaboración' },
      { campo: 'unidad_organizacional_id', motivo: 'Es obligatorio cuando el alcance es PROGRAMA' },
    ] : []),
  ]
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/elaboracion/finalizar')
    ? Promise.resolve(respuesta(422, { detail: { message: 'Proyecto incompleto', faltantes } }))
    : peticionOriginal(url, init)))
  const finalizar = await screen.findByRole('button', { name: 'Finalizar elaboración' })
  comprobarMetadatos(METADATOS_REMOTOS)
  const campos = Array.from(document.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea'))
  const valoresAntes = campos.map((campo) => campo.value)
  await usuario.click(finalizar)
  await usuario.click(screen.getByRole('button', { name: 'Confirmar y enviar a Jurídica' }))
  expect(await screen.findByText(motivo)).toBeTruthy()
  const resumen = screen.getByRole('alert')
  expect(within(resumen).getByText('Revisa lo siguiente antes de finalizar:')).toBeTruthy()
  expect(screen.queryByText('Completa estos datos antes de finalizar:')).toBeNull()
  if (otrosCampos) {
    expect(within(resumen).getByText('Describe el objeto del convenio.')).toBeTruthy()
    expect(within(resumen).getByText('Selecciona la unidad o programa responsable.')).toBeTruthy()
    expect(screen.getAllByText('Describe el objeto del convenio.')).toHaveLength(2)
    expect(screen.getAllByText('Selecciona la unidad o programa responsable.')).toHaveLength(2)
  }
  expect(document.body.textContent).not.toMatch(/HU-12|precarga|_faltantes_elaboracion|unidad_organizacional_id/)
  expect(JSON.stringify(notify.mock.calls)).not.toMatch(/HU-12|precarga|_faltantes_elaboracion/)
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_REMOTO))
  expect(campos.map((campo) => campo.value)).toEqual(valoresAntes)
  expect(guardados).toHaveLength(0)
})

describe('HU-12 CA-02: usar información de solicitud como texto libre', () => {
  afterEach(() => vi.restoreAllMocks())
  const solicitud: NonNullable<ElaboracionConvenio['solicitud']> = {
    ...ejemploBase.solicitud,
    id: 41, consecutivo: 'SOL-41', tipo_solicitante: 'INTERNO', estado: 'APROBADA',
    implicacion_financiera: null, requisitos_renovacion: null, observaciones: null, fecha_radicacion: null,
    solicitante_nombre: null, solicitante_correo: null, solicitante_cargo: null, solicitante_unidad: null,
    solicitante_programa: null, solicitante_entidad: null, nombre_aliado_propuesto: null,
    identificacion_aliado_propuesto: null, tipo_aliado_propuesto: null, correo_aliado_propuesto: null,
    pais_aliado_propuesto: null, ciudad_aliado_propuesto: null, contacto_contraparte_nombre: null,
    contacto_contraparte_cargo: null, contacto_contraparte_telefono: null, contacto_contraparte_correo: null,
    supervisor_usb_nombre: null, supervisor_usb_cargo: null, supervisor_usb_telefono: null, supervisor_usb_correo: null,
    supervisor_contraparte_nombre: null, supervisor_contraparte_cargo: null, supervisor_contraparte_telefono: null, supervisor_contraparte_correo: null,
  }
  const inicial: ElaboracionConvenio = {
    ...remotoCompleto, origen: 'SOLICITUD', solicitud_id: 41, solicitud,
    contenido: { type: 'doc', content: [{ type: 'paragraph' }] },
  }
  const nombre = 'Usar información de la solicitud como base'

  it.each([false, true])('permite usar la base, redactar libremente y guardar por el mecanismo actual (editar: %s)', async (editar) => {
    const contenido = editar ? DOCUMENTO_EDITADO : ejemploBase.documento
    const { usuario, guardados } = preparar(() => respuesta(200, { ...inicial, contenido, revision_borrador: 2 }), inicial)
    const original = structuredClone(solicitud)
    const confirm = vi.spyOn(window, 'confirm')
    await usuario.click(await screen.findByRole('button', { name: nombre }))
    expect(confirm).not.toHaveBeenCalled()
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(ejemploBase.documento))
    comprobarMetadatos(METADATOS_REMOTOS, false)
    expect(guardados).toHaveLength(0)
    if (editar) await usuario.click(screen.getByRole('button', { name: 'Editar documento' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await screen.findByText('Borrador guardado')
    const metadatos = Object.fromEntries(Object.entries(METADATOS_REMOTOS).filter(([campo]) => campo !== 'aliado_id'))
    expect(guardados).toEqual([{ contenido, expected_revision: 1, ...metadatos }])
    expect(solicitud).toEqual(original)
  })

  it('conserva texto y metadatos locales si cancela el reemplazo y solicita confirmación al reintentar', async () => {
    const { usuario, guardados } = preparar(() => respuesta(200, inicial), inicial)
    await usuario.click(await screen.findByRole('button', { name: 'Editar documento' }))
    const objeto = screen.getByRole('textbox', { name: 'Objeto' })
    await usuario.clear(objeto)
    await usuario.type(objeto, 'Decisión definitiva del Gestor')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    await usuario.click(screen.getByRole('button', { name: nombre }))
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(DOCUMENTO_EDITADO))
    expect(guardados).toHaveLength(0)
    await usuario.click(screen.getByRole('button', { name: nombre }))
    expect(confirm).toHaveBeenCalledTimes(2)
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(ejemploBase.documento))
    expect(screen.getByTestId('copia-documento').textContent).toBe(JSON.stringify(DOCUMENTO_EDITADO))
    expect((objeto as HTMLTextAreaElement).value).toBe('Decisión definitiva del Gestor')
    expect(guardados).toHaveLength(0)
  })

  it('conserva la base local y expected_revision ante un 409 real', async () => {
    const { usuario, guardados } = preparar(() => respuesta(409, { detail: { expected_revision: 1, current_revision: 2 } }), inicial)
    await usuario.click(await screen.findByRole('button', { name: nombre }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar avance' }))
    await screen.findByRole('button', { name: 'Cargar el borrador más reciente' })
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(ejemploBase.documento))
    comprobarMetadatos(METADATOS_REMOTOS, false)
    expect(guardados[0]).toMatchObject({ contenido: ejemploBase.documento, expected_revision: 1 })
    expect((screen.getByRole('button', { name: nombre }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('retira la advertencia de precarga antigua cuando se sustituye por la base libre', async () => {
    const { usuario } = preparar(() => respuesta(200, inicial), { ...inicial, contiene_antecedentes_iniciales: true })
    await screen.findByRole('button', { name: 'Empezar documento contractual limpio' })
    await usuario.click(screen.getByRole('button', { name: nombre }))
    expect(screen.queryByRole('button', { name: 'Empezar documento contractual limpio' })).toBeNull()
    expect(screen.getByTestId('documento').textContent).toBe(JSON.stringify(ejemploBase.documento))
  })

  it.each([
    { ...inicial, origen: 'MANUAL_ORI' as const, solicitud: null, solicitud_id: null },
    { ...inicial, convenio_origen_id: 99, numero_renovacion: 1 },
    { ...inicial, etapa_actual: { id: 2, orden: 2, codigo: 'REVISION_CONTRAPARTE', nombre: 'Contraparte' } },
  ])('no ofrece la acción a manuales, renovaciones o etapas de consulta (%#)', async (datos) => {
    preparar(() => respuesta(200, datos), datos)
    await screen.findByRole('heading', { name: 'Documento jurídico' })
    expect(screen.queryByRole('button', { name: nombre })).toBeNull()
  })

  it('no ofrece la acción sin permiso de edición', async () => {
    const { cliente } = preparar(() => respuesta(200, inicial), inicial)
    await act(async () => cliente.setQueryData(CLAVE_SESION, { ...sesion, permisos: ['convenios.ver'] }))
    await screen.findByRole('heading', { name: 'Documento jurídico' })
    expect(screen.queryByRole('button', { name: nombre })).toBeNull()
  })

  it('explica la ausencia de narrativas sin insertar textos pendientes', async () => {
    const datos = { ...inicial, solicitud: { ...solicitud, objeto: null, justificacion: null, actividades_por_parte: null, metas_esperadas: null } }
    preparar(() => respuesta(200, datos), datos)
    expect(await screen.findByText('La solicitud no contiene texto para usar como base.')).toBeTruthy()
    expect((screen.getByRole('button', { name: nombre }) as HTMLButtonElement).disabled).toBe(true)
  })
})
