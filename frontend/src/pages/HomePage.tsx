import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <div className="header-banner">
      <div>
        <h1>ORI Manager</h1>
        <p>Sistema de gestión de la Oficina de Relaciones Internacionales.</p>
      </div>
      <Link to="/aliados" className="btn btn-primary" style={{ marginTop: '12px' }}>
        Ir a aliados
      </Link>
    </div>
  )
}
