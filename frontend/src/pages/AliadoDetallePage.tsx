import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useSesion } from '../auth/sesion'
import { type AliadoPerfil, ETIQUETA_TIPO, TIPOS_IDENTIFICACION, type TipoAliado } from './epica02'

function fecha(valor: string | null) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

export function AliadoDetallePage() {
  const { aliadoId } = useParams()
  const id = Number(aliadoId)
  const { puede } = useSesion()
  const cliente = useQueryClient()
  const [editando, setEditando] = useState(false)
  const aliado = useQuery({
    queryKey: ['aliado', id],
    queryFn: () => apiFetch<AliadoPerfil>(`/aliados/${id}`),
    enabled: Number.isInteger(id),
    retry: false,
  })
  const estado = useMutation({
    mutationFn: (activo: boolean) => apiFetch(`/aliados/${id}/estado`, { method: 'PATCH', body: JSON.stringify({ activo }) }),
    onSuccess: () => cliente.invalidateQueries({ queryKey: ['aliado', id] }),
  })
  const editar = useMutation({
    mutationFn: (datos: {
      ordinarios: Record<string, unknown>
      identidad: { tipo_identificacion: string; identificacion: string } | null
    }) => apiFetch(`/aliados/${id}${datos.identidad ? '/administracion' : ''}`, {
      method: 'PATCH',
      body: JSON.stringify(datos.identidad ? { ...datos.ordinarios, ...datos.identidad } : datos.ordinarios),
    }),
    onSuccess: async () => { await cliente.invalidateQueries({ queryKey: ['aliado', id] }); setEditando(false) },
  })

  function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const tipoIdentificacion = String(form.get('tipo_identificacion') ?? '')
    const identificacion = String(form.get('identificacion') ?? '').trim()
    editar.mutate({
      ordinarios: {
        nombre: String(form.get('nombre') ?? '').trim(),
        ciudad: String(form.get('ciudad') ?? '').trim() || null,
        correo: String(form.get('correo') ?? '').trim() || null,
        telefono: String(form.get('telefono') ?? '').trim() || null,
      },
      identidad: puede('aliados.corregir_identificacion')
        ? { tipo_identificacion: tipoIdentificacion, identificacion }
        : null,
    })
  }

  if (aliado.isPending) return <p className="estado-pagina">Cargando perfil…</p>
  if (aliado.isError) {
    const error = aliado.error
    return <section className="card estado-vacio"><h1>{error instanceof ApiError && error.status === 404 ? 'Aliado no encontrado' : error instanceof ApiError && error.status === 403 ? 'Acceso denegado' : 'No se pudo cargar el aliado'}</h1><Link to="/aliados">Volver a aliados</Link></section>
  }
  if (!aliado.data) return null
  const datos = aliado.data
  const error = editar.error ?? estado.error

  return (
    <>
      <div className="page-toolbar"><div><Link to="/aliados">← Aliados</Link><h1>{datos.nombre}</h1></div><span className={`badge ${datos.activo ? 'badge-activo' : 'badge-inactivo'}`}>{datos.activo ? 'ACTIVO' : 'INACTIVO'}</span></div>
      {error && <p className="alert-error">{error instanceof Error ? error.message : 'No fue posible guardar.'}</p>}
      <section className="card">
        <h2>Información del aliado</h2>
        {editando ? (
          <form onSubmit={guardar} className="form-grid">
            <label className="form-group form-span-2"><span className="form-label">Nombre</span><input className="form-control" name="nombre" defaultValue={datos.nombre} required /></label>
            <label className="form-group"><span className="form-label">Tipo de identificación</span><select className="form-control" name="tipo_identificacion" defaultValue={datos.tipo_identificacion} disabled={!puede('aliados.corregir_identificacion')}>{TIPOS_IDENTIFICACION.map((tipo) => <option key={tipo} value={tipo}>{tipo.replaceAll('_', ' ')}</option>)}</select></label>
            <label className="form-group"><span className="form-label">NIT / documento</span><input className="form-control" name="identificacion" maxLength={40} defaultValue={datos.identificacion} readOnly={!puede('aliados.corregir_identificacion')} required /></label>
            <label className="form-group"><span className="form-label">Ciudad</span><input className="form-control" name="ciudad" defaultValue={datos.ciudad ?? ''} /></label>
            <label className="form-group"><span className="form-label">Correo</span><input className="form-control" type="email" name="correo" defaultValue={datos.correo ?? ''} /></label>
            <label className="form-group"><span className="form-label">Teléfono</span><input className="form-control" name="telefono" defaultValue={datos.telefono ?? ''} /></label>
            <div><button className="btn btn-primary" disabled={editar.isPending}>Guardar</button> <button className="btn btn-outline" type="button" onClick={() => setEditando(false)}>Cancelar</button></div>
          </form>
        ) : (
          <dl><dt>Tipo de identificación</dt><dd>{datos.tipo_identificacion}</dd><dt>NIT / documento</dt><dd>{datos.identificacion}</dd><dt>Tipo</dt><dd>{ETIQUETA_TIPO[datos.tipo as TipoAliado]}</dd><dt>Ciudad</dt><dd>{datos.ciudad ?? '—'}</dd><dt>Correo</dt><dd>{datos.correo ?? '—'}</dd><dt>Teléfono</dt><dd>{datos.telefono ?? '—'}</dd></dl>
        )}
        <div className="page-toolbar">
          {puede('aliados.editar') && !editando && <button className="btn btn-outline" onClick={() => setEditando(true)}>Editar datos</button>}
          {puede('aliados.cambiar_estado') && <button className={datos.activo ? 'btn btn-danger' : 'btn btn-primary'} disabled={estado.isPending} onClick={() => estado.mutate(!datos.activo)}>{datos.activo ? 'Inactivar' : 'Reactivar'}</button>}
        </div>
      </section>
      <section className="card">
        <h2>Convenios asociados</h2>
        {datos.convenios.length === 0 ? <p className="texto-secundario">Actualmente no existen convenios asociados</p> : (
          <div className="table-container"><table className="table"><thead><tr><th>Código</th><th>Objeto</th><th>Estado</th><th>Inicio</th><th>Vencimiento</th></tr></thead><tbody>{datos.convenios.map((convenio) => <tr key={convenio.id}><td><Link to={`/convenios/${convenio.id}`}>{convenio.codigo ?? `#${convenio.id}`}</Link></td><td>{convenio.objeto ?? '—'}</td><td><span className="badge">{convenio.estado}</span></td><td>{fecha(convenio.fecha_inicio)}</td><td>{fecha(convenio.fecha_vencimiento)}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </>
  )
}
