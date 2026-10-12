import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import { useSesion } from '../auth/sesion'

export interface HitoLineaTiempo {
  codigo: 'INICIO_ELABORACION' | 'ACTIVACION' | 'VENCIMIENTO'
  nombre: string
  fecha: string | null
  estado: 'COMPLETADO' | 'PENDIENTE' | 'PROGRAMADO'
}

const SOLO_FECHA = /^(\d{4})-(\d{2})-(\d{2})$/
const formatoFecha = new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' })
const formatoFechaHora = new Intl.DateTimeFormat('es-CO', { dateStyle: 'long', timeStyle: 'short' })

function fechaLegible(valor: string): string {
  // Una fecha sin hora se interpreta en UTC con new Date y en Colombia se vería un día antes.
  const partes = SOLO_FECHA.exec(valor)
  if (partes) return formatoFecha.format(new Date(Number(partes[1]), Number(partes[2]) - 1, Number(partes[3])))
  return formatoFechaHora.format(new Date(valor))
}

function etiquetaEstado(hito: HitoLineaTiempo): { texto: string; clase: string } {
  if (hito.estado === 'PENDIENTE') return { texto: 'Pendiente', clase: 'badge-pendiente' }
  if (hito.estado === 'PROGRAMADO') return { texto: 'Fecha futura', clase: 'badge-neutral' }
  if (hito.codigo === 'VENCIMIENTO') return { texto: 'Vencido', clase: 'badge-inactivo' }
  return { texto: 'Completado', clase: 'badge-activo' }
}

export function LineaTiempoConvenio({ convenioId }: { convenioId: number }) {
  const { puede } = useSesion()
  const autorizado = puede('convenios.ver')
  const consulta = useQuery({
    queryKey: ['convenio', convenioId, 'linea-tiempo'],
    queryFn: () => apiFetch<HitoLineaTiempo[]>(`/convenios/${convenioId}/linea-tiempo`),
    enabled: autorizado && Number.isInteger(convenioId) && convenioId > 0,
    retry: false,
  })

  if (!autorizado) return null

  return (
    <section className="card linea-tiempo-convenio" aria-labelledby="linea-tiempo-titulo">
      <h2 id="linea-tiempo-titulo">Línea de tiempo</h2>
      {consulta.isPending && <p className="estado-pagina">Cargando línea de tiempo…</p>}
      {consulta.isError && (
        <p className="alert-error" role="alert">No fue posible consultar la línea de tiempo del convenio.</p>
      )}
      {consulta.data?.length === 0 && <p className="section-help">El convenio aún no tiene hitos registrados.</p>}
      {consulta.data && consulta.data.length > 0 && (
        <ol className="timeline" aria-label="Hitos del convenio">
          {consulta.data.map((hito) => {
            const etiqueta = etiquetaEstado(hito)
            return (
              <li className={`timeline-item hito-${hito.estado.toLowerCase()}`} key={hito.codigo}>
                <p className="timeline-titulo">{hito.nombre}</p>
                <p className="timeline-fecha">
                  {hito.fecha ? <time dateTime={hito.fecha}>{fechaLegible(hito.fecha)}</time> : 'Sin fecha registrada'}
                </p>
                <span className={`badge ${etiqueta.clase}`}>{etiqueta.texto}</span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
