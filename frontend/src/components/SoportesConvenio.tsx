import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { CargarDocumentoModal } from './CargarDocumentoModal'
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
    <section className="card soportes-convenio-card" aria-labelledby="soportes-convenio-titulo">
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
        <div className="table-container">
          <table className="table" data-testid="tabla-soportes">
            <thead>
              <tr>
                <th>Documento</th>
                <th>Tamaño</th>
                <th>Fecha de carga</th>
                <th>Usuario responsable</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {soportes.map((soporte: SoporteConvenio) => (
                <tr key={soporte.id}>
                  <td>
                    <span className="soporte-nombre">
                      <span aria-hidden="true">📄</span> {soporte.nombre_original}
                    </span>
                  </td>
                  <td>{tamanoLegible(soporte.tamano_bytes)}</td>
                  <td>{formatearFechaSoporte(soporte.fecha_creacion)}</td>
                  <td>{soporte.usuario_nombre ?? '—'}</td>
                  <td>
                    <div className="soportes-acciones">
                      <a
                        className="btn btn-outline btn-small"
                        href={`/api/convenios/${convenioId}/documentos/${soporte.id}/descargar?disposicion=inline`}
                        target="_blank"
                        rel="noreferrer"
                        title={`Ver ${soporte.nombre_original}`}
                        data-testid={`btn-ver-soporte-${soporte.id}`}
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
    </section>
  )
}
