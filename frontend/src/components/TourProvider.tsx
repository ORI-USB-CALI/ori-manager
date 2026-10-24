import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useSesion } from '../auth/sesion'
import { abrirRecorrido, type CodigoGuia, type OpcionesRecorrido, RecorridoContext } from './recorrido'

/** Guarda cuál recorrido está abierto para que no se abran dos a la vez (HU-39 RN-06). */
export function TourProvider({ children }: { children: ReactNode }) {
  const { sesion } = useSesion()
  const [activo, setActivo] = useState<CodigoGuia | null>(null)
  const cerrarActual = useRef<(() => void) | null>(null)

  useEffect(() => () => cerrarActual.current?.(), [])

  const iniciar = useCallback((opciones: OpcionesRecorrido) => {
    if (cerrarActual.current || !sesion) return false
    const cerrar = abrirRecorrido(opciones, sesion, () => {
      cerrarActual.current = null
      setActivo(null)
    })
    if (!cerrar) return false
    cerrarActual.current = cerrar
    setActivo(opciones.guia)
    return true
  }, [sesion])

  const valor = useMemo(() => ({ activo, iniciar }), [activo, iniciar])
  return <RecorridoContext value={valor}>{children}</RecorridoContext>
}
