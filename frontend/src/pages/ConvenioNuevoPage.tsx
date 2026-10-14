import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useAliados, type Convenio } from './epica02'

export function ConvenioNuevoPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const notify = useNotifications()
  const aliados = useAliados(true)
  const [objeto, setObjeto] = useState('')
  const [aliadoId, setAliadoId] = useState('')
  const crear = useMutation({
    mutationFn: () => apiFetch<Convenio>('/convenios/manual', {
      method: 'POST',
      body: JSON.stringify({
        objeto: objeto.trim() || null,
        aliado_id: aliadoId ? Number(aliadoId) : null,
      }),
    }),
    onSuccess: async (convenio) => {
      await queryClient.invalidateQueries({ queryKey: ['convenios'] })
      notify({ type: 'success', message: 'Convenio manual creado. Puedes empezar a elaborar el documento.' })
      navigate(`/convenios/${convenio.id}/elaboracion`)
    },
    onError: (error) => notify({
      type: 'error', message: error instanceof Error ? error.message : 'No se pudo crear el convenio.',
    }),
  })

  function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!crear.isPending) crear.mutate()
  }

  return (
    <>
      <section className="header-banner">
        <h1>Crear convenio manualmente</h1>
        <p>Creación directa por ORI sin solicitud previa. Comenzará en elaboración con un documento en blanco.</p>
      </section>
      <form className="card" onSubmit={guardar}>
        <h2>Datos iniciales del convenio</h2>
        <label className="form-group">Objeto del convenio (opcional en esta etapa)
          <textarea className="form-control" value={objeto} onChange={(evento) => setObjeto(evento.target.value)} />
        </label>
        <label className="form-group">Aliado / contraparte (opcional)
          <select className="form-control select" value={aliadoId} onChange={(evento) => setAliadoId(evento.target.value)}>
            <option value="">Asociar más adelante</option>
            {aliados.data?.items.map((aliado) => (
              <option key={aliado.id} value={aliado.id}>{aliado.nombre}</option>
            ))}
          </select>
        </label>
        {aliados.isError && <p className="alert-error" role="alert">No se pudieron cargar los aliados. Puedes guardar sin seleccionar uno.</p>}
        <div className="page-toolbar">
          <button type="submit" className="btn btn-primary" disabled={crear.isPending}>
            {crear.isPending ? 'Creando…' : 'Crear y abrir editor'}
          </button>
          <Link className="btn btn-outline" to="/convenios">Cancelar</Link>
        </div>
      </form>
    </>
  )
}
