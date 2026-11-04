import { Link, useParams } from 'react-router-dom'

import { useSesion } from '../auth/sesion'
import { AccionVolver } from '../components/AccionVolver'
import { EvaluacionConvenio } from '../components/EvaluacionConvenio'
import { HistorialConvenioContenido } from '../components/HistorialConvenioContenido'

export function ConvenioHistorialPage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const { sesion } = useSesion()
  // HU-21: el Revisor puede tener acceso histórico sin acceso al detalle operativo.
  const alternativo = sesion?.rol.codigo === 'REVISOR_ORI'
    ? { to: '/convenios', texto: 'Volver a la consulta de convenios' }
    : { to: `/convenios/${id}`, texto: 'Volver al convenio' }

  return (
    <>
      <AccionVolver alternativo={alternativo} />

      <section className="header-banner">
        <h1>Historial y trazabilidad</h1>
        <p>
          Convenio #{id}
        </p>
      </section>

      <nav className="page-toolbar" aria-label="Navegación del historial">
        <Link className="btn btn-outline" to="/convenios/tablero">Tablero de convenios</Link>
        <Link className="btn btn-outline" to="/convenios">Consulta de convenios formalizados</Link>
      </nav>

      <HistorialConvenioContenido convenioId={id} />

      <EvaluacionConvenio convenioId={id} />
    </>
  )
}
