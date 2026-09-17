import { Link, useParams } from 'react-router-dom'
import { AliadoHeader } from '../components/aliados/AliadoHeader'
import { ConveniosList } from '../components/aliados/ConveniosList'
import { useAliadoDetalle } from '../hooks/useAliadoDetalle'
import { ApiError } from '../services/aliadosApi'

export function AliadoDetailPage() {
  const { aliadoId } = useParams<{ aliadoId: string }>()
  const { data: aliado, isLoading, isError, error } = useAliadoDetalle(aliadoId)

  return (
    <div>
      <header className="navbar">
        <Link to="/" className="navbar-brand">
          Sistema <span>ORI</span> USB Cali
        </Link>
        <div className="user-profile">
          <span>Usuario ORI</span>
        </div>
      </header>

      <main className="main-content">
        <div style={{ marginBottom: '16px' }}>
          <Link
            to="/"
            className="btn btn-outline"
            style={{ padding: '6px 14px', fontSize: '0.8125rem' }}
          >
            ← Volver al Inicio
          </Link>
        </div>

        {isLoading && (
          <div className="state-container">
            <h3 className="state-title">Cargando información del aliado...</h3>
            <p className="state-description">
              Por favor espere un momento mientras se recuperan los datos.
            </p>
          </div>
        )}

        {isError && (
          <div>
            {error instanceof ApiError && error.status === 404 ? (
              <div className="state-container alert-notfound">
                <h3 className="state-title" style={{ color: 'var(--color-naranja)' }}>
                  Aliado No Encontrado (404)
                </h3>
                <p className="state-description">
                  El aliado especificado no existe o no se encuentra registrado en el sistema.
                </p>
                <Link to="/" className="btn btn-primary">
                  Regresar al Inicio
                </Link>
              </div>
            ) : error instanceof ApiError && error.status === 403 ? (
              <div className="state-container alert-forbidden">
                <h3 className="state-title" style={{ color: 'var(--color-rojo)' }}>
                  Acceso Restringido (403)
                </h3>
                <p className="state-description">
                  No cuenta con los permisos necesarios para consultar la información de aliados.
                </p>
                <Link to="/" className="btn btn-outline">
                  Volver al Inicio
                </Link>
              </div>
            ) : (
              <div className="state-container alert-forbidden">
                <h3 className="state-title">Error al consultar el aliado</h3>
                <p className="state-description">
                  {error instanceof Error ? error.message : 'Ocurrió un error inesperado.'}
                </p>
              </div>
            )}
          </div>
        )}

        {aliado && (
          <div>
            <AliadoHeader aliado={aliado} />
            <ConveniosList convenios={aliado.convenios} />
          </div>
        )}
      </main>

      <footer className="footer-internal">
        <span>© Universidad de San Buenaventura Cali — Sistema de Gestión ORI</span>
        <div>
          <span>v1.0.0</span>
        </div>
      </footer>
    </div>
  )
}
