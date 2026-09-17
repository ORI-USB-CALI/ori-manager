import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export function HomePage() {
  const [aliadoId, setAliadoId] = useState('')
  const navigate = useNavigate()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (aliadoId.trim()) {
      navigate(`/aliados/${aliadoId.trim()}`)
    }
  }

  return (
    <div>
      <header className="navbar">
        <Link to="/" className="navbar-brand">
          Sistema <span>ORI</span> USB Cali
        </Link>
        <div className="user-profile">
          <span>Usuario ORI</span>
        </div>
      </header>

      <main className="main-content">
        <div className="header-banner">
          <h1>Oficina de Relaciones Internacionales (ORI)</h1>
          <p>
            Plataforma de gestión institucional de convenios y aliados estratégicos — Universidad de San Buenaventura Cali.
          </p>
        </div>

        <div className="card">
          <h2>Consulta de Aliados y Convenios</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', marginTop: '4px' }}>
            Ingrese el UUID del aliado para consultar su perfil detallado y el listado de convenios asociados.
          </p>

          <form onSubmit={handleSearch} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Ej: 123e4567-e89b-12d3-a456-426614174000"
              value={aliadoId}
              onChange={(e) => setAliadoId(e.target.value)}
              style={{ flex: 1, minWidth: '280px' }}
            />
            <button type="submit" className="btn btn-primary">
              Consultar Detalle
            </button>
          </form>
        </div>
      </main>

      <footer className="footer-internal">
        <span>© Universidad de San Buenaventura Cali — Sistema de Gestión ORI</span>
        <div>
          <span>v1.0.0</span>
        </div>
      </footer>
    </div>
  )
}
