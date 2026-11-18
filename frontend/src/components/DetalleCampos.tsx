import type { ReactNode } from 'react'

/** Información de lectura: cada término conserva su asociación semántica con el valor. */
export function DetalleCampos({ children, compacto = false, className = '' }: {
  children: ReactNode
  compacto?: boolean
  className?: string
}) {
  return <dl className={['detalle-campos', compacto && 'detalle-campos--compacto', className].filter(Boolean).join(' ')}>{children}</dl>
}

export function CampoLectura({ etiqueta, children, amplio = false, className = '' }: {
  etiqueta: ReactNode
  children: ReactNode
  amplio?: boolean
  className?: string
}) {
  const vacio = children === null || children === undefined || children === ''
  const valor = vacio ? '—' : typeof children === 'boolean' ? (children ? 'Sí' : 'No') : children
  return <div className={['campo-lectura', amplio && 'campo-lectura--amplio', className].filter(Boolean).join(' ')}>
    <dt>{etiqueta}</dt>
    <dd>{valor}</dd>
  </div>
}
