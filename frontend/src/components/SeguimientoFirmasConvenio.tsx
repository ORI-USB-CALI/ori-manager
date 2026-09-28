import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'

interface InvitacionFirma {
  id: number
  expira_en: string
  enviado_en: string | null
  utilizado_en: string | null
  revocado_en: string | null
  estado: string
}

interface FirmaConvenio {
  id: number
  orden: number
  rol_firmante: string
  parte: string
  nombre_firmante: string | null
  cargo_firmante: string | null
  correo_firmante: string | null
  modalidad: 'ELECTRONICA' | 'FISICA' | null
  estado: 'PENDIENTE' | 'FIRMADA'
  fecha_firma: string | null
  configurada: boolean
  invitaciones: InvitacionFirma[]
}

interface ProcesoFirmas {
  id: number
  estado: 'CONFIGURACION' | 'EN_CURSO' | 'COMPLETADO' | 'CANCELADO'
  version_convenio_id: number
  version_numero: number
  firmas: FirmaConvenio[]
}

function etiqueta(valor: string | null): string {
  if (!valor) return '—'
  return valor.toLowerCase().replaceAll('_', ' ').replace(/^./, (letra) => letra.toUpperCase())
}

function fecha(valor: string | null): string {
  return valor ? new Date(valor).toLocaleString() : '—'
}

function invitacionReciente(firma: FirmaConvenio): InvitacionFirma | null {
  return firma.invitaciones.reduce<InvitacionFirma | null>((ultima, invitacion) => {
    if (!ultima) return invitacion
    return invitacion.id > ultima.id ? invitacion : ultima
  }, null)
}

function ConfiguracionFirma({ convenioId, firma }: { convenioId: number; firma: FirmaConvenio }) {
  const cliente = useQueryClient()
  const notify = useNotifications()
  const [nombre, setNombre] = useState(firma.nombre_firmante ?? '')
  const [cargo, setCargo] = useState(firma.cargo_firmante ?? '')
  const [correo, setCorreo] = useState(firma.correo_firmante ?? '')
  const [modalidad, setModalidad] = useState<'ELECTRONICA' | 'FISICA'>(firma.modalidad ?? 'ELECTRONICA')
  const guardar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/firmas/${firma.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ nombre, cargo, correo: correo.trim() || null, modalidad }),
    }),
    onSuccess: async () => {
      notify({ type: 'success', message: `Firmante ${firma.orden} configurado.` })
      await cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'firmas'] })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible configurar el firmante.' }),
  })
  return (
    <div className="firma-configuracion">
      <label className="form-group"><span className="form-label">Nombre</span><input className="form-control" value={nombre} maxLength={160} onChange={(event) => setNombre(event.target.value)} /></label>
      <label className="form-group"><span className="form-label">Cargo</span><input className="form-control" value={cargo} maxLength={160} onChange={(event) => setCargo(event.target.value)} /></label>
      <label className="form-group"><span className="form-label">Modalidad</span><select className="form-control" value={modalidad} onChange={(event) => setModalidad(event.target.value as 'ELECTRONICA' | 'FISICA')}><option value="ELECTRONICA">Electrónica</option><option value="FISICA">Física</option></select></label>
      <label className="form-group"><span className="form-label">Correo {modalidad === 'ELECTRONICA' ? '*' : '(opcional)'}</span><input className="form-control" type="email" value={correo} maxLength={320} onChange={(event) => setCorreo(event.target.value)} /></label>
      <button className="btn btn-outline btn-small" type="button" disabled={!nombre.trim() || !cargo.trim() || (modalidad === 'ELECTRONICA' && !correo.trim()) || guardar.isPending} onClick={() => guardar.mutate()}>{guardar.isPending ? 'Guardando…' : 'Guardar firmante'}</button>
    </div>
  )
}

export function SeguimientoFirmasConvenio({ convenioId }: { convenioId: number }) {
  const cliente = useQueryClient()
  const notify = useNotifications()
  const proceso = useQuery({
    queryKey: ['convenio', convenioId, 'firmas'],
    queryFn: () => apiFetch<ProcesoFirmas>(`/convenios/${convenioId}/firmas`),
    retry: false,
  })
  const refrescar = () => cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'firmas'] })
  const iniciar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/firmas/iniciar`, { method: 'POST' }),
    onSuccess: async () => { notify({ type: 'success', message: 'Proceso de firmas iniciado.' }); await refrescar() },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible iniciar el proceso.' }),
  })
  const enviar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/firmas/enviar`, { method: 'POST' }),
    onSuccess: async () => { notify({ type: 'success', message: 'Invitaciones electrónicas enviadas.' }); await refrescar() },
    onError: async (error) => { notify({ type: 'error', message: error instanceof Error ? error.message : 'Hubo fallos al entregar las invitaciones.' }); await refrescar() },
  })
  const reenviar = useMutation({
    mutationFn: (firmaId: number) => apiFetch(`/convenios/${convenioId}/firmas/${firmaId}/reenviar`, { method: 'POST' }),
    onSuccess: async () => { notify({ type: 'success', message: 'Se generó y envió un nuevo enlace.' }); await refrescar() },
    onError: async (error) => { notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible reenviar el enlace.' }); await refrescar() },
  })

  if (proceso.isPending) return <p className="estado-pagina">Cargando proceso de firmas…</p>
  if (proceso.isError || !proceso.data) return null
  const datos = proceso.data
  const completadas = datos.firmas.filter((firma) => firma.estado === 'FIRMADA').length
  const electronicas = datos.firmas.filter((firma) => firma.modalidad === 'ELECTRONICA')
  const algunaInvitacion = electronicas.some((firma) => firma.invitaciones.length > 0)
  const todasConfiguradas = datos.firmas.length === 7 && datos.firmas.every((firma) => firma.configurada)

  return (
    <section className="card seguimiento-firmas">
      <div className="revision-contraparte-cabecera">
        <div><h2>Proceso de firmas</h2><p className="section-help">Versión congelada del proceso: {datos.version_numero}</p></div>
        <span className="badge badge-pendiente">{completadas} de 7 firmas completadas</span>
      </div>
      <div className="firmas-lista">
        {datos.firmas.map((firma) => {
          const invitacion = invitacionReciente(firma)
          return (
            <article className="firma-seguimiento" key={firma.id}>
              <div className="firma-seguimiento-cabecera"><strong>{firma.orden}. {etiqueta(firma.rol_firmante)}</strong><span className="badge badge-neutral">{etiqueta(firma.estado)}</span></div>
              {datos.estado === 'CONFIGURACION' ? <ConfiguracionFirma convenioId={convenioId} firma={firma} /> : (
                <dl className="proyecto-datos">
                  <dt>Nombre</dt><dd>{firma.nombre_firmante ?? '—'}</dd><dt>Cargo</dt><dd>{firma.cargo_firmante ?? '—'}</dd>
                  <dt>Correo</dt><dd>{firma.correo_firmante ?? '—'}</dd><dt>Modalidad</dt><dd>{etiqueta(firma.modalidad)}</dd>
                  <dt>Fecha de firma</dt><dd>{fecha(firma.fecha_firma)}</dd><dt>Invitación</dt><dd>{firma.modalidad === 'FISICA' ? 'Requiere carga posterior del documento firmado' : invitacion ? etiqueta(invitacion.estado) : 'Sin enviar'}</dd>
                </dl>
              )}
              {datos.estado === 'EN_CURSO' && firma.modalidad === 'ELECTRONICA' && firma.estado === 'PENDIENTE' && invitacion && (
                <button className="btn btn-outline btn-small" type="button" disabled={reenviar.isPending} onClick={() => reenviar.mutate(firma.id)}>Reenviar enlace</button>
              )}
            </article>
          )
        })}
      </div>
      <div className="page-toolbar">
        {datos.estado === 'CONFIGURACION' && <button className="btn btn-primary" type="button" disabled={!todasConfiguradas || iniciar.isPending} onClick={() => iniciar.mutate()}>{iniciar.isPending ? 'Iniciando…' : 'Iniciar proceso de firmas'}</button>}
        {datos.estado === 'EN_CURSO' && electronicas.length > 0 && !algunaInvitacion && <button className="btn btn-primary" type="button" disabled={enviar.isPending} onClick={() => enviar.mutate()}>{enviar.isPending ? 'Enviando…' : 'Enviar invitaciones electrónicas'}</button>}
      </div>
    </section>
  )
}
