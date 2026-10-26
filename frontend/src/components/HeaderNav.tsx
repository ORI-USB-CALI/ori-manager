import { useEffect, useId, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

export interface EnlaceNav {
  to: string
  label: string
  end?: boolean
}

interface HeaderNavProps {
  enlaces: EnlaceNav[]
}

/**
 * HT-04: navegación principal del header, adaptada a distintos anchos de
 * pantalla. En pantallas anchas el CSS la muestra siempre como una fila
 * horizontal (el botón de menú queda oculto). Por debajo del punto de
 * quiebre (ver .navbar-menu-boton en index.css) se colapsa detrás de un
 * botón de menú, en vez de desbordar o depender de scroll horizontal.
 *
 * Se remonta en cada cambio de ruta (mismo patrón que BandejaNotificaciones)
 * para que el menú quede siempre cerrado al navegar, incluso si la
 * navegación no pasó por un clic directo sobre un NavLink.
 */
export function HeaderNav({ enlaces }: HeaderNavProps) {
  const ubicacion = useLocation()
  return <HeaderNavInteractiva key={ubicacion.pathname} enlaces={enlaces} />
}

function HeaderNavInteractiva({ enlaces }: HeaderNavProps) {
  const [abierto, setAbierto] = useState(false)
  const contenedorRef = useRef<HTMLDivElement>(null)
  const botonRef = useRef<HTMLButtonElement>(null)
  const idPanel = useId()

  useEffect(() => {
    if (!abierto) return

    const cerrarAlHacerClicFuera = (evento: PointerEvent) => {
      if (
        evento.target instanceof Node
        && !contenedorRef.current?.contains(evento.target)
      ) {
        setAbierto(false)
      }
    }
    const cerrarConEscape = (evento: KeyboardEvent) => {
      if (evento.key !== 'Escape') return
      setAbierto(false)
      botonRef.current?.focus()
    }

    document.addEventListener('pointerdown', cerrarAlHacerClicFuera)
    document.addEventListener('keydown', cerrarConEscape)
    return () => {
      document.removeEventListener('pointerdown', cerrarAlHacerClicFuera)
      document.removeEventListener('keydown', cerrarConEscape)
    }
  }, [abierto])

  return (
    <div className="navbar-menu" ref={contenedorRef}>
      <button
        ref={botonRef}
        type="button"
        className="navbar-menu-boton"
        aria-label={abierto ? 'Cerrar menú de navegación' : 'Abrir menú de navegación'}
        aria-expanded={abierto}
        aria-controls={idPanel}
        onClick={() => setAbierto((valor) => !valor)}
      >
        <svg aria-hidden="true" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          {abierto ? (
            <path d="M6 6l12 12M18 6L6 18" />
          ) : (
            <path d="M4 7h16M4 12h16M4 17h16" />
          )}
        </svg>
      </button>

      <nav
        id={idPanel}
        className={`navbar-links${abierto ? ' navbar-links-abierto' : ''}`}
        aria-label="Navegación principal"
      >
        {enlaces.map((enlace) => (
          <NavLink
            key={enlace.to}
            to={enlace.to}
            end={enlace.end}
            onClick={() => setAbierto(false)}
          >
            {enlace.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
