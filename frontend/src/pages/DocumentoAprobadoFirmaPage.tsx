import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { AccionVolver } from '../components/AccionVolver'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'
import { referenciaConvenio } from './epica02'

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
      <>
        <AccionVolver alternativo={{ to: `/convenios/${convenioId}`, texto: 'Volver al convenio' }} />
        <section className="card estado-vacio">
          <h1>{noDisponible ? 'Documento aprobado no disponible' : 'No se pudo consultar el documento aprobado'}</h1>
        </section>
      </>
    )
  }
  if (!documento.data) return null
  const datos = documento.data

  return (
    <article className="documento-aprobado-page">
      <AccionVolver alternativo={{ to: `/convenios/${datos.convenio_id}`, texto: 'Volver al convenio' }} />
      <header className="documento-aprobado-cabecera">
        <div>
          <h1>Documento aprobado para firma</h1>
          <p>{referenciaConvenio(datos.codigo_convenio, datos.convenio_id)}</p>
        </div>
        <strong>Versión {datos.version_numero}</strong>
      </header>
      <div className="page-toolbar documento-aprobado-acciones">
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
