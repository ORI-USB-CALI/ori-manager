import { Link, useParams } from 'react-router-dom'

import { EvaluacionConvenio } from '../components/EvaluacionConvenio'
import { HistorialConvenioContenido } from '../components/HistorialConvenioContenido'

export function ConvenioHistorialPage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)

  return (
    <>
      <section className="header-banner">
        <h1>Historial y trazabilidad</h1>
        <p>
          Convenio #{id} · <Link to="/convenios/tablero">Tablero de convenios</Link>
          {' · '}<Link to="/convenios">Consulta de convenios formalizados</Link>
        </p>
      </section>

      <HistorialConvenioContenido convenioId={id} />

      <EvaluacionConvenio convenioId={id} />
    </>
  )
}
