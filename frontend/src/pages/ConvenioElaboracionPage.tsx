import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import {
  ETIQUETA_TIPO,
  type Convenio,
  type ElaboracionConvenio,
  type TipoAliado,
  useCatalogosElaboracion,
  useElaboracionConvenio,
} from './epica02'
import { FinalizarElaboracionModal } from './FinalizarElaboracionModal'

const CODIGO_ETAPA_ELABORACION = 'ELABORACION'
const CAMPOS_FORMULARIO = [
  'tipo_convenio_id',
  'objeto',
  'alcance',
  'unidad_organizacional_id',
  'implicacion_financiera',
  'duracion_meses',
  'fecha_inicio',
  'fecha_vencimiento',
] as const

const AYUDAS_ELABORACION: Record<(typeof CAMPOS_FORMULARIO)[number], string> = {
  tipo_convenio_id: 'Seleccione la modalidad contractual que corresponde al proyecto de convenio.',
  objeto: 'Describa el propósito principal que se formalizará mediante el convenio.',
  alcance: 'Indique si el convenio aplica institucionalmente o a un programa específico.',
  unidad_organizacional_id: 'Seleccione el programa o unidad al que se limita el alcance del convenio.',
  implicacion_financiera: 'Describa los compromisos o recursos financieros contemplados, cuando correspondan.',
  duracion_meses: 'Indique la duración prevista del convenio expresada en meses.',
  fecha_inicio: 'Fecha prevista para iniciar la ejecución. Este dato es opcional en Elaboración.',
  fecha_vencimiento: 'Fecha prevista de terminación. Si informa ambas fechas, debe ser posterior al inicio.',
}

interface ObservacionJuridica {
  id: number
  origen: string
  descripcion: string
  respuesta: string | null
  estado: 'PENDIENTE' | 'ATENDIDA'
  fecha_atencion: string | null
}

interface HistorialRevision {
  tipo: string
  observaciones: ObservacionJuridica[]
}

interface HistorialConvenio {
  revisiones: HistorialRevision[]
}

function fecha(valor: string | null) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

function fechaHora(valor: string) {
  return new Date(valor).toLocaleString()
}

function fechaInput(valor: string | null) {
  return valor ? valor.slice(0, 10) : ''
}

function etiquetaTipoAliado(valor: string | null) {
  if (!valor) return '—'
  return ETIQUETA_TIPO[valor as TipoAliado] ?? valor
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
        ? [[item.campo, item.motivo]]
        : []
    }))
  }
  return {}
}

function valoresFormulario(formulario: HTMLFormElement): Record<string, string | number | null> {
  const form = new FormData(formulario)
  return Object.fromEntries(CAMPOS_FORMULARIO.map((campo) => {
    const bruto = String(form.get(campo) ?? '').trim()
    const valor = campo === 'tipo_convenio_id' || campo === 'unidad_organizacional_id' || campo === 'duracion_meses'
      ? (bruto ? Number(bruto) : null)
      : (bruto || null)
    return [campo, valor]
  }))
}

function camposModificados(formulario: HTMLFormElement, original: ElaboracionConvenio): Record<string, string | number | null> {
  const form = new FormData(formulario)
  const cambios: Record<string, string | number | null> = {}

  for (const campo of CAMPOS_FORMULARIO) {
    if (!form.has(campo)) continue
    const bruto = String(form.get(campo) ?? '').trim()
    let valor: string | number | null = bruto || null
    if (campo === 'tipo_convenio_id' || campo === 'unidad_organizacional_id' || campo === 'duracion_meses') {
      valor = bruto ? Number(bruto) : null
    }
    const actual = original[campo as keyof ElaboracionConvenio]
    const actualComparable = campo === 'fecha_inicio' || campo === 'fecha_vencimiento' ? fechaInput(actual as string | null) : (actual ?? null)
    if (valor !== actualComparable && !(valor === null && actualComparable === null)) {
      cambios[campo] = valor
    }
  }

  return cambios
}

export function ConvenioElaboracionPage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const elaboracion = useElaboracionConvenio(id)
  const catalogos = useCatalogosElaboracion()
  const { puede } = useSesion()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const formRef = useRef<HTMLFormElement>(null)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [respuestas, setRespuestas] = useState<Record<number, string>>({})
  const [alcanceSeleccionado, setAlcanceSeleccionado] = useState<string | null>(null)
  const [modalFinalizarAbierto, setModalFinalizarAbierto] = useState(false)
  const [valoresFinalizacion, setValoresFinalizacion] = useState<Record<string, string | number | null>>({})
  const historial = useQuery({
    queryKey: ['convenio', id, 'historial'],
    queryFn: () => apiFetch<HistorialConvenio>(`/convenios/${id}/revisiones`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })

  const guardar = useMutation({
    mutationFn: (cambios: Record<string, unknown>) =>
      apiFetch<Convenio>(`/convenios/${id}`, { method: 'PATCH', body: JSON.stringify(cambios) }),
    onSuccess: async () => {
      setErrores({})
      notify({ type: 'success', message: 'Avance guardado. El convenio permanece en Elaboración.' })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] }),
      ])
    },
    onError: (error) => {
      setErrores(erroresServidor(error))
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible guardar el avance.' })
    },
  })
  const atender = useMutation({
    mutationFn: ({ observacionId, respuesta }: { observacionId: number; respuesta: string }) =>
      apiFetch(`/convenios/${id}/observaciones/${observacionId}/atender`, {
        method: 'PATCH',
        body: JSON.stringify({ respuesta }),
      }),
    onSuccess: async (_, variables) => {
      setRespuestas((actuales) => ({ ...actuales, [variables.observacionId]: '' }))
      notify({ type: 'success', message: 'Observación jurídica atendida correctamente.' })
      await queryClient.invalidateQueries({ queryKey: ['convenio', id, 'historial'] })
    },
    onError: (error) => notify({
      type: 'error',
      message: error instanceof Error ? error.message : 'No fue posible atender la observación.',
    }),
  })

  if (elaboracion.isPending) return <p className="estado-pagina">Cargando elaboración…</p>
  if (elaboracion.isError) {
    return (
      <section className="card estado-vacio">
        <h1>{elaboracion.error instanceof ApiError && elaboracion.error.status === 404 ? 'Convenio no encontrado' : 'No se pudo consultar la elaboración'}</h1>
      </section>
    )
  }

  const datos = elaboracion.data
  const solicitud = datos.solicitud
  const editable = puede('convenios.editar') && datos.etapa_actual?.codigo === CODIGO_ETAPA_ELABORACION
  const alcance = alcanceSeleccionado ?? datos.alcance ?? ''
  const observacionesJuridicas = historial.data?.revisiones
    .filter((revision) => revision.tipo === 'JURIDICA')
    .flatMap((revision) => revision.observaciones)
    .filter((observacion) => observacion.origen === 'REVISOR_ORI') ?? []
  const observacionesPendientes = observacionesJuridicas.filter((observacion) => observacion.estado === 'PENDIENTE')
  const puedeFinalizar = editable && observacionesPendientes.length === 0

  function mensajeCampo(campo: string) {
    return errores[campo]
  }

  function idCampo(campo: (typeof CAMPOS_FORMULARIO)[number]) {
    return `elaboracion-${campo.replaceAll('_', '-')}`
  }

  function descripcionCampo(campo: (typeof CAMPOS_FORMULARIO)[number]) {
    const id = idCampo(campo)
    const ayudaVisible = campo === 'fecha_inicio' || campo === 'fecha_vencimiento'
    return [ayudaVisible ? `${id}-ayuda` : null, mensajeCampo(campo) ? `${id}-error` : null]
      .filter(Boolean)
      .join(' ') || undefined
  }

  function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const cambios = camposModificados(event.currentTarget, datos)
    if (Object.keys(cambios).length === 0) {
      notify({ type: 'warning', message: 'No hay cambios para guardar.' })
      return
    }
    guardar.mutate(cambios)
  }

  return (
    <>
      <section className="header-banner">
        <h1>Elaboración del convenio {datos.codigo ?? `#${datos.id}`}</h1>
        <p>
          <span className="badge">{datos.etapa_actual?.nombre ?? datos.estado}</span> · Originado por la solicitud{' '}
          <strong>{solicitud.consecutivo}</strong>
        </p>
      </section>

      <form ref={formRef} onSubmit={enviar}>
        <section className="card">
          <h2>Información del convenio</h2>
          <div className="form-grid">
            <label className="form-group" htmlFor={idCampo('tipo_convenio_id')}>
              <span className="form-label">Tipo de convenio {editable && '*'}</span>
              <select
                id={idCampo('tipo_convenio_id')}
                className={`form-control select ${mensajeCampo('tipo_convenio_id') ? 'is-invalid' : ''}`}
                name="tipo_convenio_id"
                disabled={!editable || catalogos.isPending}
                defaultValue={datos.tipo_convenio_id ?? ''}
                aria-describedby={descripcionCampo('tipo_convenio_id')}
                aria-invalid={Boolean(mensajeCampo('tipo_convenio_id'))}
              >
                <option value="">Seleccione el tipo de convenio</option>
                {datos.tipo_convenio_id != null
                  && !catalogos.data?.tipos_convenio.some((tipo) => tipo.id === datos.tipo_convenio_id)
                  && datos.tipo_convenio && (
                    <option value={datos.tipo_convenio_id}>{datos.tipo_convenio.nombre}</option>
                  )}
                {catalogos.data?.tipos_convenio.map((tipo) => (
                  <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>
                ))}
              </select>
              {mensajeCampo('tipo_convenio_id') && <span id={`${idCampo('tipo_convenio_id')}-error`} className="form-error">{mensajeCampo('tipo_convenio_id')}</span>}
            </label>

            <label className="form-group form-span-2" htmlFor={idCampo('objeto')}>
              <span className="form-label">Objeto {editable && '*'}</span>
              <textarea
                id={idCampo('objeto')}
                className={`form-control ${mensajeCampo('objeto') ? 'is-invalid' : ''}`}
                name="objeto"
                placeholder={AYUDAS_ELABORACION.objeto}
                defaultValue={datos.objeto ?? ''}
                disabled={!editable}
                aria-describedby={descripcionCampo('objeto')}
                aria-invalid={Boolean(mensajeCampo('objeto'))}
              />
              {mensajeCampo('objeto') && <span id={`${idCampo('objeto')}-error`} className="form-error">{mensajeCampo('objeto')}</span>}
            </label>

            <label className="form-group" htmlFor={idCampo('alcance')}>
              <span className="form-label">Alcance {editable && '*'}</span>
              <select
                id={idCampo('alcance')}
                className={`form-control select ${mensajeCampo('alcance') ? 'is-invalid' : ''}`}
                name="alcance"
                defaultValue={datos.alcance ?? ''}
                disabled={!editable}
                aria-describedby={descripcionCampo('alcance')}
                aria-invalid={Boolean(mensajeCampo('alcance'))}
                onChange={(event) => setAlcanceSeleccionado(event.target.value)}
              >
                <option value="">Seleccione el alcance</option>
                <option value="INSTITUCIONAL">Institucional</option>
                <option value="PROGRAMA">Programa</option>
              </select>
              {mensajeCampo('alcance') && <span id={`${idCampo('alcance')}-error`} className="form-error">{mensajeCampo('alcance')}</span>}
            </label>

            {alcance === 'PROGRAMA' && (
              <label className="form-group" htmlFor={idCampo('unidad_organizacional_id')}>
                <span className="form-label">Unidad organizacional *</span>
                <select
                  id={idCampo('unidad_organizacional_id')}
                  className={`form-control select ${mensajeCampo('unidad_organizacional_id') ? 'is-invalid' : ''}`}
                  name="unidad_organizacional_id"
                  defaultValue={datos.unidad_organizacional_id ?? ''}
                  disabled={!editable || catalogos.isPending}
                  aria-describedby={descripcionCampo('unidad_organizacional_id')}
                  aria-invalid={Boolean(mensajeCampo('unidad_organizacional_id'))}
                >
                  <option value="">Seleccione una unidad organizacional</option>
                  {datos.unidad_organizacional_id != null
                    && !catalogos.data?.unidades_organizacionales.some((unidad) => unidad.id === datos.unidad_organizacional_id)
                    && datos.unidad_organizacional && (
                      <option value={datos.unidad_organizacional_id}>{datos.unidad_organizacional.nombre}</option>
                    )}
                  {catalogos.data?.unidades_organizacionales.map((unidad) => (
                    <option key={unidad.id} value={unidad.id}>{unidad.nombre}</option>
                  ))}
                </select>
                {mensajeCampo('unidad_organizacional_id') && <span id={`${idCampo('unidad_organizacional_id')}-error`} className="form-error">{mensajeCampo('unidad_organizacional_id')}</span>}
              </label>
            )}

            <label className="form-group form-span-2" htmlFor={idCampo('implicacion_financiera')}>
              <span className="form-label">Implicación financiera {editable && '*'}</span>
              <textarea
                id={idCampo('implicacion_financiera')}
                className={`form-control ${mensajeCampo('implicacion_financiera') ? 'is-invalid' : ''}`}
                name="implicacion_financiera"
                placeholder={AYUDAS_ELABORACION.implicacion_financiera}
                defaultValue={datos.implicacion_financiera ?? ''}
                disabled={!editable}
                aria-describedby={descripcionCampo('implicacion_financiera')}
                aria-invalid={Boolean(mensajeCampo('implicacion_financiera'))}
              />
              {mensajeCampo('implicacion_financiera') && <span id={`${idCampo('implicacion_financiera')}-error`} className="form-error">{mensajeCampo('implicacion_financiera')}</span>}
            </label>

            <label className="form-group" htmlFor={idCampo('duracion_meses')}>
              <span className="form-label">Duración (meses) {editable && '*'}</span>
              <input
                id={idCampo('duracion_meses')}
                className={`form-control ${mensajeCampo('duracion_meses') ? 'is-invalid' : ''}`}
                name="duracion_meses"
                type="number"
                min={0}
                placeholder="Duración prevista en meses"
                defaultValue={datos.duracion_meses ?? ''}
                disabled={!editable}
                aria-describedby={descripcionCampo('duracion_meses')}
                aria-invalid={Boolean(mensajeCampo('duracion_meses'))}
              />
              {mensajeCampo('duracion_meses') && <span id={`${idCampo('duracion_meses')}-error`} className="form-error">{mensajeCampo('duracion_meses')}</span>}
            </label>

            <label className="form-group" htmlFor={idCampo('fecha_inicio')}>
              <span className="form-label">Fecha de inicio</span>
              <input
                id={idCampo('fecha_inicio')}
                className={`form-control ${mensajeCampo('fecha_inicio') ? 'is-invalid' : ''}`}
                name="fecha_inicio"
                type="date"
                defaultValue={fechaInput(datos.fecha_inicio)}
                disabled={!editable}
                aria-describedby={descripcionCampo('fecha_inicio')}
                aria-invalid={Boolean(mensajeCampo('fecha_inicio'))}
              />
              <small id={`${idCampo('fecha_inicio')}-ayuda`} className="form-help">{AYUDAS_ELABORACION.fecha_inicio}</small>
              {mensajeCampo('fecha_inicio') && <span id={`${idCampo('fecha_inicio')}-error`} className="form-error">{mensajeCampo('fecha_inicio')}</span>}
            </label>

            <label className="form-group" htmlFor={idCampo('fecha_vencimiento')}>
              <span className="form-label">Fecha de vencimiento</span>
              <input
                id={idCampo('fecha_vencimiento')}
                className={`form-control ${mensajeCampo('fecha_vencimiento') ? 'is-invalid' : ''}`}
                name="fecha_vencimiento"
                type="date"
                defaultValue={fechaInput(datos.fecha_vencimiento)}
                disabled={!editable}
                aria-describedby={descripcionCampo('fecha_vencimiento')}
                aria-invalid={Boolean(mensajeCampo('fecha_vencimiento'))}
              />
              <small id={`${idCampo('fecha_vencimiento')}-ayuda`} className="form-help">{AYUDAS_ELABORACION.fecha_vencimiento}</small>
              {mensajeCampo('fecha_vencimiento') && <span id={`${idCampo('fecha_vencimiento')}-error`} className="form-error">{mensajeCampo('fecha_vencimiento')}</span>}
            </label>
          </div>

          {editable && (
            <div className="page-toolbar">
              <button className="btn btn-outline" type="submit" disabled={guardar.isPending}>
                {guardar.isPending ? 'Guardando…' : 'Guardar avance'}
              </button>
              <button
                className="btn btn-primary"
                type="button"
                disabled={!puedeFinalizar}
                title={!puedeFinalizar && observacionesPendientes.length > 0
                  ? 'Atienda todas las observaciones jurídicas antes de reenviar el convenio'
                  : undefined}
                onClick={() => {
                  if (!formRef.current) return
                  setErrores({})
                  setValoresFinalizacion(valoresFormulario(formRef.current))
                  setModalFinalizarAbierto(true)
                }}
              >
                Finalizar elaboración
              </button>
              <small className="caption">
                {datos.actualizado_en !== datos.creado_en
                  ? `Último guardado: ${fechaHora(datos.actualizado_en)}`
                  : 'Aún no se han guardado avances.'}
              </small>
            </div>
          )}
          {!editable && (
            <p className="section-help">
              {datos.etapa_actual?.codigo !== CODIGO_ETAPA_ELABORACION
                ? 'Este convenio ya no está en etapa de Elaboración; la información quedó fija para revisión.'
                : 'No tiene permisos para editar este convenio.'}
            </p>
          )}
        </section>
      </form>

      {observacionesJuridicas.length > 0 && (
        <section className="card observaciones-elaboracion">
          <h2>Observaciones de la revisión jurídica</h2>
          <p className="section-help">
            Revise las correcciones solicitadas y responda cada observación pendiente antes de reenviar el convenio.
          </p>
          {observacionesJuridicas.map((observacion) => {
            const respuesta = respuestas[observacion.id] ?? ''
            const pendiente = observacion.estado === 'PENDIENTE'
            const errorRespuesta = pendiente && respuestas[observacion.id] !== undefined && !respuesta.trim()
            return (
              <article className="observacion-elaboracion" key={observacion.id}>
                <div className="page-toolbar">
                  <h3>{observacion.descripcion}</h3>
                  <span className={`badge ${pendiente ? 'badge-pendiente' : 'badge-activo'}`}>
                    {pendiente ? 'Pendiente' : 'Atendida'}
                  </span>
                </div>
                {!pendiente && (
                  <p><strong>Respuesta:</strong> {observacion.respuesta ?? '—'}</p>
                )}
                {pendiente && editable && (
                  <div className="form-group">
                    <label className="form-label" htmlFor={`respuesta-observacion-${observacion.id}`}>
                      Respuesta
                    </label>
                    <textarea
                      id={`respuesta-observacion-${observacion.id}`}
                      className={`form-control ${errorRespuesta ? 'is-invalid' : ''}`}
                      value={respuesta}
                      placeholder="Describa la corrección realizada para atender esta observación."
                      aria-invalid={errorRespuesta}
                      aria-describedby={errorRespuesta ? `respuesta-observacion-${observacion.id}-error` : undefined}
                      onChange={(event) => setRespuestas((actuales) => ({
                        ...actuales,
                        [observacion.id]: event.target.value,
                      }))}
                    />
                    {errorRespuesta && (
                      <span id={`respuesta-observacion-${observacion.id}-error`} className="form-error">
                        La respuesta es obligatoria.
                      </span>
                    )}
                    <button
                      className="btn btn-outline"
                      type="button"
                      disabled={atender.isPending}
                      onClick={() => {
                        const normalizada = respuesta.trim()
                        if (!normalizada) {
                          setRespuestas((actuales) => ({ ...actuales, [observacion.id]: '' }))
                          return
                        }
                        atender.mutate({ observacionId: observacion.id, respuesta: normalizada })
                      }}
                    >
                      Marcar como atendida
                    </button>
                  </div>
                )}
              </article>
            )
          })}
        </section>
      )}

      {modalFinalizarAbierto && (
        <FinalizarElaboracionModal
          convenioId={id}
          valores={valoresFinalizacion}
          onCerrar={() => setModalFinalizarAbierto(false)}
          onErrorValidacion={(error) => setErrores(erroresServidor(error))}
          onFinalizado={() => Promise.all([
            queryClient.invalidateQueries({ queryKey: ['convenio', id] }),
            queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] }),
          ])}
        />
      )}

      <section className="card">
        <h2>Contraparte</h2>
        {datos.aliado ? (
          <dl>
            <dt>Aliado</dt>
            <dd>
              <Link to={`/aliados/${datos.aliado.id}`}>{datos.aliado.nombre}</Link> ({datos.aliado.identificacion})
            </dd>
          </dl>
        ) : (
          <dl>
            <dt>Nombre propuesto</dt>
            <dd>{solicitud.nombre_aliado_propuesto ?? '—'}</dd>
            <dt>Tipo</dt>
            <dd>{etiquetaTipoAliado(solicitud.tipo_aliado_propuesto)}</dd>
            <dt>Identificación</dt>
            <dd>{solicitud.identificacion_aliado_propuesto ?? '—'}</dd>
            <dt>Correo</dt>
            <dd>{solicitud.correo_aliado_propuesto ?? '—'}</dd>
            <dt>País / Ciudad</dt>
            <dd>{[solicitud.pais_aliado_propuesto, solicitud.ciudad_aliado_propuesto].filter(Boolean).join(' / ') || '—'}</dd>
          </dl>
        )}
        <h3>Contacto de la contraparte</h3>
        <dl>
          <dt>Nombre</dt>
          <dd>{solicitud.contacto_contraparte_nombre ?? '—'}</dd>
          <dt>Cargo</dt>
          <dd>{solicitud.contacto_contraparte_cargo ?? '—'}</dd>
          <dt>Teléfono</dt>
          <dd>{solicitud.contacto_contraparte_telefono ?? '—'}</dd>
          <dt>Correo</dt>
          <dd>{solicitud.contacto_contraparte_correo ?? '—'}</dd>
        </dl>
      </section>

      <section className="card">
        <h2>Solicitud de origen (solo lectura)</h2>
        <p className="section-help">
          Esta información proviene de la solicitud {solicitud.consecutivo} y no se modifica desde la elaboración del convenio.
        </p>
        <dl>
          <dt>Estado de la solicitud</dt>
          <dd>{solicitud.estado}</dd>
          <dt>Radicada el</dt>
          <dd>{fecha(solicitud.fecha_radicacion)}</dd>
          <dt>Solicitante</dt>
          <dd>{solicitud.solicitante_nombre ?? '—'} ({solicitud.solicitante_correo ?? '—'})</dd>
          <dt>Justificación</dt>
          <dd>{solicitud.justificacion ?? '—'}</dd>
          <dt>Actividades por parte</dt>
          <dd>{solicitud.actividades_por_parte ?? '—'}</dd>
          <dt>Metas esperadas</dt>
          <dd>{solicitud.metas_esperadas ?? '—'}</dd>
          <dt>Vigencia estimada</dt>
          <dd>{solicitud.vigencia_estimada ?? '—'}</dd>
          <dt>Requisitos de renovación</dt>
          <dd>{solicitud.requisitos_renovacion ?? '—'}</dd>
          <dt>Observaciones</dt>
          <dd>{solicitud.observaciones ?? '—'}</dd>
        </dl>

        <h3>Supervisor USB</h3>
        <dl>
          <dt>Nombre</dt>
          <dd>{solicitud.supervisor_usb_nombre ?? '—'}</dd>
          <dt>Cargo</dt>
          <dd>{solicitud.supervisor_usb_cargo ?? '—'}</dd>
          <dt>Teléfono</dt>
          <dd>{solicitud.supervisor_usb_telefono ?? '—'}</dd>
          <dt>Correo</dt>
          <dd>{solicitud.supervisor_usb_correo ?? '—'}</dd>
        </dl>

        <h3>Supervisor de la contraparte</h3>
        <dl>
          <dt>Nombre</dt>
          <dd>{solicitud.supervisor_contraparte_nombre ?? '—'}</dd>
          <dt>Cargo</dt>
          <dd>{solicitud.supervisor_contraparte_cargo ?? '—'}</dd>
          <dt>Teléfono</dt>
          <dd>{solicitud.supervisor_contraparte_telefono ?? '—'}</dd>
          <dt>Correo</dt>
          <dd>{solicitud.supervisor_contraparte_correo ?? '—'}</dd>
        </dl>
      </section>

      <div className="page-toolbar">
        <Link className="btn btn-outline" to={`/convenios/${datos.id}`}>Volver al convenio</Link>
      </div>
    </>
  )
}
