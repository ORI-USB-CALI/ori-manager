import { useEffect, useId, useRef, useState } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'

export interface EnlaceNav {
  to: string
  label: string
  end?: boolean
}

export interface GrupoNav {
  label: string
  enlaces: EnlaceNav[]
}

export type ElementoNav = EnlaceNav | GrupoNav

interface HeaderNavProps {
  enlaces: ElementoNav[]
}

// Remontar al navegar también cierra los paneles en Atrás/Adelante.
export function HeaderNav({ enlaces }: HeaderNavProps) {
  const ubicacion = useLocation()
  return <HeaderNavInteractiva key={ubicacion.pathname} enlaces={enlaces} />
}

function HeaderNavInteractiva({ enlaces }: HeaderNavProps) {
  const { pathname } = useLocation()
  const [abierto, setAbierto] = useState(false)
  const [grupoAbierto, setGrupoAbierto] = useState<string | null>(null)
  const contenedorRef = useRef<HTMLDivElement>(null)
  const botonRef = useRef<HTMLButtonElement>(null)
  const botonesGrupo = useRef(new Map<string, HTMLButtonElement>())
  const idPanel = useId()

  // La coincidencia más específica evita activar Consulta al entrar a Tablero
  // o Crear, y conserva la sección al visitar detalles e historiales.
  const enlaceActivo = enlaces
    .flatMap((elemento) => 'enlaces' in elemento ? elemento.enlaces : [elemento])
    .filter((enlace) => matchPath({ path: enlace.to, end: enlace.end ?? false }, pathname))
    .sort((a, b) => b.to.length - a.to.length)[0]?.to

  function cerrar() {
    setAbierto(false)
    setGrupoAbierto(null)
  }

  useEffect(() => {
    if (!abierto && !grupoAbierto) return

    const cerrarAlHacerClicFuera = (evento: PointerEvent) => {
      if (
        evento.target instanceof Node
        && !contenedorRef.current?.contains(evento.target)
      ) {
        setAbierto(false)
        setGrupoAbierto(null)
      }
    }
    const cerrarConEscape = (evento: KeyboardEvent) => {
      if (evento.key !== 'Escape') return
      if (grupoAbierto) {
        setGrupoAbierto(null)
        botonesGrupo.current.get(grupoAbierto)?.focus()
        return
      }
      setAbierto(false)
      botonRef.current?.focus()
    }

    document.addEventListener('pointerdown', cerrarAlHacerClicFuera)
    document.addEventListener('keydown', cerrarConEscape)
    return () => {
      document.removeEventListener('pointerdown', cerrarAlHacerClicFuera)
      document.removeEventListener('keydown', cerrarConEscape)
    }
  }, [abierto, grupoAbierto])

  function renderEnlace(enlace: EnlaceNav) {
    const activo = enlace.to === enlaceActivo
    return (
      <Link
        key={enlace.to}
        to={enlace.to}
        className={activo ? 'active' : undefined}
        aria-current={activo ? 'page' : undefined}
        onClick={cerrar}
      >
        {enlace.label}
      </Link>
    )
  }

  return (
    <div className="navbar-menu" ref={contenedorRef}>
      <button
        ref={botonRef}
        type="button"
        className="navbar-menu-boton"
        aria-label={abierto ? 'Cerrar menú de navegación' : 'Abrir menú de navegación'}
        aria-expanded={abierto}
        aria-controls={idPanel}
        onClick={() => {
          setAbierto((valor) => !valor)
          setGrupoAbierto(null)
        }}
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
        {enlaces.map((elemento, indice) => 'enlaces' in elemento ? (
          <div
            className="navbar-grupo"
            key={elemento.label}
            onBlur={(evento) => {
              if (!evento.currentTarget.contains(evento.relatedTarget)) setGrupoAbierto(null)
            }}
          >
            <button
              type="button"
              className="navbar-grupo-boton"
              ref={(boton) => {
                if (boton) botonesGrupo.current.set(elemento.label, boton)
                else botonesGrupo.current.delete(elemento.label)
              }}
              aria-expanded={grupoAbierto === elemento.label}
              aria-controls={`${idPanel}-grupo-${indice}`}
              data-active={elemento.enlaces.some((enlace) => enlace.to === enlaceActivo)}
              onClick={() => setGrupoAbierto((actual) => actual === elemento.label ? null : elemento.label)}
            >
              {elemento.label} <span aria-hidden="true">▾</span>
            </button>
            <div
              id={`${idPanel}-grupo-${indice}`}
              className="navbar-submenu"
              hidden={grupoAbierto !== elemento.label}
            >
              {elemento.enlaces.map(renderEnlace)}
            </div>
          </div>
        ) : renderEnlace(elemento))}
      </nav>
    </div>
  )
}
