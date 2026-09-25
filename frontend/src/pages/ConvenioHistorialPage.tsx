import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'

interface UsuarioResumen {
  id: number
  nombre_completo: string
  correo: string
}

interface EtapaResumen {
  id: number
  orden: number
  codigo: string
  nombre: string
}

interface ObservacionRevision {
  id: number
  origen: string
  descripcion: string
  respuesta: string | null
  estado: string
  registrada_por: UsuarioResumen
  responsable: UsuarioResumen | null
  atendida_por: UsuarioResumen | null
  fecha_atencion: string | null
  creado_en: string
}

interface RevisionConvenio {
  id: number
  tipo: string
  estado: string
  resultado: string | null
  responsable: UsuarioResumen | null
  resuelta_por: UsuarioResumen | null
  snapshot_datos: { objeto?: string | null } | null
  creado_en: string
  resuelta_en: string | null
  observaciones: ObservacionRevision[]
}

interface HistorialEtapa {
  id: number
  etapa_origen: EtapaResumen | null
  etapa_destino: EtapaResumen
  usuario: UsuarioResumen
  responsable: UsuarioResumen | null
  observacion: string | null
  fecha_cambio: string
}

interface HistorialConvenio {
  revisiones: RevisionConvenio[]
  cambios_etapa: HistorialEtapa[]
}

const ETIQUETA_TIPO_REVISION: Record<string, string> = {
  JURIDICA: 'Revisión jurídica',
  CONTRAPARTE: 'Revisión de contraparte',
  FINAL: 'Revisión final',
}

const ETIQUETA_RESULTADO: Record<string, string> = {
  APROBADA: 'Aprobada',
  DEVUELTA: 'Devuelta',
}

const ETIQUETA_ESTADO_OBSERVACION: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  ATENDIDA: 'Atendida',
}

function fechaHora(valor: string | null): string {
  if (!valor) return '—'
  return new Date(valor).toLocaleString()
}

function badgeResultado(revision: RevisionConvenio): { texto: string; clase: string } {
  if (revision.resultado === 'APROBADA') return { texto: ETIQUETA_RESULTADO.APROBADA, clase: 'badge-activo' }
  if (revision.resultado === 'DEVUELTA') return { texto: ETIQUETA_RESULTADO.DEVUELTA, clase: 'badge-inactivo' }
  return { texto: 'Pendiente', clase: 'badge-pendiente' }
}

export function ConvenioHistorialPage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const historial = useQuery({
    queryKey: ['convenio', id, 'historial'],
    queryFn: () => apiFetch<HistorialConvenio>(`/convenios/${id}/revisiones`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })

  if (historial.isPending) return <p className="estado-pagina">Cargando historial…</p>
  if (historial.isError) {
    const noEncontrado = historial.error instanceof ApiError && historial.error.status === 404
    return (
      <section className="card estado-vacio">
        <h1>{noEncontrado ? 'Convenio no encontrado' : 'No se pudo consultar el historial'}</h1>
      </section>
    )
  }

  if (!historial.data) return null
  const { revisiones, cambios_etapa: cambiosEtapa } = historial.data

  return (
    <>
      <section className="header-banner">
        <h1>Historial y trazabilidad</h1>
        <p>
          Convenio #{id} · <Link to={`/convenios/${id}`}>Volver al convenio</Link>
        </p>
      </section>

      <section className="card">
        <h2>Cambios de etapa</h2>
        {cambiosEtapa.length === 0 && <p>Aún no se han registrado cambios de etapa.</p>}
        {cambiosEtapa.length > 0 && (
          <ol className="timeline">
            {cambiosEtapa.map((cambio) => (
              <li className="timeline-item" key={cambio.id}>
                <p className="timeline-fecha">{fechaHora(cambio.fecha_cambio)}</p>
                <p className="timeline-titulo">
                  {cambio.etapa_origen ? cambio.etapa_origen.nombre : 'Registro del convenio'}
                  {' → '}
                  {cambio.etapa_destino.nombre}
                </p>
                <p className="texto-secundario">
                  Registrado por {cambio.usuario.nombre_completo}
                  {cambio.responsable && cambio.responsable.id !== cambio.usuario.id
                    ? ` · Responsable: ${cambio.responsable.nombre_completo}`
                    : ''}
                </p>
                {cambio.observacion && <p>{cambio.observacion}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="card">
        <h2>Rondas de revisión</h2>
        {revisiones.length === 0 && <p>Aún no se han registrado rondas de revisión.</p>}
        {revisiones.map((revision, indice) => {
          const badge = badgeResultado(revision)
          return (
            <article className="card timeline-revision" key={revision.id}>
              <h3>
                Ciclo {indice + 1} · {ETIQUETA_TIPO_REVISION[revision.tipo] ?? revision.tipo}{' '}
                <span className={`badge ${badge.clase}`}>{badge.texto}</span>
              </h3>
              <dl>
                <dt>Versión revisada</dt>
                <dd>{revision.snapshot_datos?.objeto ?? '—'}</dd>
                <dt>Entregada a revisión</dt>
                <dd>{fechaHora(revision.creado_en)}</dd>
                {revision.resultado && (
                  <>
                    <dt>Resuelta</dt>
                    <dd>
                      {fechaHora(revision.resuelta_en)}
                      {revision.resuelta_por ? ` · ${revision.resuelta_por.nombre_completo}` : ''}
                    </dd>
                  </>
                )}
              </dl>
              {revision.observaciones.length > 0 && (
                <div className="timeline-observaciones">
                  <h4>Observaciones</h4>
                  {revision.observaciones.map((observacion) => (
                    <div className="document-row" key={observacion.id}>
                      <p>{observacion.descripcion}</p>
                      <p className="texto-secundario">
                        Registrada por {observacion.registrada_por.nombre_completo} el{' '}
                        {fechaHora(observacion.creado_en)} ·{' '}
                        <span className={`badge ${observacion.estado === 'ATENDIDA' ? 'badge-activo' : 'badge-pendiente'}`}>
                          {ETIQUETA_ESTADO_OBSERVACION[observacion.estado] ?? observacion.estado}
                        </span>
                      </p>
                      {observacion.respuesta && <p>Respuesta: {observacion.respuesta}</p>}
                    </div>
                  ))}
                </div>
              )}
            </article>
          )
        })}
      </section>
    </>
  )
}
