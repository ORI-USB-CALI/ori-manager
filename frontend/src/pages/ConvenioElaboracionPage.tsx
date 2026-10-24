import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'
import {
  type ElaboracionConvenio,
  useCatalogosElaboracion,
  useElaboracionConvenio,
  useVersionesConvenio,
  useAliados,
} from './epica02'
import { FinalizarElaboracionModal } from './FinalizarElaboracionModal'
import { fechaHoyLocal, mensajeVigenciaServidor, validarVigencia } from './vigencia'

const ETAPA_ELABORACION = 'ELABORACION'
const CAMPOS = [
  'tipo_convenio_id', 'objeto', 'alcance', 'unidad_organizacional_id', 'aliado_id',
  'implicacion_financiera', 'duracion_meses', 'fecha_inicio', 'fecha_vencimiento',
] as const

interface Observacion {
  id: number
  origen: string
  descripcion: string
  respuesta: string | null
  estado: 'PENDIENTE' | 'ATENDIDA'
  creado_en: string
  fecha_atencion: string | null
  atendida_por: { id: number; nombre_completo: string } | null
}

interface HistorialConvenio {
  revisiones: Array<{ tipo: string; observaciones: Observacion[] }>
}

function fechaHora(valor: string) {
  return new Date(valor).toLocaleString()
}

function fechaInput(valor: string | null) {
  return valor?.slice(0, 10) ?? ''
}

const MENSAJES_PENDIENTES: Record<string, string> = {
  tipo_convenio_id: 'Selecciona el tipo de convenio.',
  objeto: 'Describe el objeto del convenio.',
  alcance: 'Selecciona el alcance del convenio.',
  unidad_organizacional_id: 'Selecciona la unidad o programa responsable.',
  implicacion_financiera: 'Describe la implicación financiera del convenio.',
  duracion_meses: 'Ingresa la duración del convenio.',
  fecha_inicio: 'Define la fecha de inicio.',
  fecha_vencimiento: 'Define la fecha de vencimiento.',
  contenido: 'Completa el documento jurídico.',
}

const CONTEXTOS_VERSION: Record<string, string> = {
  INICIALIZACION: 'Creación del proyecto',
  GUARDADO: 'Avance guardado',
  FINALIZACION: 'Elaboración finalizada',
  CORRECCION_REVISION: 'Ajustes de revisión',
}

function mensajePendiente(campo: string, motivo: string) {
  if (motivo === 'Es obligatorio para finalizar la elaboración'
    || motivo === 'Es obligatorio cuando el alcance es PROGRAMA') {
    return MENSAJES_PENDIENTES[campo] ?? motivo
  }
  if (campo === 'fecha_vencimiento') return mensajeVigenciaServidor(motivo) ?? motivo
  return motivo
}

function contextoVersion(contexto: string) {
  return CONTEXTOS_VERSION[contexto] ?? contexto
}

function valoresMetadata(formulario: HTMLFormElement): Record<string, string | number | null> {
  const form = new FormData(formulario)
  return Object.fromEntries(CAMPOS.filter((campo) => campo !== 'aliado_id' || form.has('aliado_id')).map((campo) => {
    const bruto = String(form.get(campo) ?? '').trim()
    const numerico = campo === 'aliado_id' || campo === 'tipo_convenio_id'
      || campo === 'unidad_organizacional_id'
      || campo === 'duracion_meses'
    return [campo, numerico ? (bruto ? Number(bruto) : null) : (bruto || null)]
  }))
}

function erroresVigencia(metadata: Record<string, string | number | null>) {
  const inicio = typeof metadata.fecha_inicio === 'string' ? metadata.fecha_inicio : null
  const vencimiento = typeof metadata.fecha_vencimiento === 'string' ? metadata.fecha_vencimiento : null
  return validarVigencia(inicio, vencimiento, fechaHoyLocal())
}

function erroresServidor(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object') return {}
  if (Array.isArray(error.detail)) {
    return Object.fromEntries(error.detail.flatMap((item: unknown) => {
      if (!item || typeof item !== 'object' || !('loc' in item) || !('msg' in item)) return []
      const loc = Array.isArray(item.loc) ? item.loc : []
      const campo = loc.at(-1)
      return typeof campo === 'string' && typeof item.msg === 'string' ? [[campo, item.msg]] : []
    }))
  }
  if ('faltantes' in error.detail && Array.isArray(error.detail.faltantes)) {
    return Object.fromEntries(error.detail.faltantes.flatMap((item: unknown) => {
      if (!item || typeof item !== 'object' || !('campo' in item) || !('motivo' in item)) return []
      return typeof item.campo === 'string' && typeof item.motivo === 'string'
        ? [[item.campo, mensajePendiente(item.campo, item.motivo)]]
        : []
    }))
  }
  return {}
}

function esConflictoBorrador(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 409 || !error.detail
    || typeof error.detail !== 'object' || Array.isArray(error.detail)) return false
  return 'expected_revision' in error.detail && 'current_revision' in error.detail
}

export function ConvenioElaboracionPage() {
  const id = Number(useParams().convenioId)
  const elaboracion = useElaboracionConvenio(id)
  const catalogos = useCatalogosElaboracion()
  const aliados = useAliados(true)
  const versiones = useVersionesConvenio(id)
  const historial = useQuery({
    queryKey: ['convenio', id, 'historial'],
    queryFn: () => apiFetch<HistorialConvenio>(`/convenios/${id}/revisiones`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })
  const { puede } = useSesion()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const formRef = useRef<HTMLFormElement>(null)
  // Lo editado y no guardado, junto con la revisión del borrador desde la que se
  // empezó a editar. Se conserva aunque lleguen datos nuevos del servidor.
  const [cambiosLocales, setCambiosLocales] = useState<{
    revision: number
    contenido: DocumentoConvenio
  } | null>(null)
  const [conflicto, setConflicto] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [modalAbierto, setModalAbierto] = useState(false)
  const [payloadFinal, setPayloadFinal] = useState<Record<string, unknown>>({})
  const [respuestas, setRespuestas] = useState<Record<number, string>>({})

  const guardar = useMutation({
    mutationFn: (payload: Record<string, unknown>) => apiFetch<ElaboracionConvenio>(
      `/convenios/${id}/elaboracion`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
    onSuccess: async (resultado, variables) => {
      const sinCambios = resultado.revision_borrador === Number(variables.expected_revision)
      setErrores({})
      setCambiosLocales(null)
      setConflicto(false)
      queryClient.setQueryData(['convenios', id, 'elaboracion'], resultado)
      notify({
        type: sinCambios ? 'warning' : 'success',
        message: sinCambios
          ? 'No había cambios por guardar.'
          : 'Avance guardado. La versión formal se crea al enviar el proyecto a revisión jurídica.',
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] }),
        queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion', 'validacion'] }),
      ])
    },
    onError: (error) => {
      setErrores(erroresServidor(error))
      const esConflicto = esConflictoBorrador(error)
      setConflicto(esConflicto)
      notify({
        type: 'error',
        message: esConflicto
          ? 'Otra persona guardó el borrador mientras lo editabas. Tus cambios no se guardaron.'
          : error instanceof Error ? error.message : 'No fue posible guardar el avance.',
      })
    },
  })

  function cargarBorradorReciente() {
    setCambiosLocales(null)
    setConflicto(false)
    void queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] })
  }

  const atender = useMutation({
    mutationFn: ({ observacionId, respuesta }: { observacionId: number; respuesta: string }) =>
      apiFetch(`/convenios/${id}/observaciones/${observacionId}/atender`, {
        method: 'PATCH', body: JSON.stringify({ respuesta }),
      }),
    onSuccess: async (_, variables) => {
      setRespuestas((actual) => ({ ...actual, [variables.observacionId]: '' }))
      await queryClient.invalidateQueries({ queryKey: ['convenio', id, 'historial'] })
      notify({ type: 'success', message: 'Observación atendida.' })
    },
    onError: (error) => notify({
      type: 'error', message: error instanceof Error ? error.message : 'No fue posible atender la observación.',
    }),
  })

  if (elaboracion.isPending) return <p className="estado-pagina">Cargando elaboración…</p>
  if (elaboracion.isError) {
    return <section className="card estado-vacio"><h1>No se pudo consultar el proyecto de convenio</h1></section>
  }

  const datos = elaboracion.data
  const contenido = cambiosLocales?.contenido ?? datos.contenido
  const contenidoModificado = cambiosLocales !== null
  const revisionBase = cambiosLocales?.revision ?? datos.revision_borrador
  const borradorDesactualizado = conflicto
    || (cambiosLocales !== null && cambiosLocales.revision !== datos.revision_borrador)
  const editable = puede('convenios.editar') && datos.etapa_actual?.codigo === ETAPA_ELABORACION
  const todasLasObservaciones = historial.data?.revisiones.flatMap((revision) => revision.observaciones) ?? []
  const observacionesJuridicas = todasLasObservaciones.filter((item) => item.origen === 'REVISOR_ORI')
  const observacionesContraparte = todasLasObservaciones.filter((item) => item.origen === 'CONTRAPARTE')
  const observacionesRevisionFinal = todasLasObservaciones.filter((item) => item.origen === 'REVISION_FINAL_ORI')
  const juridicasPendientes = observacionesJuridicas.filter((item) => item.estado === 'PENDIENTE')
  const contrapartePendientes = observacionesContraparte.filter((item) => item.estado === 'PENDIENTE')
  const revisionFinalPendientes = observacionesRevisionFinal.filter((item) => item.estado === 'PENDIENTE')
  const juridicasAtendidas = observacionesJuridicas.filter((item) => item.estado === 'ATENDIDA')
  const contraparteAtendidas = observacionesContraparte.filter((item) => item.estado === 'ATENDIDA')
  const hayObservacionesPendientes = juridicasPendientes.length > 0
    || contrapartePendientes.length > 0
    || revisionFinalPendientes.length > 0

  function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!contenido) return
    const metadata = valoresMetadata(event.currentTarget)
    // Igual que el backend: al guardar solo se valida si cambió alguna fecha.
    const cambioVigencia = metadata.fecha_inicio !== (fechaInput(datos.fecha_inicio) || null)
      || metadata.fecha_vencimiento !== (fechaInput(datos.fecha_vencimiento) || null)
    const invalidas = cambioVigencia ? erroresVigencia(metadata) : {}
    if (Object.keys(invalidas).length > 0) {
      setErrores(invalidas)
      notify({ type: 'error', message: 'Revisa las fechas de vigencia antes de guardar.' })
      return
    }
    guardar.mutate({
      ...metadata,
      contenido,
      expected_revision: revisionBase,
    })
  }

  function prepararFinalizacion() {
    if (!formRef.current || !contenido) return
    const metadata = valoresMetadata(formRef.current)
    const invalidas = erroresVigencia(metadata)
    setErrores(invalidas)
    if (Object.keys(invalidas).length > 0) {
      notify({ type: 'error', message: 'Revisa las fechas de vigencia antes de finalizar.' })
      return
    }
    setPayloadFinal({
      ...metadata,
      contenido,
      expected_revision: revisionBase,
    })
    setModalAbierto(true)
  }

  return (
    <>
      <section className="header-banner">
        <h1>Proyecto de convenio {datos.codigo ?? `#${datos.id}`}</h1>
        <p>
          <span className="badge">{datos.etapa_actual?.nombre ?? datos.estado}</span>
          {' · '}Versión formal {datos.version_actual} · {datos.solicitud ? `Solicitud ${datos.solicitud.consecutivo}` : 'Creación directa de ORI'}
        </p>
      </section>

      <form ref={formRef} onSubmit={enviar}>
        <div className="elaboracion-workspace">
          <main className="elaboracion-principal">
            <section className="elaboracion-documento card">
              <div className="editor-cabecera">
                <div>
                  <h2>Documento jurídico</h2>
                  <p className="section-help">Edita libremente el contenido del proyecto de convenio.</p>
                </div>
                {contenidoModificado
                  ? <span className="badge badge-pendiente">Cambios sin guardar</span>
                  : datos.borrador_guardado_en && <span className="badge">Borrador guardado</span>}
              </div>
              {borradorDesactualizado && (
                <div className="alert-error" role="alert">
                  <p>
                    Otra persona guardó el borrador mientras lo editabas. Tus cambios siguen en
                    pantalla pero no se han guardado: cópialos antes de cargar el borrador más reciente.
                  </p>
                  <button className="btn btn-outline" type="button" onClick={cargarBorradorReciente}>
                    Cargar el borrador más reciente
                  </button>
                </div>
              )}
              {contenido ? (
                <ConvenioEditor
                  key={`${datos.version_actual}-${revisionBase}`}
                  contenido={contenido}
                  editable={editable}
                  onChange={(nuevo) => {
                    setCambiosLocales((actual) => ({
                      revision: actual?.revision ?? datos.revision_borrador,
                      contenido: nuevo,
                    }))
                  }}
                />
              ) : (
                <div className="estado-vacio">Este proyecto aún no tiene un documento editable.</div>
              )}
            </section>

            {juridicasPendientes.length > 0 && (
              <section className="card observaciones-elaboracion observaciones-pendientes">
                <h2>Observaciones jurídicas pendientes</h2>
                <p className="section-help">Corrige estos puntos antes de volver a enviar el proyecto a revisión jurídica.</p>
                {juridicasPendientes.map((observacion) => (
                  <article className="observacion-elaboracion" key={observacion.id}>
                    <div className="observacion-cabecera">
                      <h3>{observacion.descripcion}</h3>
                      <span className="badge badge-pendiente">Pendiente</span>
                    </div>
                    <p className="texto-secundario">Registrada el {fechaHora(observacion.creado_en)}</p>
                    {editable && (
                      <div className="form-group">
                        <textarea className="form-control" value={respuestas[observacion.id] ?? ''} onChange={(event) => setRespuestas((actual) => ({ ...actual, [observacion.id]: event.target.value }))} />
                        <button className="btn btn-outline" type="button" disabled={!respuestas[observacion.id]?.trim() || atender.isPending} onClick={() => atender.mutate({ observacionId: observacion.id, respuesta: respuestas[observacion.id].trim() })}>Marcar como atendida</button>
                      </div>
                    )}
                  </article>
                ))}
              </section>
            )}

            {contrapartePendientes.length > 0 && (
              <section className="card observaciones-elaboracion observaciones-pendientes observaciones-contraparte">
                <h2>Observaciones de contraparte pendientes</h2>
                <p className="section-help">Atiende las solicitudes de la contraparte y corrige el documento antes de iniciar una nueva ronda jurídica.</p>
                {contrapartePendientes.map((observacion) => (
                  <article className="observacion-elaboracion" key={observacion.id}>
                    <div className="observacion-cabecera">
                      <h3>{observacion.descripcion}</h3>
                      <span className="badge badge-pendiente">Pendiente</span>
                    </div>
                    <p className="texto-secundario">Recibida el {fechaHora(observacion.creado_en)}</p>
                    {observacion.respuesta && <p><strong>Respuesta del Gestor:</strong> {observacion.respuesta}</p>}
                    {editable && (
                      <div className="form-group">
                        <textarea className="form-control" aria-label={`Respuesta a: ${observacion.descripcion}`} value={respuestas[observacion.id] ?? ''} onChange={(event) => setRespuestas((actual) => ({ ...actual, [observacion.id]: event.target.value }))} />
                        <button className="btn btn-outline" type="button" disabled={!respuestas[observacion.id]?.trim() || atender.isPending} onClick={() => atender.mutate({ observacionId: observacion.id, respuesta: respuestas[observacion.id].trim() })}>Marcar como atendida</button>
                      </div>
                    )}
                  </article>
                ))}
              </section>
            )}

            {revisionFinalPendientes.length > 0 && (
              <section className="card observaciones-elaboracion observaciones-pendientes">
                <h2>Observaciones de revisión final pendientes</h2>
                <p className="section-help">Atiende la observación, corrige el proyecto y envíalo de nuevo: al enviarlo se crea la nueva versión que repite las revisiones.</p>
                {revisionFinalPendientes.map((observacion) => (
                  <article className="observacion-elaboracion" key={observacion.id}>
                    <div className="observacion-cabecera">
                      <h3>{observacion.descripcion}</h3>
                      <span className="badge badge-pendiente">Pendiente</span>
                    </div>
                    <p className="texto-secundario">Registrada el {fechaHora(observacion.creado_en)}</p>
                    {editable && (
                      <div className="form-group">
                        <textarea className="form-control" aria-label={`Respuesta a: ${observacion.descripcion}`} value={respuestas[observacion.id] ?? ''} onChange={(event) => setRespuestas((actual) => ({ ...actual, [observacion.id]: event.target.value }))} />
                        <button className="btn btn-outline" type="button" disabled={!respuestas[observacion.id]?.trim() || atender.isPending} onClick={() => atender.mutate({ observacionId: observacion.id, respuesta: respuestas[observacion.id].trim() })}>Marcar como atendida</button>
                      </div>
                    )}
                  </article>
                ))}
              </section>
            )}
          </main>

          <aside className="elaboracion-panel">
            <section className="card proyecto-resumen">
              <h2>Proyecto de convenio</h2>
              <dl className="proyecto-datos">
                <dt>Etapa actual</dt><dd>{datos.etapa_actual?.nombre ?? '—'}</dd>
                <dt>Versión formal</dt><dd>{datos.version_actual || 'Sin versión'}</dd>
                <dt>Borrador</dt>
                <dd>
                  {datos.borrador_guardado_en
                    ? `Guardado el ${fechaHora(datos.borrador_guardado_en)}, pendiente de enviar a revisión`
                    : 'Sin avances guardados desde la versión formal'}
                </dd>
                <dt>Plantilla utilizada</dt><dd>{datos.plantilla_origen?.nombre ?? 'Sin plantilla asociada'}</dd>
              </dl>
              {editable && (
                <div className="acciones-verticales">
                  <button className="btn btn-outline" type="submit" disabled={guardar.isPending || !contenido}>
                    {guardar.isPending ? 'Guardando…' : 'Guardar avance'}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!contenido || hayObservacionesPendientes}
                    onClick={prepararFinalizacion}
                  >
                    Finalizar elaboración
                  </button>
                </div>
              )}
            </section>

            <section className="card datos-clave">
              <h2>Datos clave del convenio</h2>
              <p className="section-help">Estos datos ayudan a identificar y gestionar el convenio dentro del sistema.</p>
              {Object.keys(errores).length > 0 && (
                <div className="resumen-pendientes" role="alert">
                  <strong>Completa estos datos antes de finalizar:</strong>
                  <ul>
                    {Object.entries(errores).map(([campo, mensaje]) => <li key={campo}>{mensaje}</li>)}
                  </ul>
                </div>
              )}
              {datos.origen === 'MANUAL_ORI' && (
                <p className="section-help">Creado manualmente por {datos.creado_por.nombre_completo} el {fechaHora(datos.creado_en)}.</p>
              )}
              <div className="datos-clave-campos">
                {datos.origen === 'MANUAL_ORI' && (
                  <label className="form-group">Aliado / contraparte (puedes definirlo durante la elaboración)
                    <select className="form-control select" name="aliado_id" defaultValue={datos.aliado_id ?? ''} disabled={!editable}>
                      <option value="">Por definir</option>
                      {aliados.data?.items.map((aliado) => <option key={aliado.id} value={aliado.id}>{aliado.nombre}</option>)}
                      {datos.aliado && !aliados.data?.items.some((aliado) => aliado.id === datos.aliado_id) && (
                        <option value={datos.aliado.id}>{datos.aliado.nombre}</option>
                      )}
                    </select>
                    {errores.aliado_id && <span className="form-error">{errores.aliado_id}</span>}
                  </label>
                )}
                <label className="form-group">Tipo de convenio
                  <select className="form-control select" name="tipo_convenio_id" defaultValue={datos.tipo_convenio_id ?? ''} disabled={!editable}>
                    <option value="">Seleccione</option>
                    {catalogos.data?.tipos_convenio.map((tipo) => <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>)}
                  </select>
                  {errores.tipo_convenio_id && <span className="form-error">{errores.tipo_convenio_id}</span>}
                </label>
                <label className="form-group">Objeto
                  <textarea className="form-control" name="objeto" defaultValue={datos.objeto ?? ''} disabled={!editable} />
                  {errores.objeto && <span className="form-error">{errores.objeto}</span>}
                </label>
                <label className="form-group">Alcance
                  <select className="form-control select" name="alcance" defaultValue={datos.alcance ?? ''} disabled={!editable}>
                    <option value="">Seleccione</option><option value="INSTITUCIONAL">Institucional</option><option value="PROGRAMA">Programa</option>
                  </select>
                  {errores.alcance && <span className="form-error">{errores.alcance}</span>}
                </label>
                <label className="form-group">Unidad / programa
                  <select className="form-control select" name="unidad_organizacional_id" defaultValue={datos.unidad_organizacional_id ?? ''} disabled={!editable}>
                    <option value="">No aplica</option>
                    {catalogos.data?.unidades_organizacionales.map((unidad) => <option key={unidad.id} value={unidad.id}>{unidad.nombre}</option>)}
                  </select>
                  {errores.unidad_organizacional_id && <span className="form-error">{errores.unidad_organizacional_id}</span>}
                </label>
                <label className="form-group">Implicación financiera
                  <textarea className="form-control" name="implicacion_financiera" defaultValue={datos.implicacion_financiera ?? ''} disabled={!editable} />
                  {errores.implicacion_financiera && <span className="form-error">{errores.implicacion_financiera}</span>}
                </label>
                <label className="form-group">Duración (meses)
                  <input className="form-control" name="duracion_meses" type="number" min="0" defaultValue={datos.duracion_meses ?? ''} disabled={!editable} />
                  {errores.duracion_meses && <span className="form-error">{errores.duracion_meses}</span>}
                </label>
                <label className="form-group">Fecha de inicio
                  <input className="form-control" name="fecha_inicio" type="date" defaultValue={fechaInput(datos.fecha_inicio)} disabled={!editable} />
                  {errores.fecha_inicio && <span className="form-error">{errores.fecha_inicio}</span>}
                </label>
                <label className="form-group">Fecha de vencimiento
                  <input className="form-control" name="fecha_vencimiento" type="date" defaultValue={fechaInput(datos.fecha_vencimiento)} disabled={!editable} />
                  {errores.fecha_vencimiento && <span className="form-error">{errores.fecha_vencimiento}</span>}
                </label>
              </div>
            </section>

            <section className="card historial-versiones">
              <h2>Historial de versiones</h2>
              <div className="version-lista">
                {versiones.data?.map((version) => (
                  <article className={version.numero === datos.version_actual ? 'version-actual' : undefined} key={version.numero}>
                    <div className="version-cabecera">
                      <strong>Versión {version.numero}</strong>
                      {version.numero === datos.version_actual && <span className="badge">Actual</span>}
                    </div>
                    <span><strong>Autor:</strong> {version.autor.nombre_completo}</span>
                    <span><strong>Fecha:</strong> {fechaHora(version.creado_en)}</span>
                    <span><strong>Contexto:</strong> {contextoVersion(version.contexto)}</span>
                  </article>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </form>

      {juridicasAtendidas.length > 0 && (
        <section className="card observaciones-elaboracion">
          <h2>Observaciones jurídicas</h2>
          {juridicasAtendidas.map((observacion) => (
            <article className="observacion-elaboracion" key={observacion.id}>
              <h3>{observacion.descripcion}</h3>
              <p><strong>Respuesta:</strong> {observacion.respuesta}</p>
              <p className="texto-secundario">Atendida por {observacion.atendida_por?.nombre_completo ?? 'ORI'} el {fechaHora(observacion.fecha_atencion ?? observacion.creado_en)}</p>
            </article>
          ))}
        </section>
      )}

      {contraparteAtendidas.length > 0 && (
        <section className="card observaciones-elaboracion observaciones-contraparte-atendidas">
          <h2>Observaciones de contraparte atendidas</h2>
          {contraparteAtendidas.map((observacion) => (
            <article className="observacion-elaboracion" key={observacion.id}>
              <div className="observacion-cabecera">
                <h3>{observacion.descripcion}</h3>
                <span className="badge badge-activo">Atendida</span>
              </div>
              <p><strong>Respuesta del Gestor:</strong> {observacion.respuesta ?? '—'}</p>
              <p className="texto-secundario">Atendida por {observacion.atendida_por?.nombre_completo ?? 'ORI'} el {fechaHora(observacion.fecha_atencion ?? observacion.creado_en)}</p>
            </article>
          ))}
        </section>
      )}

      {modalAbierto && (
        <FinalizarElaboracionModal
          convenioId={id}
          valores={payloadFinal}
          onCerrar={() => setModalAbierto(false)}
          onErrorValidacion={(error) => setErrores(erroresServidor(error))}
          onFinalizado={() => Promise.all([
            queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] }),
            queryClient.invalidateQueries({ queryKey: ['convenios', id, 'versiones'] }),
          ])}
        />
      )}

      <div className="page-toolbar"><Link className="btn btn-outline" to={`/convenios/${datos.id}`}>Volver al detalle</Link></div>
    </>
  )
}
