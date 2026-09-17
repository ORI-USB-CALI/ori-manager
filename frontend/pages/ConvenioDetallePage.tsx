import { Link, useParams } from 'react-router-dom'

import { ConvenioDetail } from '../features/convenios/ConvenioDetail'

export function ConvenioDetallePage() {
  const { id } = useParams<{ id: string }>()
  const convenioId = Number(id)

  return (
    <main className="page">
      <Link to="/">Volver al inicio</Link>
      <h1>Convenio #{id}</h1>

      {Number.isInteger(convenioId) && convenioId > 0 ? (
        <ConvenioDetail convenioId={convenioId} />
      ) : (
        <p className="form-error">El id del convenio no es valido.</p>
      )}
    </main>
  )
}
