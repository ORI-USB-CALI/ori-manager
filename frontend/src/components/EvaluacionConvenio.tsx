import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type FormEvent } from 'react'

import { ApiError } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import {
  CALIFICACION_MAXIMA,
  LEYENDA_CALIFICACION,
  LIMITE_OBSERVACIONES,
  OPCIONES_CALIFICACION,
  claveEvaluacion,
  erroresEvaluacion,
  mensajeErrorEvaluacion,
  registrarEvaluacion,
  useEvaluacionConvenio,
  type EvaluacionConvenio as DatosEvaluacion,
} from '../pages/evaluaciones'

interface Props {
  convenioId: number
  /** El histórico monta el bloque sin este indicador: nunca ofrece formulario. */
  permitirRegistro?: boolean
}

function fechaHora(valor: string): string {
  return new Date(valor).toLocaleString()
}

function etiquetaEstado(estado: string): string {
  return estado.toLowerCase().replaceAll('_', ' ').replace(/^./, (letra) => letra.toUpperCase())
}

function EvaluacionRegistrada({ evaluacion }: { evaluacion: DatosEvaluacion }) {
  return (
    <dl className="proyecto-datos">
      <dt>Fue funcional</dt>
      <dd>
        <span className={`badge ${evaluacion.fue_funcional ? 'badge-activo' : 'badge-inactivo'}`}>
          {evaluacion.fue_funcional ? 'Sí' : 'No'}
        </span>
      </dd>
      <dt>Calificación de cumplimiento</dt>
      <dd>
        {evaluacion.calificacion} de {CALIFICACION_MAXIMA}
        <br />
        <span className="texto-secundario">{LEYENDA_CALIFICACION}</span>
      </dd>
      <dt>Comentarios sobre la experiencia</dt>
      <dd>{evaluacion.observaciones}</dd>
      <dt>Registrada por</dt>
      <dd>{evaluacion.evaluado_por.nombre_completo}</dd>
      <dt>Fecha de registro</dt>
      <dd>{fechaHora(evaluacion.creado_en)}</dd>
    </dl>
  )
}

export function EvaluacionConvenio({ convenioId, permitirRegistro = false }: Props) {
  const { puede } = useSesion()
  const puedeVer = puede('convenios.ver')
  const puedeEvaluar = puede('convenios.evaluar')
  const consulta = useEvaluacionConvenio(convenioId, puedeVer)
  const cliente = useQueryClient()
  const notify = useNotifications()
  const formularioRef = useRef<HTMLFormElement>(null)
  const enviando = useRef(false)
  const [errores, setErrores] = useState<Record<string, string>>({})

  const registro = useMutation({
    mutationFn: async () => {
      const formulario = formularioRef.current
      if (!formulario) throw new Error('No fue posible leer el formulario.')
      const valores = new FormData(formulario)
      const funcional = String(valores.get('fue_funcional') ?? '')
      const calificacion = String(valores.get('calificacion') ?? '')
      const observaciones = String(valores.get('observaciones') ?? '').trim()

      const locales: Record<string, string> = {}
      if (funcional !== 'SI' && funcional !== 'NO') {
        locales.fue_funcional = 'Indica si el convenio fue funcional'
      }
      if (!/^(?:[1-9]|10)$/.test(calificacion)) {
        locales.calificacion = `Selecciona una calificación de 1 a ${CALIFICACION_MAXIMA}`
      }
      if (!observaciones) {
        locales.observaciones = 'Los comentarios sobre la experiencia son obligatorios'
      } else if (observaciones.length > LIMITE_OBSERVACIONES) {
        locales.observaciones = `Los comentarios admiten máximo ${LIMITE_OBSERVACIONES} caracteres`
      }
      setErrores(locales)
      if (Object.keys(locales).length > 0) throw new Error('Revisa los campos marcados.')

      return registrarEvaluacion(convenioId, {
        fue_funcional: funcional === 'SI',
        calificacion: Number(calificacion),
        observaciones,
      })
    },
    onSuccess: async () => {
      setErrores({})
      formularioRef.current?.reset()
      notify({ type: 'success', message: 'La evaluación del convenio quedó registrada.' })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: claveEvaluacion(convenioId) }),
        cliente.invalidateQueries({ queryKey: ['convenio', convenioId] }),
        cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'historial'] }),
      ])
    },
    onError: async (error) => {
      setErrores((actuales) => ({ ...actuales, ...erroresEvaluacion(error) }))
      notify({ type: 'error', message: mensajeErrorEvaluacion(error) })
      // Solo un error del servidor justifica reconsultar: una validación local no
      // cambió nada en la BD.
      if (error instanceof ApiError) {
        await cliente.invalidateQueries({ queryKey: claveEvaluacion(convenioId) })
      }
    },
    onSettled: () => { enviando.current = false },
    retry: false,
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!puedeEvaluar || enviando.current || registro.isPending) return
    enviando.current = true
    registro.mutate()
  }

  if (!puedeVer || !Number.isInteger(convenioId) || convenioId <= 0) return null
  if (consulta.isPending) return <p className="estado-pagina">Cargando evaluación del convenio…</p>
  // El historial también lo consulta quien ya no tiene acceso operativo al
  // convenio (HU-21): para esa persona no hay evaluación que mostrar.
  if (consulta.error instanceof ApiError && consulta.error.status === 404) return null
  if (consulta.isError || !consulta.data) {
    return (
      <p className="alert-error" role="alert">
        {mensajeErrorEvaluacion(consulta.error)}
      </p>
    )
  }

  const { evaluable, estado_convenio: estadoConvenio, evaluacion } = consulta.data

  if (evaluacion) {
    return (
      <section className="card" aria-labelledby="evaluacion-convenio-titulo">
        <h2 id="evaluacion-convenio-titulo">Evaluación del convenio</h2>
        <p className="section-help">La evaluación registrada es definitiva y queda en el histórico del convenio.</p>
        <EvaluacionRegistrada evaluacion={evaluacion} />
      </section>
    )
  }

  // Sin evaluación registrada, el bloque solo aporta a quien puede evaluar: a los
  // demás les hablaría de una acción que nunca podrán ejecutar.
  if (!puedeEvaluar) return null

  if (!evaluable) {
    return (
      <section className="card" aria-labelledby="evaluacion-convenio-titulo">
        <h2 id="evaluacion-convenio-titulo">Evaluación del convenio</h2>
        <p className="section-help">
          Este convenio todavía no admite evaluación. Estado actual: {etiquetaEstado(estadoConvenio)}.
        </p>
      </section>
    )
  }

  if (!permitirRegistro) {
    return (
      <section className="card" aria-labelledby="evaluacion-convenio-titulo">
        <h2 id="evaluacion-convenio-titulo">Evaluación del convenio</h2>
        <p className="section-help">Este convenio aún no tiene una evaluación registrada.</p>
      </section>
    )
  }

  return (
    <section className="card" aria-labelledby="evaluacion-convenio-titulo">
      <h2 id="evaluacion-convenio-titulo">Evaluación del convenio</h2>
      <p className="section-help">
        Registra si el convenio fue funcional, su calificación de cumplimiento y los comentarios sobre la
        experiencia. La evaluación se guarda una sola vez y no puede modificarse.
      </p>
      <form ref={formularioRef} onSubmit={enviar} noValidate>
        <label className="form-group" htmlFor="evaluacion-fue-funcional">
          <span className="form-label">¿El convenio fue funcional? *</span>
          <select
            id="evaluacion-fue-funcional"
            name="fue_funcional"
            className={`form-control ${errores.fue_funcional ? 'is-invalid' : ''}`}
            defaultValue=""
            aria-invalid={Boolean(errores.fue_funcional)}
            aria-describedby={errores.fue_funcional ? 'evaluacion-fue-funcional-error' : undefined}
          >
            <option value="">Seleccione una opción</option>
            <option value="SI">Sí</option>
            <option value="NO">No</option>
          </select>
          {errores.fue_funcional && (
            <span id="evaluacion-fue-funcional-error" className="form-error">{errores.fue_funcional}</span>
          )}
        </label>

        <label className="form-group" htmlFor="evaluacion-calificacion">
          <span className="form-label">Calificación de cumplimiento *</span>
          <select
            id="evaluacion-calificacion"
            name="calificacion"
            className={`form-control ${errores.calificacion ? 'is-invalid' : ''}`}
            defaultValue=""
            aria-invalid={Boolean(errores.calificacion)}
            // La leyenda de RN-08 debe seguir anunciándose cuando hay error, no ser reemplazada por él.
            aria-describedby={
              [
                'evaluacion-calificacion-ayuda',
                errores.calificacion ? 'evaluacion-calificacion-error' : null,
              ]
                .filter(Boolean)
                .join(' ')
            }
          >
            <option value="">Seleccione una calificación</option>
            {OPCIONES_CALIFICACION.map((valor) => (
              <option key={valor} value={valor}>{valor}</option>
            ))}
          </select>
          <span id="evaluacion-calificacion-ayuda" className="form-help">{LEYENDA_CALIFICACION}</span>
          {errores.calificacion && (
            <span id="evaluacion-calificacion-error" className="form-error">{errores.calificacion}</span>
          )}
        </label>

        <label className="form-group" htmlFor="evaluacion-observaciones">
          <span className="form-label">Comentarios sobre la experiencia *</span>
          <textarea
            id="evaluacion-observaciones"
            name="observaciones"
            className={`form-control ${errores.observaciones ? 'is-invalid' : ''}`}
            rows={5}
            maxLength={LIMITE_OBSERVACIONES}
            aria-invalid={Boolean(errores.observaciones)}
            aria-describedby={errores.observaciones ? 'evaluacion-observaciones-error' : undefined}
          />
          {errores.observaciones && (
            <span id="evaluacion-observaciones-error" className="form-error">{errores.observaciones}</span>
          )}
        </label>

        <div className="page-toolbar">
          <button className="btn btn-primary" type="submit" disabled={registro.isPending}>
            {registro.isPending ? 'Registrando…' : 'Registrar evaluación'}
          </button>
        </div>
      </form>
    </section>
  )
}
