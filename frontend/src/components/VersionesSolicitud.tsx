import { useState } from 'react'

import { ApiError } from '../app/api'
import {
  useComparacionVersionesSolicitud,
  useHistorialSolicitud,
  type AlcanceHistorialSolicitud,
  type ComparacionVersiones,
  type DocumentoVersion,
  type TipoDocumento,
  type ValorCampoVersion,
  type VersionSolicitudHistorial,
} from '../pages/solicitudes'
import { Select } from './Select'
import { formatDateTime } from './tableFormatters'

const ETIQUETA_TIPO_DOCUMENTO: Record<TipoDocumento, string> = {
  CAMARA_COMERCIO: 'Cámara de Comercio',
  RUT: 'RUT',
  CEDULA_REPRESENTANTE_LEGAL: 'Cédula del representante legal',
  OTRO_DOCUMENTO_REPRESENTACION: 'Otro documento de representación legal',
  OTRO_SOPORTE: 'Otro soporte',
}

function valor(dato: ValorCampoVersion): string {
  if (dato === null || dato === '') return '—'
  if (typeof dato === 'boolean') return dato ? 'Sí' : 'No'
  return String(dato)
}

function documento(item: DocumentoVersion): string {
  return `${item.nombre_archivo} (${ETIQUETA_TIPO_DOCUMENTO[item.tipo] ?? item.tipo})`
}

function Radicacion({ version }: { version: VersionSolicitudHistorial }) {
  const { devolucion } = version
  return (
    <li className="timeline-item">
      <p className="timeline-fecha">Radicada {formatDateTime(version.radicada_en)}</p>
      <p className="timeline-titulo">Versión {version.numero}</p>
      {devolucion && (
        <div className="timeline-observaciones">
          <span className="badge badge-warning">Devuelta</span>
          <p>{devolucion.observaciones}</p>
          <p className="texto-secundario">
            {devolucion.devuelta_por_nombre} · {formatDateTime(devolucion.devuelta_en)}
          </p>
          <p>
            {devolucion.corregida_en_version
              ? `Corregida en la versión ${devolucion.corregida_en_version}`
              : 'Pendiente de corrección por el Solicitante'}
          </p>
        </div>
      )}
    </li>
  )
}

function Comparacion({ comparacion }: { comparacion: ComparacionVersiones }) {
  const { campos, documentos } = comparacion
  const hayDocumentos =
    documentos.agregados.length + documentos.sustituidos.length + documentos.eliminados.length > 0

  if (!comparacion.hay_cambios) {
    return (
      <p className="texto-secundario">
        La versión {comparacion.version_comparada.numero} no tiene cambios respecto a la versión{' '}
        {comparacion.version_base.numero}.
      </p>
    )
  }

  return (
    <>
      {campos.length > 0 && (
        <div className="table-container">
          <table className="table" aria-label="Campos modificados">
            <thead>
              <tr>
                <th scope="col">Campo</th>
                <th scope="col">Antes</th>
                <th scope="col">Después</th>
              </tr>
            </thead>
            <tbody>
              {campos.map((cambio) => (
                <tr key={cambio.campo}>
                  <th scope="row">{cambio.etiqueta}</th>
                  <td>{valor(cambio.valor_anterior)}</td>
                  <td>{valor(cambio.valor_nuevo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {hayDocumentos && (
        <>
          <h3>Cambios en documentos</h3>
          <ul className="versiones-documentos" aria-label="Cambios en documentos">
            {documentos.agregados.map((item) => (
              <li className="document-row" key={`agregado-${item.id}`}>
                <span>{documento(item)}</span>
                <span className="badge badge-success">Agregado</span>
              </li>
            ))}
            {documentos.sustituidos.map(({ anterior, nuevo }) => (
              <li className="document-row" key={`sustituido-${anterior.id}-${nuevo.id}`}>
                <span>{documento(anterior)} → {documento(nuevo)}</span>
                <span className="badge badge-warning">Sustituido</span>
              </li>
            ))}
            {documentos.eliminados.map((item) => (
              <li className="document-row" key={`eliminado-${item.id}`}>
                <span>{documento(item)}</span>
                <span className="badge badge-danger">Eliminado</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}

/** HT-02: radicaciones de la solicitud de origen y comparación contra la anterior. */
export function VersionesSolicitud({
  solicitudId,
  alcance = 'recibida',
}: {
  solicitudId: number
  alcance?: AlcanceHistorialSolicitud
}) {
  const historial = useHistorialSolicitud(solicitudId, alcance)
  const [elegida, setElegida] = useState<number | null>(null)
  const versiones = historial.data?.versiones ?? []
  const comparables = versiones.filter((version) => version.numero > 1)
  const numero = elegida ?? comparables.at(-1)?.numero ?? null
  const comparacion = useComparacionVersionesSolicitud(solicitudId, numero, alcance)

  // Sin acceso a las solicitudes recibidas la sección no aplica.
  if (historial.error instanceof ApiError && [403, 404].includes(historial.error.status)) return null

  return (
    <section className="card" aria-labelledby="versiones-solicitud-titulo">
      <h2 id="versiones-solicitud-titulo">Versiones de la solicitud</h2>
      {historial.isPending && <p className="estado-pagina">Cargando versiones de la solicitud…</p>}
      {historial.isError && (
        <p className="alert-error" role="alert">No se pudieron consultar las versiones de la solicitud.</p>
      )}
      {historial.data && versiones.length === 0 && (
        <p className="texto-secundario">Aún no hay radicaciones registradas.</p>
      )}
      {versiones.length > 0 && (
        <ol className="timeline" aria-label="Radicaciones de la solicitud">
          {versiones.map((version) => <Radicacion key={version.numero} version={version} />)}
        </ol>
      )}
      {historial.data && versiones.length === 1 && (
        <p className="texto-secundario">Solo existe la radicación inicial; no hay cambios que comparar.</p>
      )}
      {comparables.length > 0 && numero !== null && (
        <>
          <Select
            id="versiones-solicitud-comparar"
            label="Comparar con la versión anterior"
            value={String(numero)}
            opciones={comparables.map((version) => ({
              value: String(version.numero),
              label: `Versión ${version.numero} · ${formatDateTime(version.radicada_en)}`,
            }))}
            onChange={(evento) => setElegida(Number(evento.target.value))}
          />
          {comparacion.isPending && <p className="estado-pagina">Cargando comparación…</p>}
          {comparacion.isError && (
            <p className="alert-error" role="alert">No se pudo comparar la versión {numero}.</p>
          )}
          {comparacion.data && <Comparacion comparacion={comparacion.data} />}
        </>
      )}
    </section>
  )
}
