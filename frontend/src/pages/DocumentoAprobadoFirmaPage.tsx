import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'

interface DocumentoAprobadoFirma {
  convenio_id: number
  codigo_convenio: string | null
  proceso_firmas_id: number
  version_convenio_id: number
  version_numero: number
  contenido: DocumentoConvenio
  creado_en: string
}

export function DocumentoAprobadoFirmaPage() {
  const convenioId = Number(useParams().convenioId)
  const documento = useQuery({
    queryKey: ['convenio', convenioId, 'firmas', 'documento-aprobado'],
    queryFn: () => apiFetch<DocumentoAprobadoFirma>(
      `/convenios/${convenioId}/firmas/documento-aprobado`,
    ),
    enabled: Number.isInteger(convenioId) && convenioId > 0,
    retry: false,
  })

  if (documento.isPending) return <p className="estado-pagina">Cargando documento aprobado…</p>
  if (documento.isError) {
    const noDisponible = documento.error instanceof ApiError
      && (documento.error.status === 404 || documento.error.status === 409)
    return (
      <section className="card estado-vacio">
        <h1>{noDisponible ? 'Documento aprobado no disponible' : 'No se pudo consultar el documento aprobado'}</h1>
        <Link className="btn btn-outline" to={`/convenios/${convenioId}`}>Volver al convenio</Link>
      </section>
    )
  }
  if (!documento.data) return null
  const datos = documento.data

  return (
    <article className="documento-aprobado-page">
      <header className="documento-aprobado-cabecera">
        <div>
          <h1>Documento aprobado para firma</h1>
          <p>{datos.codigo_convenio ?? `Convenio #${datos.convenio_id}`}</p>
        </div>
        <strong>Versión {datos.version_numero}</strong>
      </header>
      <div className="page-toolbar documento-aprobado-acciones">
        <Link className="btn btn-outline" to={`/convenios/${datos.convenio_id}`}>Volver al convenio</Link>
        <button className="btn btn-primary" type="button" onClick={() => window.print()}>
          Imprimir / Guardar como PDF
        </button>
      </div>
      <section className="documento-aprobado-contenido" aria-label="Contenido contractual aprobado">
        <ConvenioEditor contenido={datos.contenido} editable={false} onChange={() => undefined} />
      </section>
    </article>
  )
}
