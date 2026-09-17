import { Link, useNavigate } from 'react-router-dom'

import { ConvenioForm } from '../features/convenios/ConvenioForm'

export function ConvenioNuevoPage() {
  const navigate = useNavigate()

  return (
    <main className="page">
      <Link to="/">Volver al inicio</Link>
      <h1>Registrar convenio</h1>
      <p>Registra la informacion base del convenio para disponer de una estructura inicial sobre la cual gestionar su ciclo de vida.</p>

      <ConvenioForm onCreated={(convenio) => navigate(`/convenios/${convenio.id}`)} />
    </main>
  )
}
