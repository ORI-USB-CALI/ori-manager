import type { Convenio } from '../../types/aliado'
import { ConvenioBadge } from './ConvenioBadge'

interface ConveniosListProps {
  convenios: Convenio[]
}

export function ConveniosList({ convenios }: ConveniosListProps) {
  if (convenios.length === 0) {
    return (
      <div className="state-container">
        <h3 className="state-title">Sin Convenios Asociados</h3>
        <p className="state-description">
          Actualmente no existen convenios registrados para este aliado.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
        }}
      >
        <h2>Convenios Asociados ({convenios.length})</h2>
      </div>

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Título del Convenio</th>
              <th>Tipo</th>
              <th>Estado</th>
              <th>Fecha Inicio</th>
              <th>Fecha Fin</th>
            </tr>
          </thead>
          <tbody>
            {convenios.map((c) => (
              <tr key={c.id}>
                <td>
                  <strong>{c.codigo}</strong>
                </td>
                <td>{c.titulo}</td>
                <td>{c.tipo_convenio || '—'}</td>
                <td>
                  <ConvenioBadge estado={c.estado} />
                </td>
                <td>
                  {c.fecha_inicio
                    ? new Date(c.fecha_inicio).toLocaleDateString('es-CO')
                    : '—'}
                </td>
                <td>
                  {c.fecha_fin
                    ? new Date(c.fecha_fin).toLocaleDateString('es-CO')
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
