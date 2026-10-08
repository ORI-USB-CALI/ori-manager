import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { ConfirmacionModal } from '../components/ConfirmacionModal'
import { CLAVE_ALERTAS_VENCIMIENTO } from './alertasVencimiento'
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

function esEstadoSeguimiento(valor: string | null): valor is EstadoSeguimientoRenovacion {
  return valor !== null && Object.hasOwn(VISTAS, valor)
}

export function RenovacionesPage() {
  const { puede } = useSesion()
  const autorizado = puede('convenios.gestionar_renovaciones')
  const consulta = useSeguimientoRenovaciones(autorizado)
  const cliente = useQueryClient()
  const notify = useNotifications()
  const [parametros, setParametros] = useSearchParams()
  const estadoUrl = parametros.get('estado')
  const estado = esEstadoSeguimiento(estadoUrl) ? estadoUrl : 'PENDIENTE_DE_DECISION'
  const idUrl = parametros.get('convenio_id')
  const convenioId = idUrl !== null && /^\d+$/.test(idUrl)
    && Number.isSafeInteger(Number(idUrl)) && Number(idUrl) > 0 ? Number(idUrl) : null
  const [accion, setAccion] = useState<Accion | null>(null)
  const enviando = useRef(false)
  const filaSolicitada = useRef<HTMLTableRowElement>(null)
  const convenioSolicitado = consulta.data?.find((item) => item.convenio_id === convenioId)

  function cambiarEstado(nuevoEstado: EstadoSeguimientoRenovacion, id?: number) {
    setParametros((actuales) => {
      const siguientes = new URLSearchParams(actuales)
      siguientes.set('estado', nuevoEstado)
      if (id !== undefined) siguientes.set('convenio_id', String(id))
      return siguientes
    })
  }

  useEffect(() => {
    if (!autorizado || consulta.isPending || consulta.isError || consulta.isFetching
      || convenioSolicitado?.estado_seguimiento !== estado) return
    filaSolicitada.current?.scrollIntoView({ block: 'center', inline: 'nearest' })
    filaSolicitada.current?.focus({ preventScroll: true })
  }, [autorizado, consulta.isPending, consulta.isError, consulta.isFetching,
    convenioSolicitado?.convenio_id, convenioSolicitado?.estado_seguimiento, estado])

  const mutacion = useMutation({
    mutationFn: async ({ tipo, convenio }: Accion) => {
      if (tipo === 'iniciar') {
        return { tipo: 'iniciar' as const, datos: await iniciarRenovacion(convenio.convenio_id) }
      }
      return { tipo: 'no-renovar' as const, datos: await registrarNoRenovacion(convenio.convenio_id) }
    },
    onSuccess: async (resultado, variables) => {
      setAccion(null)
      cambiarEstado(resultado.tipo === 'iniciar' ? 'RENOVACION_INICIADA' : 'NO_SE_RENOVARA', variables.convenio.convenio_id)
      notify({
        type: 'success',
        message: resultado.tipo === 'iniciar'
          ? 'La nueva elaboración de renovación se ha iniciado.'
          : 'Se ha registrado la decisión de no renovar.',
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: CLAVE_RENOVACIONES }),
        cliente.invalidateQueries({ queryKey: ['convenios', 'tablero'] }),
        cliente.invalidateQueries({ queryKey: CLAVE_ALERTAS_VENCIMIENTO }),
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
  const mostrarTipo = visibles.some((item) => item.tipo_convenio?.trim())
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
            onClick={() => cambiarEstado(valor)}
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
          {!consulta.isFetching && idUrl !== null && (
            <div className="card renovaciones-destino" role="status">
              {convenioId === null ? (
                <p>El identificador del convenio solicitado no es válido.</p>
              ) : !convenioSolicitado ? (
                <p>El convenio #{convenioId} no está disponible en el seguimiento de renovaciones.</p>
              ) : convenioSolicitado.estado_seguimiento !== estado ? (
                <>
                  <p>{identificacion(convenioSolicitado)} se encuentra en «{VISTAS[convenioSolicitado.estado_seguimiento].etiqueta}».</p>
                  <button className="btn btn-outline btn-small" type="button" onClick={() => cambiarEstado(convenioSolicitado.estado_seguimiento, convenioSolicitado.convenio_id)}>
                    Ir a {VISTAS[convenioSolicitado.estado_seguimiento].titulo}
                  </button>
                </>
              ) : <p>Convenio solicitado: {identificacion(convenioSolicitado)}. Su fila está identificada en la tabla.</p>}
            </div>
          )}
          {visibles.length === 0 ? (
            <div className="card estado-vacio"><p>{vista.vacio}</p></div>
          ) : (
            <div className="table-container" role="region" aria-label={`Tabla de renovaciones: ${vista.titulo}`} tabIndex={0}>
              <table className="table renovaciones-tabla">
                <thead>
                  <tr>
                    <th scope="col">Convenio</th>
                    <th scope="col">Aliado</th>
                    <th scope="col">Objeto</th>
                    {mostrarTipo && <th scope="col">Tipo de convenio</th>}
                    <th scope="col">Fecha de vencimiento</th>
                    <th scope="col">Estado contractual</th>
                    <th scope="col">Estado del seguimiento</th>
                    <th scope="col">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((convenio) => {
                    const iniciada = convenio.estado_seguimiento === 'RENOVACION_INICIADA'
                    const pendiente = convenio.estado_seguimiento === 'PENDIENTE_DE_DECISION'
                    const configuracion = VISTAS[convenio.estado_seguimiento]
                    const destacado = convenio.convenio_id === convenioId
                    return (
                      <tr
                        key={convenio.convenio_id}
                        ref={destacado ? filaSolicitada : undefined}
                        className={destacado ? 'renovacion-destacada' : undefined}
                        tabIndex={destacado ? -1 : undefined}
                        aria-current={destacado ? true : undefined}
                      >
                        <th scope="row">
                          {identificacion(convenio)}
                          {destacado && <small className="tabla-ayuda renovacion-identificada">Convenio solicitado</small>}
                        </th>
                        <td>{convenio.aliado?.trim() || 'Sin aliado registrado'}</td>
                        <td><span className="renovacion-objeto" title={convenio.objeto?.trim()}>{convenio.objeto?.trim() || 'Sin objeto registrado'}</span></td>
                        {mostrarTipo && <td>{convenio.tipo_convenio?.trim() || 'Sin tipo registrado'}</td>}
                        <td>
                          {formatearFechaConvenio(convenio.fecha_vencimiento)}
                          {pendiente && <small className="tabla-ayuda">{diasRestantes(convenio.fecha_vencimiento)}</small>}
                        </td>
                        <td>
                          <span
                            className={`badge badge-${convenio.estado_convenio === 'VIGENTE' ? 'success' : convenio.estado_convenio === 'POR_VENCER' ? 'warning' : convenio.estado_convenio === 'VENCIDO' ? 'danger' : 'neutral'}`}
                            aria-label={`Estado contractual: ${convenio.estado_convenio.replaceAll('_', ' ')}`}
                          >
                            {convenio.estado_convenio.replaceAll('_', ' ')}
                          </span>
                        </td>
                        <td>
                          <span className={`badge badge-${configuracion.variante}`} aria-label={`Seguimiento: ${configuracion.etiqueta}`}>{configuracion.etiqueta}</span>
                          {iniciada && <small className="tabla-ayuda">
                            {convenio.numero_renovacion !== null && `Renovación #${convenio.numero_renovacion} · `}
                            {convenio.etapa_renovacion || 'Sin etapa registrada'}
                          </small>}
                          {iniciada && convenio.codigo_renovacion && <small className="tabla-ayuda">{convenio.codigo_renovacion}</small>}
                        </td>
                        <td>
                          <div className="renovacion-acciones">
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
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
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
