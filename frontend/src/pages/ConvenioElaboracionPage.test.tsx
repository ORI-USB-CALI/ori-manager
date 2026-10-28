import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
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

function comprobarMetadatos(valores: Record<string, string | number | null>) {
  const etiquetas = {
    aliado_id: /Aliado \/ contraparte/, tipo_convenio_id: 'Tipo de convenio', objeto: 'Objeto',
    alcance: 'Alcance', unidad_organizacional_id: 'Unidad / programa',
    implicacion_financiera: 'Implicación financiera', duracion_meses: 'Duración (meses)',
    fecha_inicio: 'Fecha de inicio', fecha_vencimiento: 'Fecha de vencimiento',
  }
  for (const [campo, etiqueta] of Object.entries(etiquetas)) {
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
  return {
    cliente, guardados, notify, usuario: userEvent.setup(),
    actualizarServidor: (nuevo: ElaboracionConvenio) => { datos = nuevo },
    fallarLectura: () => { falloLectura = true },
  }
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
