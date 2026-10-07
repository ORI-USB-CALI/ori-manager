import type { ReactNode } from 'react'

interface TableFiltersProps {
  children: ReactNode
  hasActiveFilters: boolean
  onClear: () => void
}

export function TableFilters({ children, hasActiveFilters, onClear }: TableFiltersProps) {
  return (
    <section className="card table-filters" aria-label="Filtros del listado">
      <h2 className="table-filters-title">Filtros</h2>
      <div className="table-filters-grid">{children}</div>
      {hasActiveFilters && (
        <div className="table-filters-actions">
          <button type="button" className="btn btn-outline btn-small" onClick={onClear}>
            Limpiar filtros
          </button>
        </div>
      )}
    </section>
  )
}
