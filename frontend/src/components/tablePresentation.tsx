import type { ReactNode } from 'react'

import { badgeVariant, enumLabel } from './tableFormatters'

interface StatusBadgeProps {
  value: string
  label?: ReactNode
}

export function StatusBadge({ value, label }: StatusBadgeProps) {
  return (
    <span className={`badge ${badgeVariant(value)}`}>
      {label ?? enumLabel(value)}
    </span>
  )
}
