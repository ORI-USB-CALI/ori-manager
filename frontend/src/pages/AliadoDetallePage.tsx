import { Link, useOutletContext, useParams } from 'react-router-dom'
import { ApiError, puedeGestionar } from '../api/http'
import { ConveniosList } from '../components/aliados/ConveniosList'
import {
  useAliado,
  useCambiarEstadoAliado,
  useConveniosDeAliado,
} from '../features/aliados/hooks'
import { TIPO_ALIADO_ETIQUETA, type RolUsuario } from '../features/aliados/types'

export function AliadoDetallePage() {
  const { aliadoId } = useParams<{ aliadoId: string }>()
  const id = Number(aliadoId)
  const { rol } = useOutletContext<{ rol: RolUsuario }>()

  const { data: aliado, isPending, isError, error } = useAliado(id)
  const convenios = useConveniosDeAliado(id)
  const cambiarEstado = useCambiarEstadoAliado(id)

  function inactivar() {
    if (!aliado) return
    if (window.confirm(`¿Inactivar a ${aliado.nombre}? Conservará su historial.`)) {
      cambiarEstado.mutate('inactivar')
    }
  }

  if (isPending) {
    return (
      <div className="state-container">
        <h3 className="state-title">Cargando información del aliado...</h3>
      </div>
    )
  }

  if (isError) {
    const noEncontrado = error instanceof ApiError && error.status === 404
    return (
      <div className={`state-container ${noEncontrado ? 'alert-notfound' : 'alert-forbidden'}`}>
        <h3 className="state-title">
          {noEncontrado ? 'Aliado no encontrado' : 'No se pudo consultar el aliado'}
        </h3>
        <p className="state-description">{error.message}</p>
        <Link to="/aliados" className="btn btn-outline">
          Volver al listado
        </Link>
      </div>
    )
  }

  const activo = aliado.estado === 'activo'
  const errorEstado = cambiarEstado.error instanceof ApiError ? cambiarEstado.error : null

  return (
    <>
      <nav className="caption">
        <Link to="/aliados">Aliados</Link> / {aliado.nombre}
      </nav>

      <div className="header-banner">
        <div>
          <span className={`badge badge-${aliado.estado}`} style={{ marginBottom: '12px' }}>
            Aliado {aliado.estado}
          </span>
          <h1>{aliado.nombre}</h1>
          <p>
            <strong>Identificación:</strong> {aliado.identificacion} ·{' '}
            <strong>Tipo:</strong> {TIPO_ALIADO_ETIQUETA[aliado.tipo]}
            {aliado.sector_economico ? ` · ${aliado.sector_economico}` : ''}
          </p>
        </div>
        {puedeGestionar(rol) && (
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Link to={`/aliados/${aliado.id}/editar`} className="btn btn-primary">
              Editar datos
            </Link>
            {activo ? (
              <button
                type="button"
                className="btn btn-outline"
                style={{ backgroundColor: '#FFFFFF' }}
                disabled={cambiarEstado.isPending}
                onClick={inactivar}
              >
                Inactivar aliado
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-outline"
                style={{ backgroundColor: '#FFFFFF' }}
                disabled={cambiarEstado.isPending}
                onClick={() => cambiarEstado.mutate('reactivar')}
              >
                Reactivar aliado
              </button>
            )}
          </div>
        )}
      </div>

      {errorEstado && (
        <div className="state-container alert-forbidden">
          <h3 className="state-title" style={{ color: 'var(--color-rojo)' }}>
            {errorEstado.status === 409
              ? 'No se puede inactivar: tiene convenios vigentes o por vencer'
              : 'No se pudo cambiar el estado'}
          </h3>
          <p className="state-description">{errorEstado.message}</p>
        </div>
      )}

      <div className="card">
        <h2 style={{ marginBottom: '16px' }}>Datos de la entidad</h2>
        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          <Dato etiqueta="Ciudad" valor={aliado.ciudad} />
          <Dato etiqueta="Dirección" valor={aliado.direccion} />
          <Dato etiqueta="Teléfono" valor={aliado.telefono} />
          <Dato etiqueta="Correo" valor={aliado.correo} />
          <Dato etiqueta="Sitio web" valor={aliado.sitio_web} />
          <Dato etiqueta="Registrado el" valor={new Date(aliado.creado_en).toLocaleDateString('es-CO')} />
        </dl>
      </div>

      {convenios.isPending && (
        <div className="state-container">
          <h3 className="state-title">Cargando convenios...</h3>
        </div>
      )}
      {convenios.isError && (
        <div className="state-container alert-forbidden">
          <h3 className="state-title">No se pudieron cargar los convenios</h3>
          <p className="state-description">{convenios.error.message}</p>
        </div>
      )}
      {convenios.data && <ConveniosList convenios={convenios.data} />}
    </>
  )
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string | null }) {
  return (
    <div>
      <dt className="caption">{etiqueta}</dt>
      <dd style={{ fontWeight: 600 }}>{valor || '—'}</dd>
    </div>
  )
}
