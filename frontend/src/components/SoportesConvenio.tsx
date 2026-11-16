import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { CargarDocumentoModal } from './CargarDocumentoModal'
import { DocumentoPreviewModal } from './DocumentoPreviewModal'
import {
  claveSoportesConvenio,
  esConvenioActivoParaSoportes,
  formatearFechaSoporte,
  tamanoLegible,
  useSoportesConvenio,
  type SoporteConvenio,
} from '../pages/soportes'

export interface SoportesConvenioProps {
  convenioId: number
  estadoConvenio?: string | null
  puedeGestionarSoportes: boolean
}

export function SoportesConvenio({
  convenioId,
  estadoConvenio,
  puedeGestionarSoportes,
}: SoportesConvenioProps) {
  const cliente = useQueryClient()
  const [mostrarModalCarga, setMostrarModalCarga] = useState(false)
  const [soportePreview, setSoportePreview] = useState<SoporteConvenio | null>(null)

  // FE-03 / CA-04: Solo Gestor y Administrador ORI pueden gestionar soportes
  // y solo convenios vigentes o por vencer admiten cargar nuevos documentos.
  const puedeCargar = puedeGestionarSoportes && esConvenioActivoParaSoportes(estadoConvenio)

  // La consulta solo se habilita para usuarios autorizados
  const { data: soportes, isPending, isError, error } = useSoportesConvenio(
    convenioId,
    puedeGestionarSoportes,
  )

  const manejarDocumentoCargado = () => {
    cliente.invalidateQueries({ queryKey: claveSoportesConvenio(convenioId) })
    cliente.invalidateQueries({ queryKey: ['convenio', convenioId] })
  }

  // Si no tiene permiso de gestión de soportes, no mostramos la sección
  if (!puedeGestionarSoportes) {
    return null
  }

  return (
    <section className="card soportes-convenio-card tabla-seccion" aria-labelledby="soportes-convenio-titulo">
      <div className="soportes-cabecera">
        <h2 id="soportes-convenio-titulo">Documentos de soporte</h2>
        {puedeCargar && (
          <button
            type="button"
            className="btn btn-outline btn-small"
            onClick={() => setMostrarModalCarga(true)}
            data-testid="btn-cargar-soporte"
          >
            + Cargar documento PDF
          </button>
        )}
      </div>

      {isPending && <p className="estado-pagina">Cargando documentos de soporte…</p>}

      {isError && (
        <p className="texto-peligro">
          {error instanceof Error ? error.message : 'No fue posible consultar los documentos de soporte.'}
        </p>
      )}

      {!isPending && !isError && soportes && soportes.length === 0 && (
        <p className="section-help" data-testid="soportes-vacio">
          Aún no hay documentos de soporte asociados a este convenio
        </p>
      )}

      {!isPending && !isError && soportes && soportes.length > 0 && (
        <div className="table-container tabla-densa-region" role="region" aria-label="Documentos de soporte" tabIndex={0}>
          <table className="table tabla-densa" data-testid="tabla-soportes">
            <thead>
              <tr>
                <th scope="col" className="tabla-col-descripcion">Documento</th>
                <th scope="col" className="tabla-col-numero">Tamaño</th>
                <th scope="col" className="tabla-col-fecha">Fecha de carga</th>
                <th scope="col" className="tabla-col-persona">Usuario responsable</th>
                <th scope="col" className="tabla-col-acciones">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {soportes.map((soporte: SoporteConvenio) => (
                <tr key={soporte.id}>
                  <td className="tabla-col-descripcion">
                    <span className="soporte-nombre">
                      <span aria-hidden="true">📄</span> {soporte.nombre_original}
                    </span>
                  </td>
                  <td className="tabla-col-numero">{tamanoLegible(soporte.tamano_bytes)}</td>
                  <td className="tabla-col-fecha">{formatearFechaSoporte(soporte.fecha_creacion)}</td>
                  <td className="tabla-col-persona">{soporte.usuario_nombre ?? '—'}</td>
                  <td className="tabla-col-acciones">
                    <div className="soportes-acciones">
                      <a
                        className="btn btn-outline btn-small"
                        href={`/api/convenios/${convenioId}/documentos/${soporte.id}/descargar?disposicion=inline`}
                        target="_blank"
                        rel="noreferrer"
                        title={`Ver ${soporte.nombre_original}`}
                        data-testid={`btn-ver-soporte-${soporte.id}`}
                        onClick={(evento) => {
                          evento.preventDefault()
                          setSoportePreview(soporte)
                        }}
                      >
                        Ver
                      </a>
                      <a
                        className="btn btn-primary btn-small"
                        href={`/api/convenios/${convenioId}/documentos/${soporte.id}/descargar?disposicion=attachment`}
                        download={soporte.nombre_original}
                        title={`Descargar ${soporte.nombre_original}`}
                        data-testid={`btn-descargar-soporte-${soporte.id}`}
                      >
                        Descargar
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {mostrarModalCarga && (
        <CargarDocumentoModal
          convenioId={convenioId}
          onCerrar={() => setMostrarModalCarga(false)}
          onDocumentoCargado={manejarDocumentoCargado}
        />
      )}

      {soportePreview && (
        <DocumentoPreviewModal
          nombreArchivo={soportePreview.nombre_original}
          urlContenido={`/convenios/${convenioId}/documentos/${soportePreview.id}/descargar?disposicion=inline`}
          urlDescarga={`/api/convenios/${convenioId}/documentos/${soportePreview.id}/descargar?disposicion=attachment`}
          tipoMime="application/pdf"
          onCerrar={() => setSoportePreview(null)}
        />
      )}
    </section>
  )
}
