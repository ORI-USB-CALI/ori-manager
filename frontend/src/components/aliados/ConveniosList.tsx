import type { ConvenioDeAliado } from '../../features/aliados/types'
import { ConvenioBadge } from './ConvenioBadge'

// Adaptado de feature/InterfazPerfilDetalleAliado. La tabla convenio de esta
// rama solo tiene id, estado y fechas de registro; código, título y vigencia
// se mostrarán cuando la HU de convenios cree esas columnas.

interface ConveniosListProps {
  convenios: ConvenioDeAliado[]
}

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleDateString('es-CO')
}

export function ConveniosList({ convenios }: ConveniosListProps) {
  if (convenios.length === 0) {
    return (
      <div className="state-container">
        <h3 className="state-title">Sin convenios asociados</h3>
        <p className="state-description">
          Actualmente no existen convenios registrados para este aliado.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 style={{ marginBottom: '16px' }}>Convenios asociados ({convenios.length})</h2>

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Convenio</th>
              <th>Estado</th>
              <th>Registrado</th>
              <th>Última actualización</th>
            </tr>
          </thead>
          <tbody>
            {convenios.map((c) => (
              <tr key={c.id}>
                <td>
                  <strong>Convenio #{c.id}</strong>
                </td>
                <td>
                  <ConvenioBadge estado={c.estado} />
                </td>
                <td>{formatearFecha(c.creado_en)}</td>
                <td>{formatearFecha(c.actualizado_en)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
