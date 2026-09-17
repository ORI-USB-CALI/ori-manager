import { ESTADO_CONVENIO_ETIQUETA, type EstadoConvenio } from '../../features/aliados/types'

// Adaptado de feature/InterfazPerfilDetalleAliado a los enums en minúscula
// del backend de esta rama. La clase CSS es el estado con '_' → '-'.

interface ConvenioBadgeProps {
  estado: EstadoConvenio
}

export function ConvenioBadge({ estado }: ConvenioBadgeProps) {
  return (
    <span className={`badge badge-${estado.replace('_', '-')}`}>
      {ESTADO_CONVENIO_ETIQUETA[estado]}
    </span>
  )
}
