import type { ComponentProps } from 'react'

export interface OpcionSelect {
  value: string
  label: string
}

interface Props extends Omit<ComponentProps<'select'>, 'children' | 'id'> {
  id: string
  label: string
  opciones: readonly OpcionSelect[]
  ayuda?: string
}

export function Select({
  id,
  label,
  opciones,
  ayuda,
  className,
  'aria-describedby': descripcionExterna,
  ...props
}: Props) {
  const ayudaId = `${id}-ayuda`
  const descripcion = [ayuda ? ayudaId : null, descripcionExterna]
    .filter(Boolean)
    .join(' ') || undefined

  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className={`form-control select ${className ?? ''}`}
        aria-describedby={descripcion}
        {...props}
      >
        {opciones.map((opcion) => (
          <option key={opcion.value} value={opcion.value}>
            {opcion.label}
          </option>
        ))}
      </select>
      {ayuda && <small id={ayudaId} className="form-help">{ayuda}</small>}
    </div>
  )
}
