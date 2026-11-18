import type { ReactNode } from 'react'

/** Identidad tipográfica; no sustituye ni representa un escudo oficial. */
export function IdentidadInstitucional({ acceso = false }: { acceso?: boolean }) {
  return <div className={`identidad-institucional${acceso ? ' identidad-institucional--acceso' : ''}`}>
    <strong>ORI Manager</strong>
    <span>Universidad de San Buenaventura Cali</span>
    <span className="identidad-area">Oficina de Relaciones Interinstitucionales</span>
  </div>
}

export function CabeceraPublica({ children }: { children?: ReactNode }) {
  return <header className="cabecera-institucional">
    <IdentidadInstitucional />
    {children}
  </header>
}

export function PieInstitucional() {
  return <footer className="pie-institucional">
    Universidad de San Buenaventura Cali · ORI Manager
  </footer>
}
