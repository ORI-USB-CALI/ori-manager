import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <main>
      <h1>ORI Manager</h1>
      <p>Frontend base configured successfully.</p>
      <Link to="/usuarios" className="btn btn-outline">
        Ir a Usuarios
      </Link>
    </main>
  )
}
