import type { ReactNode } from 'react'

export interface DataTableColumn<T> {
  id: string
  header: ReactNode
  render: (row: T) => ReactNode
  align?: 'left' | 'center' | 'right'
  className?: string
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  label: string
  emptyMessage?: string
  onClearEmpty?: () => void
  isLoading?: boolean
  loadingMessage?: string
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  label,
  emptyMessage = 'No hay resultados.',
  onClearEmpty,
  isLoading = false,
  loadingMessage = 'Cargando…',
}: DataTableProps<T>) {
  if (isLoading) return <p className="estado-pagina">{loadingMessage}</p>
  if (rows.length === 0) {
    return <TableEmptyState message={emptyMessage} onClear={onClearEmpty} />
  }

  return (
    <div className="table-container">
      <table className="table" aria-label={label}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                className={column.className}
                scope="col"
                style={column.align ? { textAlign: column.align } : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td
                  key={column.id}
                  className={column.className}
                  style={column.align ? { textAlign: column.align } : undefined}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface TableEmptyStateProps {
  message: string
  onClear?: () => void
}

export function TableEmptyState({ message, onClear }: TableEmptyStateProps) {
  return (
    <section className="card estado-vacio">
      <p>{message}</p>
      {onClear && (
        <button type="button" className="btn btn-outline btn-small" onClick={onClear}>
          Limpiar filtros
        </button>
      )}
    </section>
  )
}

export function ResultsCount({ count }: { count: number }) {
  return (
    <p className="table-results" aria-live="polite">
      {count} {count === 1 ? 'resultado' : 'resultados'}
    </p>
  )
}
