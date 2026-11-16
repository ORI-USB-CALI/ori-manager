import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { enumLabel } from '../components/tableFormatters'
import { CampoLectura, DetalleCampos } from '../components/DetalleCampos'
import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { volverA } from '../components/retornoVolver'
import { type AliadoPerfil, ETIQUETA_TIPO, referenciaConvenio, type TipoAliado, TIPOS_IDENTIFICACION } from './epica02'

function fecha(valor: string | null) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

export function AliadoDetallePage() {
  const retorno = volverA(useLocation(), 'Volver al aliado')
  const { aliadoId } = useParams()
  const id = Number(aliadoId)
  const { puede } = useSesion()
  const notify = useNotifications()
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
    onSuccess: (_respuesta, activo) => {
      void cliente.invalidateQueries({ queryKey: ['aliado', id] })
      notify({ type: 'success', message: activo ? 'Aliado reactivado correctamente.' : 'Aliado inactivado correctamente.' })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof ApiError ? error.message : 'No fue posible cambiar el estado del aliado.' }),
  })
  const editar = useMutation({
    mutationFn: (datos: {
      ordinarios: Record<string, unknown>
      identidad: { tipo_identificacion: string; identificacion: string } | null
    }) => apiFetch(`/aliados/${id}${datos.identidad ? '/administracion' : ''}`, {
      method: 'PATCH',
      body: JSON.stringify(datos.identidad ? { ...datos.ordinarios, ...datos.identidad } : datos.ordinarios),
    }),
    onSuccess: async () => {
      await cliente.invalidateQueries({ queryKey: ['aliado', id] })
      setEditando(false)
      notify({ type: 'success', message: 'Aliado actualizado correctamente.' })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof ApiError ? error.message : 'No fue posible guardar el aliado.' }),
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
    return <section className="card estado-vacio"><h1>{error instanceof ApiError && error.status === 404 ? 'Aliado no encontrado' : error instanceof ApiError && error.status === 403 ? 'Acceso denegado' : 'No se pudo cargar el aliado'}</h1><Link className="btn accion-volver" to="/aliados">Volver a aliados</Link></section>
  }
  if (!aliado.data) return null
  const datos = aliado.data

  return (
    <div className="detalle-secciones">
      <div className="page-toolbar"><div><Link className="btn accion-volver" to="/aliados">← Aliados</Link><h1>{datos.nombre}</h1></div><span className={`badge ${datos.activo ? 'badge-activo' : 'badge-inactivo'}`}>{datos.activo ? 'ACTIVO' : 'INACTIVO'}</span></div>
      <section className="card">
        <h2>Información del aliado</h2>
        {editando ? (
          <form onSubmit={guardar} className="form-grid">
            <label className="form-group form-span-2" htmlFor="aliado-nombre"><span className="form-label">Nombre</span><input id="aliado-nombre" className="form-control" name="nombre" defaultValue={datos.nombre} required placeholder="Razón social o nombre oficial de la institución" /></label>
            <label className="form-group" htmlFor="aliado-tipo-identificacion"><span className="form-label">Tipo de identificación</span><select id="aliado-tipo-identificacion" className="form-control" name="tipo_identificacion" defaultValue={datos.tipo_identificacion} disabled={!puede('aliados.corregir_identificacion')}>{TIPOS_IDENTIFICACION.map((tipo) => <option key={tipo} value={tipo}>{tipo.replaceAll('_', ' ')}</option>)}</select></label>
            <label className="form-group" htmlFor="aliado-identificacion"><span className="form-label">NIT / documento</span><input id="aliado-identificacion" className="form-control" name="identificacion" maxLength={40} defaultValue={datos.identificacion} readOnly={!puede('aliados.corregir_identificacion')} required placeholder="Número de identificación jurídica" /></label>
            <label className="form-group" htmlFor="aliado-ciudad"><span className="form-label">Ciudad</span><input id="aliado-ciudad" className="form-control" name="ciudad" defaultValue={datos.ciudad ?? ''} placeholder="Ciudad donde se encuentra la entidad" /></label>
            <label className="form-group" htmlFor="aliado-correo"><span className="form-label">Correo</span><input id="aliado-correo" className="form-control" type="email" name="correo" defaultValue={datos.correo ?? ''} placeholder="Correo institucional de contacto" /></label>
            <label className="form-group" htmlFor="aliado-telefono"><span className="form-label">Teléfono</span><input id="aliado-telefono" className="form-control" name="telefono" defaultValue={datos.telefono ?? ''} placeholder="Número institucional de contacto" /></label>
            <div><button className="btn btn-primary" disabled={editar.isPending}>Guardar</button> <button className="btn btn-outline" type="button" onClick={() => setEditando(false)}>Cancelar</button></div>
          </form>
        ) : (
          <DetalleCampos><CampoLectura etiqueta="Tipo de identificación">{enumLabel(datos.tipo_identificacion)}</CampoLectura><CampoLectura etiqueta="NIT / documento">{datos.identificacion}</CampoLectura><CampoLectura etiqueta="Tipo">{ETIQUETA_TIPO[datos.tipo as TipoAliado]}</CampoLectura><CampoLectura etiqueta="Ciudad">{datos.ciudad ?? '—'}</CampoLectura><CampoLectura etiqueta="Correo">{datos.correo ?? '—'}</CampoLectura><CampoLectura etiqueta="Teléfono">{datos.telefono ?? '—'}</CampoLectura></DetalleCampos>
        )}
        <div className="page-toolbar">
          {puede('aliados.editar') && !editando && <button className="btn btn-outline" onClick={() => setEditando(true)}>Editar datos</button>}
          {puede('aliados.cambiar_estado') && <button className={datos.activo ? 'btn btn-danger' : 'btn btn-primary'} disabled={estado.isPending} onClick={() => estado.mutate(!datos.activo)}>{datos.activo ? 'Inactivar' : 'Reactivar'}</button>}
        </div>
      </section>
      <section className="card tabla-seccion">
        <h2>Convenios asociados</h2>
        {datos.convenios.length === 0 ? <p className="texto-secundario">Actualmente no existen convenios asociados</p> : (
          <div className="table-container tabla-densa-region" role="region" aria-label="Convenios asociados" tabIndex={0}><table className="table tabla-densa"><thead><tr><th scope="col" className="tabla-col-referencia">Código</th><th scope="col" className="tabla-col-descripcion">Objeto</th><th scope="col" className="tabla-col-estado">Estado</th><th scope="col" className="tabla-col-fecha">Inicio</th><th scope="col" className="tabla-col-fecha">Vencimiento</th></tr></thead><tbody>{datos.convenios.map((convenio) => <tr key={convenio.id}><td className="tabla-col-referencia"><Link to={`/convenios/${convenio.id}`} state={retorno}>{referenciaConvenio(convenio.codigo, convenio.id)}</Link></td><td className="tabla-col-descripcion">{convenio.objeto ?? '—'}</td><td className="tabla-col-estado"><span className="badge">{convenio.estado}</span></td><td className="tabla-col-fecha">{fecha(convenio.fecha_inicio)}</td><td className="tabla-col-fecha">{fecha(convenio.fecha_vencimiento)}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </div>
  )
}
