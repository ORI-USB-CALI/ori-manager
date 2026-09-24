import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import {
  ETIQUETA_TIPO,
  type ElaboracionConvenio,
  type TipoAliado,
  useElaboracionConvenio,
  useUnidadesOrganizacionales,
  useValidacionElaboracion,
} from './epica02'
import { FinalizarElaboracionModal } from './FinalizarElaboracionModal'

const CODIGO_ETAPA_ELABORACION = 'ELABORACION'
const CAMPOS_FORMULARIO = [
  'objeto',
  'alcance',
  'unidad_organizacional_id',
  'implicacion_financiera',
  'duracion_meses',
  'fecha_inicio',
  'fecha_vencimiento',
] as const

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
  return {}
}

function camposModificados(formulario: HTMLFormElement, original: ElaboracionConvenio): Record<string, string | number | null> {
  const form = new FormData(formulario)
  const cambios: Record<string, string | number | null> = {}

  for (const campo of CAMPOS_FORMULARIO) {
    if (!form.has(campo)) continue
    const bruto = String(form.get(campo) ?? '').trim()
    let valor: string | number | null = bruto || null
    if (campo === 'unidad_organizacional_id' || campo === 'duracion_meses') {
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
  const validacion = useValidacionElaboracion(id)
  const unidades = useUnidadesOrganizacionales()
  const { puede } = useSesion()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const formRef = useRef<HTMLFormElement>(null)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [alcanceSeleccionado, setAlcanceSeleccionado] = useState<string | null>(null)
  const [modalFinalizarAbierto, setModalFinalizarAbierto] = useState(false)

  const guardar = useMutation({
    mutationFn: (cambios: Record<string, unknown>) =>
      apiFetch<ElaboracionConvenio>(`/convenios/${id}`, { method: 'PATCH', body: JSON.stringify(cambios) }),
    onSuccess: async () => {
      setErrores({})
      notify({ type: 'success', message: 'Avance guardado. El convenio permanece en Elaboración.' })
      await queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] })
    },
    onError: (error) => {
      setErrores(erroresServidor(error))
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible guardar el avance.' })
    },
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
  const faltantes = Object.fromEntries((validacion.data?.faltantes ?? []).map((item) => [item.campo, item.motivo]))
  const puedeFinalizar = editable && validacion.data?.completo === true

  function mensajeCampo(campo: string) {
    return errores[campo] || faltantes[campo]
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
            <label className="form-group">
              <span className="form-label">Tipo de convenio</span>
              <select className={`form-control select ${mensajeCampo('tipo_convenio_id') ? 'is-invalid' : ''}`} disabled defaultValue={datos.tipo_convenio_id ?? ''}>
                <option value="">{datos.tipo_convenio?.nombre ?? 'Sin definir'}</option>
              </select>
              <small className="caption">
                Pendiente de un catálogo accesible para Gestor ORI; por ahora este campo se deja deshabilitado.
              </small>
              {mensajeCampo('tipo_convenio_id') && <span className="form-error">{mensajeCampo('tipo_convenio_id')}</span>}
            </label>

            <label className="form-group form-span-2">
              <span className="form-label">Objeto {editable && '*'}</span>
              <textarea
                className={`form-control ${mensajeCampo('objeto') ? 'is-invalid' : ''}`}
                name="objeto"
                defaultValue={datos.objeto ?? ''}
                disabled={!editable}
              />
              {mensajeCampo('objeto') && <span className="form-error">{mensajeCampo('objeto')}</span>}
            </label>

            <label className="form-group">
              <span className="form-label">Alcance {editable && '*'}</span>
              <select
                className={`form-control select ${mensajeCampo('alcance') ? 'is-invalid' : ''}`}
                name="alcance"
                defaultValue={datos.alcance ?? ''}
                disabled={!editable}
                onChange={(event) => setAlcanceSeleccionado(event.target.value)}
              >
                <option value="">Seleccione</option>
                <option value="INSTITUCIONAL">Institucional</option>
                <option value="PROGRAMA">Programa</option>
              </select>
              {mensajeCampo('alcance') && <span className="form-error">{mensajeCampo('alcance')}</span>}
            </label>

            {alcance === 'PROGRAMA' && (
              <label className="form-group">
                <span className="form-label">Unidad organizacional *</span>
                <select
                  className={`form-control select ${mensajeCampo('unidad_organizacional_id') ? 'is-invalid' : ''}`}
                  name="unidad_organizacional_id"
                  defaultValue={datos.unidad_organizacional_id ?? ''}
                  disabled={!editable || unidades.isPending}
                >
                  <option value="">Seleccione</option>
                  {unidades.data?.map((unidad) => (
                    <option key={unidad.id} value={unidad.id}>{unidad.nombre}</option>
                  ))}
                </select>
                {mensajeCampo('unidad_organizacional_id') && <span className="form-error">{mensajeCampo('unidad_organizacional_id')}</span>}
              </label>
            )}

            <label className="form-group form-span-2">
              <span className="form-label">Implicación financiera {editable && '*'}</span>
              <textarea
                className={`form-control ${mensajeCampo('implicacion_financiera') ? 'is-invalid' : ''}`}
                name="implicacion_financiera"
                defaultValue={datos.implicacion_financiera ?? ''}
                disabled={!editable}
              />
              {mensajeCampo('implicacion_financiera') && <span className="form-error">{mensajeCampo('implicacion_financiera')}</span>}
            </label>

            <label className="form-group">
              <span className="form-label">Duración (meses) {editable && '*'}</span>
              <input
                className={`form-control ${mensajeCampo('duracion_meses') ? 'is-invalid' : ''}`}
                name="duracion_meses"
                type="number"
                min={0}
                defaultValue={datos.duracion_meses ?? ''}
                disabled={!editable}
              />
              {mensajeCampo('duracion_meses') && <span className="form-error">{mensajeCampo('duracion_meses')}</span>}
            </label>

            <label className="form-group">
              <span className="form-label">Fecha de inicio</span>
              <input
                className={`form-control ${mensajeCampo('fecha_inicio') ? 'is-invalid' : ''}`}
                name="fecha_inicio"
                type="date"
                defaultValue={fechaInput(datos.fecha_inicio)}
                disabled={!editable}
              />
              {mensajeCampo('fecha_inicio') && <span className="form-error">{mensajeCampo('fecha_inicio')}</span>}
            </label>

            <label className="form-group">
              <span className="form-label">Fecha de vencimiento</span>
              <input
                className={`form-control ${mensajeCampo('fecha_vencimiento') ? 'is-invalid' : ''}`}
                name="fecha_vencimiento"
                type="date"
                defaultValue={fechaInput(datos.fecha_vencimiento)}
                disabled={!editable}
              />
              {mensajeCampo('fecha_vencimiento') && <span className="form-error">{mensajeCampo('fecha_vencimiento')}</span>}
            </label>
          </div>

          {editable && validacion.data && !validacion.data.completo && (
            <p className="alert-error">
              Faltan {validacion.data.faltantes.length} campo(s) para poder finalizar la elaboración y enviarla a revisión jurídica.
            </p>
          )}

          {editable && (
            <div className="page-toolbar">
              <button className="btn btn-outline" type="submit" disabled={guardar.isPending}>
                {guardar.isPending ? 'Guardando…' : 'Guardar avance'}
              </button>
              <button
                className="btn btn-primary"
                type="button"
                disabled={!puedeFinalizar}
                title={puedeFinalizar ? undefined : 'Complete la información requerida para habilitar la finalización'}
                onClick={() => setModalFinalizarAbierto(true)}
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

      {modalFinalizarAbierto && (
        <FinalizarElaboracionModal
          convenioId={id}
          onCerrar={() => setModalFinalizarAbierto(false)}
          onFinalizado={() =>
            queryClient.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] })
          }
        />
      )}

      <section className="card">
        <h2>Historial de etapas</h2>
        <p className="section-help">
          Vista simplificada mientras no exista un endpoint de historial completo (usuario responsable y
          transiciones intermedias quedan pendientes de esa mejora en backend).
        </p>
        <dl>
          <dt>Elaboración</dt>
          <dd>Convenio creado el {fechaHora(datos.creado_en)}</dd>
          {datos.etapa_actual?.codigo !== CODIGO_ETAPA_ELABORACION && (
            <>
              <dt>{datos.etapa_actual?.nombre ?? 'Etapa actual'}</dt>
              <dd>Desde el {fechaHora(datos.actualizado_en)}</dd>
            </>
          )}
        </dl>
      </section>

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
