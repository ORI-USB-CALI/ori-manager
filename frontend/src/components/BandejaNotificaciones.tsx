import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'

interface BandejaNotificacionesProps {
  contador: number
  children: ReactNode
  onAbrir?: () => void
}

export function BandejaNotificaciones({
  contador,
  children,
  onAbrir,
}: BandejaNotificacionesProps) {
  const ubicacion = useLocation()

  return (
    <BandejaNotificacionesInteractiva
      key={ubicacion.key}
      contador={contador}
      onAbrir={onAbrir}
    >
      {children}
    </BandejaNotificacionesInteractiva>
  )
}

function BandejaNotificacionesInteractiva({
  contador,
  children,
  onAbrir,
}: BandejaNotificacionesProps) {
  const [abierta, setAbierta] = useState(false)
  const contenedorRef = useRef<HTMLDivElement>(null)
  const botonRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const tituloId = useId()

  useEffect(() => {
    if (!abierta) return

    const cerrarAlHacerClicFuera = (event: PointerEvent) => {
      if (
        event.target instanceof Node
        && !contenedorRef.current?.contains(event.target)
      ) {
        setAbierta(false)
      }
    }
    const cerrarConEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setAbierta(false)
      botonRef.current?.focus()
    }

    document.addEventListener('pointerdown', cerrarAlHacerClicFuera)
    document.addEventListener('keydown', cerrarConEscape)
    return () => {
      document.removeEventListener('pointerdown', cerrarAlHacerClicFuera)
      document.removeEventListener('keydown', cerrarConEscape)
    }
  }, [abierta])

  const alternarBandeja = () => {
    const proximoValor = !abierta
    setAbierta(proximoValor)
    if (proximoValor) onAbrir?.()
  }

  const cerrarBandeja = () => {
    setAbierta(false)
    botonRef.current?.focus()
  }

  return (
    <div className="bandeja-notificaciones" ref={contenedorRef}>
      <button
        ref={botonRef}
        type="button"
        className="bandeja-notificaciones-trigger"
        aria-label={contador > 0 ? `Notificaciones: ${contador} avisos activos` : 'Notificaciones'}
        aria-expanded={abierta}
        aria-controls={panelId}
        onClick={alternarBandeja}
      >
        <svg aria-hidden="true" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
        </svg>
        {contador > 0 && (
          <span className="bandeja-notificaciones-contador" aria-hidden="true">
            {contador}
          </span>
        )}
      </button>

      {abierta && (
        <section
          className="bandeja-notificaciones-panel"
          id={panelId}
          aria-labelledby={tituloId}
        >
          <header className="bandeja-notificaciones-cabecera">
            <h2 id={tituloId}>Notificaciones</h2>
            <button
              type="button"
              className="btn-icon bandeja-notificaciones-cerrar"
              aria-label="Cerrar notificaciones"
              onClick={cerrarBandeja}
            >
              ×
            </button>
          </header>
          <div className="bandeja-notificaciones-contenido">{children}</div>
        </section>
      )}
    </div>
  )
}
