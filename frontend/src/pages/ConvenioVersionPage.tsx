import { Link, useLocation, useParams } from 'react-router-dom'

import { CampoLectura, DetalleCampos } from '../components/DetalleCampos'
import { ApiError } from '../app/api'
import { useSesion } from '../auth/sesion'
import { AccionVolver } from '../components/AccionVolver'
import { volverA } from '../components/retornoVolver'
import { ConvenioEditor } from '../components/ConvenioEditor'
import { contextoVersion, useVersionConvenio, useVersionesConvenio } from './epica02'

// Etiquetas de los campos que congela el snapshot. Un campo desconocido (por
// ejemplo, de un snapshot más antiguo o más reciente) se muestra con su clave.
const CAMPOS_SNAPSHOT: Record<string, string> = {
  codigo: 'Código',
  solicitud_id: 'Solicitud (ID)',
  origen: 'Origen',
  aliado_id: 'Aliado (ID)',
  aliado_identidad: 'Identidad jurídica del aliado',
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
  const retorno = volverA(useLocation(), 'Volver a la versión del convenio')
  const { sesion } = useSesion()
  const params = useParams()
  const id = Number(params.convenioId)
  const numero = Number(params.numero)
  const parametrosValidos = Number.isInteger(id) && id > 0 && Number.isInteger(numero) && numero > 0
  const version = useVersionConvenio(id, numero)
  const versiones = useVersionesConvenio(id, parametrosValidos)

  // HU-21: una versión histórica no implica acceso al detalle operativo.
  const accionVolver = <AccionVolver alternativo={sesion?.rol.codigo === 'REVISOR_ORI' || !Number.isInteger(id) || id <= 0
    ? { to: '/convenios', texto: 'Volver a la consulta de convenios' }
    : { to: `/convenios/${id}?pestana=historial`, texto: 'Volver al historial del convenio' }} />
  const navegacion = (
    <nav className="page-toolbar" aria-label="Navegación de la versión">
      <Link className="btn btn-outline" to={`/convenios/${id}/elaboracion`} state={retorno}>Ir al proyecto de convenio</Link>
    </nav>
  )

  if (parametrosValidos && version.isPending) return <p className="estado-pagina">Cargando versión…</p>
  if (!parametrosValidos || version.isError) {
    const noExiste = !parametrosValidos || (version.error instanceof ApiError && version.error.status === 404)
    return (
      <>
        {accionVolver}
        <section className="card estado-vacio" role="alert">
          <h1>{noExiste ? 'Versión no encontrada' : 'No se pudo consultar la versión'}</h1>
          <p>
            {noExiste
              ? 'La versión solicitada no existe o no está disponible para este convenio.'
              : version.error instanceof Error ? version.error.message : 'Intenta de nuevo más tarde.'}
          </p>
        </section>
        {navegacion}
      </>
    )
  }

  const datos = version.data!
  const snapshot = Object.entries(datos.snapshot_metadata ?? {})
  // La versión actual es la de mayor número entre las que existen; mientras
  // esa lista cargue, no se afirma si es histórica o no.
  const esVersionActual = versiones.data
    ? datos.numero === Math.max(...versiones.data.map((v) => v.numero))
    : null

  return (
    <>
      {accionVolver}
      <section className="header-banner">
        <h1>Versión {datos.numero} del convenio</h1>
        <p>
          <span className="badge badge-historica">
            {esVersionActual ? 'Versión actual' : 'Versión histórica'} · Solo lectura
          </span>
          {' · '}Convenio #{id}
        </p>
      </section>

      <div className="version-historica-aviso" role="note">
        {esVersionActual
          ? 'Estás consultando la versión formal vigente del convenio. Su contenido '
            + 'no se puede editar desde aquí; el borrador de trabajo, si existe, puede '
            + 'tener cambios sin enviar todavía.'
          : 'Estás consultando una versión formal almacenada. Su contenido no se puede '
            + 'editar y no corresponde necesariamente al borrador de trabajo actual del '
            + 'convenio.'}
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
            <DetalleCampos compacto>
              <CampoLectura etiqueta="Número de versión">{datos.numero}</CampoLectura>
              <CampoLectura etiqueta="Autor">{datos.autor.nombre_completo}</CampoLectura>
              <CampoLectura etiqueta="Fecha">{fechaHora(datos.creado_en)}</CampoLectura>
              <CampoLectura etiqueta="Etapa">{datos.etapa.nombre}</CampoLectura>
              <CampoLectura etiqueta="Contexto de generación">{contextoVersion(datos.contexto)}</CampoLectura>
              <CampoLectura etiqueta="Plantilla utilizada">{datos.plantilla?.nombre ?? 'Sin plantilla asociada'}</CampoLectura>
            </DetalleCampos>
          </section>

          <section className="card proyecto-resumen">
            <h2>Datos del convenio en esta versión</h2>
            {snapshot.length > 0 ? (
              <DetalleCampos compacto>
                {snapshot.map(([campo, valor]) => (
                  <CampoLectura key={campo} etiqueta={CAMPOS_SNAPSHOT[campo] ?? campo}>{valorSnapshot(valor)}</CampoLectura>
                ))}
              </DetalleCampos>
            ) : (
              <p className="section-help">Esta versión no registró datos del convenio.</p>
            )}
          </section>
        </aside>
      </div>

      {navegacion}
    </>
  )
}
