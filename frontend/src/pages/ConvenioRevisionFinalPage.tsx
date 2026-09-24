import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../app/api'
import { useRevisionFinalConvenio } from './epica02'

const ETIQUETAS_ROL_FIRMANTE: Record<string, string> = {
  ADMINISTRADOR_ORI: 'Administrador ORI',
  REVISOR_ORI: 'Revisor ORI',
  VICERRECTORIA_FINANCIERA: 'Vicerrectoría Financiera',
  VICERRECTORIA_ACADEMICA: 'Vicerrectoría Académica',
  SECRETARIA: 'Secretaría',
  RECTOR: 'Rector',
  PARTE_SOLICITANTE: 'Representante Parte Solicitante',
}

const ETIQUETAS_PARTE: Record<string, string> = {
  USB: 'Universidad de San Buenaventura',
  SOLICITANTE: 'Parte Solicitante',
}

function fecha(valor: string | null) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

function fechaHora(valor: string | null) {
  return valor ? new Date(valor).toLocaleString() : '—'
}

function formatoTamano(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ConvenioRevisionFinalPage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const revisionQuery = useRevisionFinalConvenio(id)

  if (revisionQuery.isPending) {
    return <p className="estado-pagina">Cargando datos de revisión final…</p>
  }

  if (revisionQuery.isError) {
    const error = revisionQuery.error
    return (
      <section className="card estado-vacio">
        <h1>
          {error instanceof ApiError && error.status === 404
            ? 'Convenio no encontrado'
            : 'No se pudo consultar la revisión final del convenio'}
        </h1>
        <p className="caption">Verifique el identificador del convenio e intente nuevamente.</p>
        <Link className="btn btn-outline" to="/convenios">
          Volver a convenios
        </Link>
      </section>
    )
  }

  const datos = revisionQuery.data
  if (!datos) return null

  return (
    <>
      <section className="header-banner">
        <div>
          <h1>Revisión Final — Convenio {datos.codigo ?? `#${datos.id}`}</h1>
          <p>
            <span className="badge">{datos.estado}</span>{' '}
            <span className={datos.revision_final_aprobada ? 'badge badge-success' : 'badge badge-warning'}>
              {datos.revision_final_aprobada ? 'Aprobada por contraparte' : 'Revisión pendiente'}
            </span>
          </p>
        </div>
      </section>

      <div className="page-toolbar">
        <Link className="btn btn-outline" to={`/convenios/${datos.id}`}>
          Ver Convenio
        </Link>
        <Link className="btn btn-outline" to={`/convenios/${datos.id}/elaboracion`}>
          Ir a Elaboración
        </Link>
      </div>

      <div className="alert-info" style={{ marginBottom: '16px', padding: '12px 16px', borderRadius: '8px', background: '#e0f2fe', border: '1px solid #7dd3fc', color: '#0369a1' }}>
        <strong>Modo de Vista Previa de Revisión Final (CA-01):</strong> Esta vista permite verificar la información y el documento aprobados por la contraparte antes de la apertura del proceso de firmas.
        {!datos.proceso_firmas_abierto && (
          <span style={{ display: 'block', marginTop: '4px' }}>
            <em>Nota: El proceso de firmas aún no ha sido abierto oficialmente.</em>
          </span>
        )}
      </div>

      <section className="card" style={{ marginBottom: '20px' }}>
        <h2>Información del Convenio para Revisión Final</h2>
        <dl>
          <dt>Solicitud de origen</dt>
          <dd>#{datos.solicitud_id}</dd>
          <dt>Código del convenio</dt>
          <dd>{datos.codigo ?? 'Sin código asignado'}</dd>
          <dt>Objeto</dt>
          <dd>{datos.objeto ?? '—'}</dd>
          <dt>Implicación financiera</dt>
          <dd>{datos.implicacion_financiera ?? 'Sin implicación financiera especificada'}</dd>
          <dt>Estado actual</dt>
          <dd>{datos.estado}</dd>
          <dt>Fecha de creación</dt>
          <dd>{fecha(datos.creado_en)}</dd>
        </dl>
      </section>

      <section className="card" style={{ marginBottom: '20px' }}>
        <h2>Documento Aprobado por la Contraparte</h2>
        {datos.documento_aprobado ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <p>
              <strong>Archivo:</strong> {datos.documento_aprobado.nombre_archivo}
            </p>
            <p>
              <strong>Tipo:</strong> {datos.documento_aprobado.tipo_documento}
            </p>
            <p>
              <strong>Tamaño:</strong> {formatoTamano(datos.documento_aprobado.tamano_bytes)}
            </p>
            <p>
              <strong>Cargado en:</strong> {fechaHora(datos.documento_aprobado.creado_en)}
            </p>
          </div>
        ) : (
          <p className="caption">No hay un documento adjunto registrado para esta revisión final.</p>
        )}
      </section>

      <section className="card">
        <h2>Firmantes Requeridos ({datos.firmas.length} de 7)</h2>
        <p className="caption" style={{ marginBottom: '12px' }}>
          De acuerdo con CA-05 y CA-08, cada convenio requiere 6 firmantes institucionales obligatorios y 1 firmante representante de la parte solicitante.
        </p>

        {datos.firmas.length === 0 ? (
          <p className="caption">No se han registrado firmantes para este convenio.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)', paddingBottom: '8px' }}>
                <th style={{ padding: '8px' }}>#</th>
                <th style={{ padding: '8px' }}>Rol Firmante</th>
                <th style={{ padding: '8px' }}>Parte</th>
                <th style={{ padding: '8px' }}>Firmante / Cargo</th>
                <th style={{ padding: '8px' }}>Modalidad</th>
                <th style={{ padding: '8px' }}>Estado</th>
                <th style={{ padding: '8px' }}>Fecha de Firma</th>
              </tr>
            </thead>
            <tbody>
              {datos.firmas.map((firma) => (
                <tr key={firma.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '8px', fontWeight: 'bold' }}>{firma.orden}</td>
                  <td style={{ padding: '8px' }}>{ETIQUETAS_ROL_FIRMANTE[firma.rol_firmante] ?? firma.rol_firmante}</td>
                  <td style={{ padding: '8px' }}>{ETIQUETAS_PARTE[firma.parte] ?? firma.parte}</td>
                  <td style={{ padding: '8px' }}>
                    {firma.nombre_firmante ? (
                      <div>
                        <strong>{firma.nombre_firmante}</strong>
                        {firma.cargo_firmante && <div className="caption">{firma.cargo_firmante}</div>}
                      </div>
                    ) : (
                      <span className="caption">Por asignar</span>
                    )}
                  </td>
                  <td style={{ padding: '8px' }}>{firma.modalidad ?? 'Por definir'}</td>
                  <td style={{ padding: '8px' }}>
                    <span className={firma.estado === 'FIRMADA' ? 'badge badge-success' : firma.estado === 'RECHAZADA' ? 'badge badge-danger' : 'badge'}>
                      {firma.estado}
                    </span>
                  </td>
                  <td style={{ padding: '8px' }}>{fechaHora(firma.fecha_firma)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
