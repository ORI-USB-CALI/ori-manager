import type { ComponentProps } from 'react'

export interface OpcionSelect {
  value: string
  label: string
}

interface Props extends Omit<ComponentProps<'select'>, 'children' | 'id'> {
  id: string
  label: string
  opciones: OpcionSelect[]
}

// Select con el estilo de la guía ORI. Es un <select> nativo: conserva teclado,
// accesibilidad y envío en formularios; donde el navegador lo soporta también se estiliza la lista.
export function Select({ id, label, opciones, className, ...props }: Props) {
  return (
    <div className="form-group">
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <select id={id} className={`form-control select ${className ?? ''}`} {...props}>
        {opciones.map((opcion) => (
          <option key={opcion.value} value={opcion.value}>
            {opcion.label}
          </option>
        ))}
      </select>
    </div>
  )
}
