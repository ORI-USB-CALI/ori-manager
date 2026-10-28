import { Link, useLocation } from 'react-router-dom'

import { type Retorno, retornoSeguro } from './retornoVolver'

interface Props {
  /** Destino cuando la vista no recibió un contexto de origen válido. */
  alternativo: Retorno
  /** Estado que se entrega a la vista de destino (por ejemplo, para que conserve su propio retorno). */
  estado?: unknown
}

/* HT-12: única acción Volver de las vistas de convenios. Siempre va al inicio
   de la vista, antes del encabezado, con el mismo tratamiento visual. */
export function AccionVolver({ alternativo, estado }: Props) {
  const ubicacion = useLocation()
  const { to, texto } = retornoSeguro(ubicacion.state) ?? alternativo

  return (
    <div className="accion-volver-barra">
      <Link className="btn accion-volver" to={to} state={estado}>
        <span aria-hidden="true">←</span>
        {texto}
      </Link>
    </div>
  )
}
