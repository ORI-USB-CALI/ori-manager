import { useState, type FormEvent } from 'react'

import { ApiError } from '../../api/http'
import type { AlcanceConvenio, ConvenioRead } from '../../api/convenios'
import { useCreateConvenio } from './useConvenios'

interface ConvenioFormProps {
  onCreated: (convenio: ConvenioRead) => void
}

function parsePositiveInt(value: string): number | null {
  if (value.trim() === '') {
    return null
  }

  const parsed = Number(value)

  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null
  }

  return parsed
}

export function ConvenioForm({ onCreated }: ConvenioFormProps) {
  const [solicitudId, setSolicitudId] = useState('')
  const [tieneAliado, setTieneAliado] = useState(false)
  const [aliadoId, setAliadoId] = useState('')
  const [creadoPorId, setCreadoPorId] = useState('')
  const [objeto, setObjeto] = useState('')
  const [alcance, setAlcance] = useState<AlcanceConvenio | ''>('')
  const [formError, setFormError] = useState<string | null>(null)

  const crearConvenio = useCreateConvenio()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    const solicitudIdValue = parsePositiveInt(solicitudId)
    const creadoPorIdValue = parsePositiveInt(creadoPorId)
    const aliadoIdValue = tieneAliado ? parsePositiveInt(aliadoId) : null

    if (solicitudIdValue === null) {
      setFormError('Ingresa el id de la solicitud que dio origen al convenio (numero entero mayor a 0).')
      return
    }

    if (creadoPorIdValue === null) {
      setFormError('Ingresa el id del usuario responsable de la creacion (numero entero mayor a 0).')
      return
    }

    if (tieneAliado && aliadoIdValue === null) {
      setFormError('Ingresa el id del aliado, o desmarca la casilla si el aliado aun no existe.')
      return
    }

    crearConvenio.mutate(
      {
        solicitud_id: solicitudIdValue,
        creado_por_id: creadoPorIdValue,
        aliado_id: aliadoIdValue,
        objeto: objeto.trim() === '' ? null : objeto.trim(),
        alcance: alcance === '' ? null : alcance,
      },
      {
        onSuccess: (convenio) => onCreated(convenio),
      },
    )
  }

  const apiError = crearConvenio.error instanceof ApiError ? crearConvenio.error.message : null

  return (
    <form className="convenio-form" onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="solicitud_id">Solicitud de origen *</label>
        <input
          id="solicitud_id"
          type="number"
          min={1}
          inputMode="numeric"
          value={solicitudId}
          onChange={(event) => setSolicitudId(event.target.value)}
          placeholder="Id de la solicitud"
          required
        />
        <p className="form-hint">Toda solicitud origina, a lo sumo, un convenio.</p>
      </div>

      <div className="form-field">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={tieneAliado}
            onChange={(event) => {
              setTieneAliado(event.target.checked)
              if (!event.target.checked) {
                setAliadoId('')
              }
            }}
          />
          Ya existe un aliado registrado para este convenio
        </label>

        {tieneAliado ? (
          <>
            <label htmlFor="aliado_id">Aliado</label>
            <input
              id="aliado_id"
              type="number"
              min={1}
              inputMode="numeric"
              value={aliadoId}
              onChange={(event) => setAliadoId(event.target.value)}
              placeholder="Id del aliado"
            />
          </>
        ) : (
          <p className="form-hint">
            Puedes registrar el convenio sin aliado. No se creara un aliado automaticamente; podras
            asociarlo mas adelante.
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor="creado_por_id">Usuario responsable *</label>
        <input
          id="creado_por_id"
          type="number"
          min={1}
          inputMode="numeric"
          value={creadoPorId}
          onChange={(event) => setCreadoPorId(event.target.value)}
          placeholder="Id de tu usuario"
          required
        />
        <p className="form-hint">
          Temporal: mientras no exista inicio de sesion, ingresa manualmente tu id de usuario.
        </p>
      </div>

      <div className="form-field">
        <label htmlFor="alcance">Alcance</label>
        <select
          id="alcance"
          value={alcance}
          onChange={(event) => setAlcance(event.target.value as AlcanceConvenio | '')}
        >
          <option value="">Sin definir</option>
          <option value="PROGRAMA">Programa academico especifico</option>
          <option value="INSTITUCIONAL">Toda la universidad</option>
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="objeto">Objeto del convenio</label>
        <textarea
          id="objeto"
          value={objeto}
          onChange={(event) => setObjeto(event.target.value)}
          placeholder="Descripcion breve del proposito del convenio"
          rows={4}
        />
      </div>

      {(formError || apiError) && <p className="form-error">{formError ?? apiError}</p>}

      <button type="submit" disabled={crearConvenio.isPending}>
        {crearConvenio.isPending ? 'Creando...' : 'Crear registro base'}
      </button>
    </form>
  )
}
