import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export function HomePage() {
  const [buscarId, setBuscarId] = useState('')
  const navigate = useNavigate()

  function handleBuscar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = Number(buscarId)

    if (Number.isInteger(id) && id > 0) {
      navigate(`/convenios/${id}`)
    }
  }

  return (
    <main className="page">
      <h1>ORI Manager</h1>
      <p>Frontend base configured successfully.</p>

      <section>
        <h2>Convenios</h2>
        <p>
          <Link to="/convenios/nuevo">Registrar convenio</Link>
        </p>

        <form className="convenio-form" onSubmit={handleBuscar}>
          <div className="form-field">
            <label htmlFor="buscar_id">Consultar convenio por id</label>
            <input
              id="buscar_id"
              type="number"
              min={1}
              inputMode="numeric"
              value={buscarId}
              onChange={(event) => setBuscarId(event.target.value)}
              placeholder="Id del convenio"
            />
          </div>
          <button type="submit">Consultar</button>
        </form>
      </section>
    </main>
  )
}
