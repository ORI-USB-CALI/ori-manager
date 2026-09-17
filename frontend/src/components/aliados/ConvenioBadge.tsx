import type { EstadoConvenio } from '../../types/aliado'

interface ConvenioBadgeProps {
  estado: EstadoConvenio
}

export function ConvenioBadge({ estado }: ConvenioBadgeProps) {
  const getBadgeClass = (st: EstadoConvenio) => {
    switch (st) {
      case 'VIGENTE':
        return 'badge badge-vigente'
      case 'EN_TRAMITE':
        return 'badge badge-en-tramite'
      case 'FINALIZADO':
        return 'badge badge-finalizado'
      case 'VENCIDO':
        return 'badge badge-vencido'
      case 'CANCELADO':
        return 'badge badge-cancelado'
      default:
        return 'badge'
    }
  }

  const getLabel = (st: EstadoConvenio) => {
    switch (st) {
      case 'VIGENTE':
        return 'Vigente'
      case 'EN_TRAMITE':
        return 'En Trámite'
      case 'FINALIZADO':
        return 'Finalizado'
      case 'VENCIDO':
        return 'Vencido'
      case 'CANCELADO':
        return 'Cancelado'
      default:
        return st
    }
  }

  return <span className={getBadgeClass(estado)}>{getLabel(estado)}</span>
}
