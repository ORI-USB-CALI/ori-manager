import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useAliados, type Convenio } from './epica02'
import { fechaHoyLocal, validarVigencia, vencimientoEsperado } from './vigencia'

export function ConvenioNuevoPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const notify = useNotifications()
  const aliados = useAliados(true)
  const [objeto, setObjeto] = useState('')
  const [aliadoId, setAliadoId] = useState('')
  // HT-08: vigencia opcional; si se informa, se valida antes de enviar.
  const [fechaInicio, setFechaInicio] = useState('')
  const [duracion, setDuracion] = useState('')
  const fechaVencimiento = fechaInicio && duracion && Number(duracion) >= 4 ? vencimientoEsperado(fechaInicio, Number(duracion)) : ''
  const [errores, setErrores] = useState<Record<string, string>>({})
  const crear = useMutation({
    mutationFn: () => apiFetch<Convenio>('/convenios/manual', {
      method: 'POST',
      body: JSON.stringify({
        objeto: objeto.trim() || null,
        aliado_id: aliadoId ? Number(aliadoId) : null,
        fecha_inicio: fechaInicio || null,
        fecha_vencimiento: fechaVencimiento || null,
        duracion_meses: duracion ? Number(duracion) : null,
      }),
    }),
    onSuccess: async (convenio) => {
      await queryClient.invalidateQueries({ queryKey: ['convenios'] })
      notify({ type: 'success', message: 'Convenio manual creado. Puedes empezar a elaborar el documento.' })
      navigate(`/convenios/${convenio.id}/elaboracion`)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.detail && typeof error.detail === 'object' && 'faltantes' in error.detail && Array.isArray(error.detail.faltantes)) {
        const campos: Record<string, string> = {}
        for (const item of error.detail.faltantes) {
          if (item && typeof item.campo === 'string' && typeof item.motivo === 'string') campos[item.campo] = item.motivo
        }
        setErrores(campos)
      }
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No se pudo crear el convenio.' })
    },
  })

  function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const invalidas = validarVigencia(fechaInicio || null, fechaVencimiento || null, fechaHoyLocal(), duracion ? Number(duracion) : null)
    setErrores(invalidas)
    if (Object.keys(invalidas).length > 0) return
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
        <label className="form-group">Fecha de inicio de vigencia (opcional)
          <input className="form-control" name="fecha_inicio" type="date" value={fechaInicio} onChange={(evento) => setFechaInicio(evento.target.value)} />
        </label>
        {errores.fecha_inicio && <span className="form-error" role="alert">{errores.fecha_inicio}</span>}
        <label className="form-group">Duración (meses)
          <input className="form-control" name="duracion_meses" type="number" min="4" step="1" value={duracion} onChange={(evento) => setDuracion(evento.target.value)} />
          {errores.duracion_meses && <span className="form-error" role="alert">{errores.duracion_meses}</span>}
        </label>
        <label className="form-group">Fecha de vencimiento (opcional)
          <input className="form-control" name="fecha_vencimiento" type="date" value={fechaVencimiento} aria-invalid={Boolean(errores.fecha_vencimiento)} readOnly />
          {errores.fecha_vencimiento && <span className="form-error" role="alert">{errores.fecha_vencimiento}</span>}
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
