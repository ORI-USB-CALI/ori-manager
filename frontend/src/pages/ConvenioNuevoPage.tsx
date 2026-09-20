import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { type Convenio, useAliados } from './epica02'

export function ConvenioNuevoPage() {
  const navigate = useNavigate()
  const aliados = useAliados(true)
  const [alcance, setAlcance] = useState('INSTITUCIONAL')
  const crear = useMutation({
    mutationFn: (datos: Record<string, unknown>) =>
      apiFetch<Convenio>('/convenios', { method: 'POST', body: JSON.stringify(datos) }),
    onSuccess: (convenio) => navigate(`/convenios/${convenio.id}`),
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const aliadoId = String(form.get('aliado_id') ?? '')
    const unidadId = String(form.get('unidad_organizacional_id') ?? '')
    crear.mutate({
      solicitud_id: Number(form.get('solicitud_id')),
      aliado_id: aliadoId ? Number(aliadoId) : null,
      objeto: String(form.get('objeto') ?? '').trim(),
      alcance,
      unidad_organizacional_id: unidadId ? Number(unidadId) : null,
    })
  }

  return (
    <>
      <section className="header-banner"><h1>Nuevo convenio</h1><p>Registre la información base. El estado inicial será EN_TRAMITE.</p></section>
      <form className="card" onSubmit={enviar}>
        <div className="form-grid">
          <label className="form-group"><span className="form-label">Solicitud de origen</span><input className="form-control" name="solicitud_id" type="number" min="1" required /></label>
          <label className="form-group"><span className="form-label">Aliado (opcional)</span><select className="form-control select" name="aliado_id"><option value="">Sin aliado asociado</option>{aliados.data?.items.map((aliado) => <option key={aliado.id} value={aliado.id}>{aliado.nombre} — {aliado.identificacion}</option>)}</select></label>
          <label className="form-group"><span className="form-label">Alcance</span><select className="form-control select" value={alcance} onChange={(e) => setAlcance(e.target.value)}><option value="INSTITUCIONAL">Institucional</option><option value="PROGRAMA">Programa</option></select></label>
          {alcance === 'PROGRAMA' && <label className="form-group"><span className="form-label">ID unidad organizacional</span><input className="form-control" name="unidad_organizacional_id" type="number" min="1" required /></label>}
          <label className="form-group form-span-2"><span className="form-label">Objeto</span><textarea className="form-control" name="objeto" required /></label>
        </div>
        {crear.isError && <p className="alert-error">{crear.error instanceof ApiError ? crear.error.message : 'No fue posible crear el convenio.'}</p>}
        <div className="page-toolbar"><Link className="btn btn-outline" to="/">Cancelar</Link><button className="btn btn-primary" disabled={crear.isPending}>{crear.isPending ? 'Creando…' : 'Crear convenio'}</button></div>
      </form>
    </>
  )
}
