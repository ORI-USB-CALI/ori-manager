import { ApiError } from '../../api/http'
import { useConvenio } from './useConvenios'

const ESTADO_LABELS: Record<string, string> = {
  EN_TRAMITE: 'En tramite',
  VIGENTE: 'Vigente',
  POR_VENCER: 'Por vencer',
  VENCIDO: 'Vencido',
  RENOVADO: 'Renovado',
  FINALIZADO: 'Finalizado',
  CANCELADO: 'Cancelado',
}

const ALCANCE_LABELS: Record<string, string> = {
  PROGRAMA: 'Programa academico especifico',
  INSTITUCIONAL: 'Toda la universidad',
}

function formatFecha(value: string | null): string {
  if (!value) {
    return 'Sin definir'
  }

  return new Date(value).toLocaleString()
}

interface ConvenioDetailProps {
  convenioId: number
}

export function ConvenioDetail({ convenioId }: ConvenioDetailProps) {
  const { data: convenio, isLoading, error } = useConvenio(convenioId)

  if (isLoading) {
    return <p>Cargando convenio...</p>
  }

  if (error) {
    const mensaje =
      error instanceof ApiError && error.status === 404
        ? `No existe un convenio con id ${convenioId}.`
        : 'No fue posible consultar el convenio.'

    return <p className="form-error">{mensaje}</p>
  }

  if (!convenio) {
    return null
  }

  return (
    <dl className="convenio-detail">
      <div className="detail-row">
        <dt>Id</dt>
        <dd>{convenio.id}</dd>
      </div>

      <div className="detail-row">
        <dt>Codigo</dt>
        <dd>{convenio.codigo ?? 'Aun no asignado'}</dd>
      </div>

      <div className="detail-row">
        <dt>Estado</dt>
        <dd>
          <span className="badge">{ESTADO_LABELS[convenio.estado] ?? convenio.estado}</span>
        </dd>
      </div>

      <div className="detail-row">
        <dt>Solicitud de origen</dt>
        <dd>#{convenio.solicitud_id}</dd>
      </div>

      <div className="detail-row">
        <dt>Aliado</dt>
        <dd>{convenio.aliado_id !== null ? `#${convenio.aliado_id}` : 'Sin aliado asociado todavia'}</dd>
      </div>

      <div className="detail-row">
        <dt>Alcance</dt>
        <dd>{convenio.alcance ? (ALCANCE_LABELS[convenio.alcance] ?? convenio.alcance) : 'Sin definir'}</dd>
      </div>

      <div className="detail-row">
        <dt>Objeto</dt>
        <dd>{convenio.objeto ?? 'Sin descripcion'}</dd>
      </div>

      <div className="detail-row">
        <dt>Responsable de creacion</dt>
        <dd>Usuario #{convenio.creado_por_id}</dd>
      </div>

      <div className="detail-row">
        <dt>Creado el</dt>
        <dd>{formatFecha(convenio.creado_en)}</dd>
      </div>

      <div className="detail-row">
        <dt>Ultima actualizacion</dt>
        <dd>{formatFecha(convenio.actualizado_en)}</dd>
      </div>
    </dl>
  )
}
