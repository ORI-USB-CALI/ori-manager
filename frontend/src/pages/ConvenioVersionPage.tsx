import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../app/api'
import { ConvenioEditor } from '../components/ConvenioEditor'
import { contextoVersion, useVersionConvenio } from './epica02'

// Etiquetas de los campos que congela el snapshot. Un campo desconocido (por
// ejemplo, de un snapshot más antiguo o más reciente) se muestra con su clave.
const CAMPOS_SNAPSHOT: Record<string, string> = {
  codigo: 'Código',
  solicitud_id: 'Solicitud (ID)',
  origen: 'Origen',
  aliado_id: 'Aliado (ID)',
  tipo_convenio_id: 'Tipo de convenio (ID)',
  objeto: 'Objeto',
  alcance: 'Alcance',
  unidad_organizacional_id: 'Unidad / programa (ID)',
  implicacion_financiera: 'Implicación financiera',
  fecha_inicio: 'Fecha de inicio',
  fecha_vencimiento: 'Fecha de vencimiento',
  duracion_meses: 'Duración (meses)',
  convenio_origen_id: 'Convenio de origen (ID)',
  numero_renovacion: 'Número de renovación',
}

function fechaHora(valor: string) {
  return new Date(valor).toLocaleString()
}

function valorSnapshot(valor: unknown) {
  if (valor === null || valor === undefined || valor === '') return '—'
  return typeof valor === 'object' ? JSON.stringify(valor) : String(valor)
}

/**
 * HT-05. Consulta de solo lectura de una versión formal del convenio.
 * Muestra el snapshot almacenado tal cual, sin acciones de edición ni guardado,
 * y no consulta el borrador de trabajo para no alterarlo ni confundirlo.
 */
export function ConvenioVersionPage() {
  const params = useParams()
  const id = Number(params.convenioId)
  const numero = Number(params.numero)
  const numeroValido = Number.isInteger(numero) && numero > 0
  const version = useVersionConvenio(id, numero)

  const volver = (
    <nav className="page-toolbar" aria-label="Navegación de la versión">
      <Link className="btn btn-outline" to={`/convenios/${id}/elaboracion`}>Volver al historial de versiones</Link>
      <Link className="btn btn-outline" to={`/convenios/${id}`}>Volver al convenio</Link>
    </nav>
  )

  if (numeroValido && version.isPending) return <p className="estado-pagina">Cargando versión…</p>
  if (!numeroValido || version.isError) {
    const noExiste = !numeroValido || (version.error instanceof ApiError && version.error.status === 404)
    return (
      <>
        <section className="card estado-vacio" role="alert">
          <h1>{noExiste ? 'Versión no encontrada' : 'No se pudo consultar la versión'}</h1>
          <p>
            {noExiste
              ? 'La versión solicitada no existe o no está disponible para este convenio.'
              : version.error instanceof Error ? version.error.message : 'Intenta de nuevo más tarde.'}
          </p>
        </section>
        {volver}
      </>
    )
  }

  const datos = version.data!
  const snapshot = Object.entries(datos.snapshot_metadata ?? {})

  return (
    <>
      <section className="header-banner">
        <h1>Versión {datos.numero} del convenio</h1>
        <p>
          <span className="badge badge-historica">Versión histórica · Solo lectura</span>
          {' · '}Convenio #{id}
        </p>
      </section>

      <div className="version-historica-aviso" role="note">
        Estás consultando una versión formal almacenada. Su contenido no se puede editar
        y no corresponde necesariamente al borrador de trabajo actual del convenio.
      </div>

      <div className="elaboracion-workspace">
        <main className="elaboracion-principal">
          <section className="elaboracion-documento version-historica-documento card" aria-label={`Contenido de la versión ${datos.numero}`}>
            <div className="editor-cabecera">
              <div>
                <h2>Documento jurídico</h2>
                <p className="section-help">Contenido tal como quedó registrado en la versión {datos.numero}.</p>
              </div>
              <span className="badge badge-historica">Solo lectura</span>
            </div>
            <ConvenioEditor key={`${id}-${datos.numero}`} contenido={datos.contenido} editable={false} />
          </section>
        </main>

        <aside className="elaboracion-panel">
          <section className="card proyecto-resumen">
            <h2>Datos de la versión</h2>
            <dl className="proyecto-datos">
              <dt>Número de versión</dt><dd>{datos.numero}</dd>
              <dt>Autor</dt><dd>{datos.autor.nombre_completo}</dd>
              <dt>Fecha</dt><dd>{fechaHora(datos.creado_en)}</dd>
              <dt>Etapa</dt><dd>{datos.etapa.nombre}</dd>
              <dt>Contexto de generación</dt><dd>{contextoVersion(datos.contexto)}</dd>
              <dt>Plantilla utilizada</dt><dd>{datos.plantilla?.nombre ?? 'Sin plantilla asociada'}</dd>
            </dl>
          </section>

          <section className="card proyecto-resumen">
            <h2>Datos del convenio en esta versión</h2>
            {snapshot.length > 0 ? (
              <dl className="proyecto-datos">
                {snapshot.map(([campo, valor]) => (
                  <div className="snapshot-campo" key={campo}>
                    <dt>{CAMPOS_SNAPSHOT[campo] ?? campo}</dt>
                    <dd>{valorSnapshot(valor)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="section-help">Esta versión no registró datos del convenio.</p>
            )}
          </section>
        </aside>
      </div>

      {volver}
    </>
  )
}
