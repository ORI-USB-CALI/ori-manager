import type { AliadoDetalle } from '../../types/aliado'

interface AliadoHeaderProps {
  aliado: AliadoDetalle
}

export function AliadoHeader({ aliado }: AliadoHeaderProps) {
  const isActivo = aliado.estado === 'ACTIVO'

  return (
    <div className="header-banner">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '16px',
          flexWrap: 'wrap',
        }}

      >
        <div>
          <span
            className={`badge ${isActivo ? 'badge-activo' : 'badge-inactivo'}`}
            style={{ marginBottom: '12px' }}
          >
            Aliado {aliado.estado}
          </span>
          <h1>{aliado.nombre}</h1>
          <div
            style={{
              display: 'flex',
              gap: '20px',
              flexWrap: 'wrap',
              marginTop: '8px',
              fontSize: '0.875rem',
            }}
          >
            {aliado.nit_o_identificacion && (
              <span>
                <strong>NIT / Identificación:</strong> {aliado.nit_o_identificacion}
              </span>
            )}
            {aliado.tipo_aliado && (
              <span>
                <strong>Tipo:</strong> {aliado.tipo_aliado}
              </span>
            )}
          </div>
        </div>
      </div>
      {aliado.descripcion && (
        <p
          style={{
            marginTop: '16px',
            borderTop: '1px solid rgba(255,255,255,0.2)',
            paddingTop: '12px',
          }}
        >
          {aliado.descripcion}
        </p>
      )}
    </div>
  )
}
