import type { ObservacionRevision, RevisionConvenioTrazabilidad } from '../pages/epica02'
import { formatDateTime } from './tableFormatters'

interface RondaJuridica {
  numero: number | null
  revisiones: RevisionConvenioTrazabilidad[]
}

// Las revisiones llegan en orden cronológico, así que el orden de inserción del
// Map conserva el orden de las rondas y, dentro de cada una, el de las instancias.
function agruparPorRonda(revisiones: RevisionConvenioTrazabilidad[]): RondaJuridica[] {
  const rondas = new Map<number | null, RevisionConvenioTrazabilidad[]>()
  for (const revision of revisiones) {
    if (revision.tipo !== 'JURIDICA') continue
    const grupo = rondas.get(revision.numero_ronda) ?? []
    grupo.push(revision)
    rondas.set(revision.numero_ronda, grupo)
  }
  return [...rondas.entries()].map(([numero, grupo]) => ({ numero, revisiones: grupo }))
}

function resultado(revision: RevisionConvenioTrazabilidad): { texto: string; clase: string } {
  if (revision.resultado === 'APROBADA') return { texto: 'Aprobada', clase: 'badge-activo' }
  if (revision.resultado === 'DEVUELTA') return { texto: 'Devuelta', clase: 'badge-inactivo' }
  return { texto: 'En revisión', clase: 'badge-pendiente' }
}

function ObservacionConCorreccion({ observacion }: { observacion: ObservacionRevision }) {
  const atendida = observacion.estado === 'ATENDIDA'
  return (
    <li className="observacion-correccion">
      <div className="observacion-juridica">
        <span className="etiqueta-dato">Observación</span>
        <p>{observacion.descripcion}</p>
        <p className="texto-secundario">
          {observacion.registrada_por?.nombre_completo ?? 'Revisor no identificado'} ·{' '}
          {formatDateTime(observacion.creado_en)}
        </p>
      </div>
      <span className="observacion-flecha" aria-hidden="true">→</span>
      <div className="correccion-gestor">
        <span className="etiqueta-dato">Corrección del Gestor</span>
        {observacion.respuesta ? (
          <>
            <p>{observacion.respuesta}</p>
            <p className="texto-secundario">
              {observacion.atendida_por?.nombre_completo ?? 'Gestor no identificado'} ·{' '}
              {formatDateTime(observacion.fecha_atencion)}
            </p>
          </>
        ) : (
          <p className="texto-secundario">Pendiente de atención</p>
        )}
        <span className={`badge ${atendida ? 'badge-activo' : 'badge-pendiente'}`}>
          {atendida ? 'Atendida' : 'Pendiente'}
        </span>
      </div>
    </li>
  )
}

export function ObservacionesJuridicas({ revisiones }: { revisiones: RevisionConvenioTrazabilidad[] }) {
  const rondas = agruparPorRonda(revisiones)
  const hayObservaciones = rondas.some((ronda) =>
    ronda.revisiones.some((revision) => revision.observaciones.length > 0),
  )

  return (
    <section className="card observaciones-juridicas" aria-labelledby="observaciones-juridicas-titulo">
      <h2 id="observaciones-juridicas-titulo">Observaciones jurídicas</h2>
      {!hayObservaciones && (
        <p className="texto-secundario">Este convenio no tiene observaciones jurídicas registradas.</p>
      )}
      {hayObservaciones &&
        rondas.map((ronda) => (
          <section className="ronda-juridica" key={ronda.numero ?? 'sin-ronda'}>
            <h3>{ronda.numero ? `Ronda ${ronda.numero}` : 'Revisión jurídica'}</h3>
            {ronda.revisiones.map((revision) => {
              const badge = resultado(revision)
              return (
                <article className="instancia-juridica" key={revision.id}>
                  <h4>
                    {revision.instancia_juridica
                      ? `Revisión jurídica ${revision.instancia_juridica} de 2`
                      : 'Revisión jurídica'}
                    <span className={`badge ${badge.clase}`}>{badge.texto}</span>
                  </h4>
                  {revision.observaciones.length === 0 ? (
                    <p className="texto-secundario">
                      {revision.resultado === 'APROBADA' ? 'Aprobada sin observaciones.' : 'Sin observaciones registradas.'}
                    </p>
                  ) : (
                    <ol className="observaciones-lista">
                      {revision.observaciones.map((observacion) => (
                        <ObservacionConCorreccion key={observacion.id} observacion={observacion} />
                      ))}
                    </ol>
                  )}
                </article>
              )
            })}
          </section>
        ))}
    </section>
  )
}
