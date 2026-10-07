import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { ConfirmacionModal } from '../components/ConfirmacionModal'
import {
  CLAVE_RENOVACIONES,
  diasRestantes,
  formatearFechaConvenio,
  iniciarRenovacion,
  mensajeErrorAccion,
  registrarNoRenovacion,
  useSeguimientoRenovaciones,
  type EstadoSeguimientoRenovacion,
  type SeguimientoRenovacion,
} from './renovaciones'

const VISTAS: Record<EstadoSeguimientoRenovacion, {
  titulo: string
  etiqueta: string
  variante: string
  vacio: string
}> = {
  PENDIENTE_DE_DECISION: {
    titulo: 'Pendientes', etiqueta: 'Pendiente de decisión', variante: 'warning',
    vacio: 'No hay convenios pendientes de decisión de renovación.',
  },
  RENOVACION_INICIADA: {
    titulo: 'Renovación iniciada', etiqueta: 'Renovación iniciada', variante: 'info',
    vacio: 'No hay renovaciones en proceso.',
  },
  NO_SE_RENOVARA: {
    titulo: 'No se renovará', etiqueta: 'No se renovará', variante: 'neutral',
    vacio: 'No hay decisiones de no renovación registradas.',
  },
}

interface Accion {
  tipo: 'iniciar' | 'no-renovar'
  convenio: SeguimientoRenovacion
}

function identificacion(convenio: SeguimientoRenovacion) {
  return convenio.codigo?.trim() || `Convenio #${convenio.convenio_id}`
}

export function RenovacionesPage() {
  const { puede } = useSesion()
  const autorizado = puede('convenios.gestionar_renovaciones')
  const consulta = useSeguimientoRenovaciones(autorizado)
  const cliente = useQueryClient()
  const notify = useNotifications()
  const [estado, setEstado] = useState<EstadoSeguimientoRenovacion>('PENDIENTE_DE_DECISION')
  const [accion, setAccion] = useState<Accion | null>(null)
  const enviando = useRef(false)
  const mutacion = useMutation({
    mutationFn: async ({ tipo, convenio }: Accion) => {
      if (tipo === 'iniciar') {
        return { tipo: 'iniciar' as const, datos: await iniciarRenovacion(convenio.convenio_id) }
      }
      return { tipo: 'no-renovar' as const, datos: await registrarNoRenovacion(convenio.convenio_id) }
    },
    onSuccess: async (resultado) => {
      setAccion(null)
      setEstado(resultado.tipo === 'iniciar' ? 'RENOVACION_INICIADA' : 'NO_SE_RENOVARA')
      notify({
        type: 'success',
        message: resultado.tipo === 'iniciar'
          ? 'La nueva elaboración de renovación se ha iniciado.'
          : 'Se ha registrado la decisión de no renovar.',
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: CLAVE_RENOVACIONES }),
        cliente.invalidateQueries({ queryKey: ['convenios', 'tablero'] }),
      ])
    },
    onError: async (error, variables) => {
      notify({ type: 'error', message: mensajeErrorAccion(error, variables.tipo) })
      setAccion(null)
      await cliente.invalidateQueries({ queryKey: CLAVE_RENOVACIONES })
    },
    onSettled: () => { enviando.current = false },
    retry: false,
  })

  function confirmar() {
    if (!accion || !autorizado || enviando.current || mutacion.isPending) return
    enviando.current = true
    mutacion.mutate(accion)
  }

  if (!autorizado) return null

  const registros = consulta.data ?? []
  const visibles = registros.filter((item) => item.estado_seguimiento === estado)
  const vista = VISTAS[estado]
  const ultima = mutacion.data

  return (
    <>
      <section className="header-banner">
        <h1>Panel de renovaciones</h1>
        <p>Decide la continuidad de los convenios y consulta las renovaciones en proceso.</p>
      </section>

      <nav className="renovaciones-filtros" aria-label="Estado del seguimiento de renovación">
        {(Object.keys(VISTAS) as EstadoSeguimientoRenovacion[]).map((valor) => (
          <button
            key={valor}
            type="button"
            className={`btn ${estado === valor ? 'btn-primary' : 'btn-outline'}`}
            aria-pressed={estado === valor}
            onClick={() => setEstado(valor)}
          >
            {VISTAS[valor].titulo}
            {consulta.data && <span className="badge badge-neutral">{registros.filter((item) => item.estado_seguimiento === valor).length}</span>}
          </button>
        ))}
      </nav>

      {ultima?.tipo === 'iniciar' && (
        <div className="alert-success renovaciones-resultado" role="status">
          <p>La nueva elaboración está disponible.</p>
          <Link className="btn btn-outline btn-small" to={`/convenios/${ultima.datos.convenio_renovacion_id}`}>Ver renovación creada</Link>
        </div>
      )}

      {consulta.isPending && <p className="estado-pagina" role="status">Cargando seguimiento de renovaciones…</p>}
      {consulta.isError && (
        <section className="alert-error" role="alert">
          <p>No se pudo consultar el panel de renovaciones.</p>
          <button className="btn btn-outline btn-small" type="button" disabled={consulta.isFetching} onClick={() => { void consulta.refetch() }}>
            {consulta.isFetching ? 'Consultando…' : 'Reintentar'}
          </button>
        </section>
      )}
      {consulta.isFetching && !consulta.isPending && !consulta.isError && (
        <p className="section-help" role="status">Actualizando seguimiento…</p>
      )}

      {!consulta.isPending && !consulta.isError && (
        <section aria-label={vista.titulo} aria-busy={consulta.isFetching}>
          <h2 className="renovaciones-titulo">{vista.titulo}</h2>
          {visibles.length === 0 ? (
            <div className="card estado-vacio"><p>{vista.vacio}</p></div>
          ) : (
            <ul className="renovaciones-lista">
              {visibles.map((convenio) => {
                const iniciada = convenio.estado_seguimiento === 'RENOVACION_INICIADA'
                const pendiente = convenio.estado_seguimiento === 'PENDIENTE_DE_DECISION'
                const configuracion = VISTAS[convenio.estado_seguimiento]
                return (
                  <li key={convenio.convenio_id}>
                    <article className="card renovacion-tarjeta">
                      <header className="renovacion-cabecera">
                        <h3>{identificacion(convenio)}</h3>
                        <span className={`badge badge-${configuracion.variante}`}>{configuracion.etiqueta}</span>
                      </header>
                      {convenio.objeto?.trim() && <p className="renovacion-objeto">{convenio.objeto}</p>}
                      <dl className="renovacion-datos">
                        <div><dt>Aliado</dt><dd>{convenio.aliado?.trim() || 'Sin aliado registrado'}</dd></div>
                        {convenio.tipo_convenio && <div><dt>Tipo de convenio</dt><dd>{convenio.tipo_convenio}</dd></div>}
                        <div><dt>Fecha de inicio</dt><dd>{formatearFechaConvenio(convenio.fecha_inicio)}</dd></div>
                        <div><dt>{iniciada ? 'Vencimiento del convenio original' : 'Fecha de vencimiento'}</dt><dd>{formatearFechaConvenio(convenio.fecha_vencimiento)}</dd></div>
                        {pendiente && <div><dt>Vigencia restante</dt><dd>{diasRestantes(convenio.fecha_vencimiento) ?? 'Sin fecha registrada'}</dd></div>}
                        {iniciada && convenio.numero_renovacion !== null && <div><dt>Número de renovación</dt><dd>{convenio.numero_renovacion}</dd></div>}
                        {iniciada && convenio.etapa_renovacion && <div><dt>Etapa de la renovación</dt><dd>{convenio.etapa_renovacion}</dd></div>}
                        {iniciada && convenio.codigo_renovacion && <div><dt>Código de la renovación</dt><dd>{convenio.codigo_renovacion}</dd></div>}
                      </dl>
                      <section className="renovacion-evaluacion" aria-label={`Evaluación de ${identificacion(convenio)}`}>
                        <h4>Evaluación</h4>
                        <p>Sin evaluación disponible</p>
                      </section>
                      <footer className="renovacion-acciones">
                        <Link className="btn btn-outline btn-small" to={`/convenios/${convenio.convenio_id}`}>
                          {iniciada ? 'Ver convenio original' : 'Ver convenio'}
                        </Link>
                        {iniciada ? (
                          convenio.convenio_renovacion_id !== null && (
                            <Link className="btn btn-primary btn-small" to={`/convenios/${convenio.convenio_renovacion_id}`}>Ver renovación</Link>
                          )
                        ) : (
                          <>
                            <button type="button" className="btn btn-primary btn-small" disabled={mutacion.isPending} onClick={() => setAccion({ tipo: 'iniciar', convenio })}>Iniciar renovación</button>
                            {pendiente && <button type="button" className="btn btn-outline btn-small" disabled={mutacion.isPending} onClick={() => setAccion({ tipo: 'no-renovar', convenio })}>No se renovará</button>}
                          </>
                        )}
                      </footer>
                    </article>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      )}

      {accion && (
        <ConfirmacionModal
          titulo={accion.tipo === 'iniciar' ? 'Iniciar renovación' : 'Confirmar decisión de no renovar'}
          confirmar={accion.tipo === 'iniciar' ? 'Iniciar renovación' : 'Confirmar: no se renovará'}
          procesando="Registrando…"
          pendiente={mutacion.isPending}
          onConfirmar={confirmar}
          onCerrar={() => setAccion(null)}
        >
          <h3>{identificacion(accion.convenio)}</h3>
          <p>{accion.tipo === 'iniciar'
            ? 'Se iniciará una nueva elaboración de convenio usando como base el documento vigente del convenio actual. ¿Deseas continuar?'
            : 'El convenio dejará de aparecer como pendiente de decisión. Esta decisión no modifica el convenio actual.'}</p>
          {accion.tipo === 'no-renovar' && <small>La decisión se conservará en el histórico. Podrás iniciar una renovación posteriormente.</small>}
        </ConfirmacionModal>
      )}
    </>
  )
}
