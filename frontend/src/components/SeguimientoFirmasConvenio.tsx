import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { ConfirmacionModal } from './ConfirmacionModal'

interface DocumentoFirma {
  id: number
  tipo: string
  nombre_archivo: string
  tipo_mime: string
  tamano_bytes: number
  creado_en: string
}

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
  estado: 'PENDIENTE' | 'FIRMADA' | 'RECHAZADA'
  fecha_firma: string | null
  documento_id: number | null
  documento: DocumentoFirma | null
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

function fechaFisica(valor: string | null): string {
  if (!valor) return '—'
  return new Date(`${valor.slice(0, 10)}T00:00:00Z`).toLocaleDateString('es-CO', {
    timeZone: 'UTC',
  })
}

function invitacionReciente(firma: FirmaConvenio): InvitacionFirma | null {
  return firma.invitaciones.reduce<InvitacionFirma | null>((ultima, invitacion) => {
    if (!ultima) return invitacion
    return invitacion.id > ultima.id ? invitacion : ultima
  }, null)
}

function claseEstadoFirma(estado: FirmaConvenio['estado']): string {
  if (estado === 'FIRMADA') return 'badge-success'
  if (estado === 'RECHAZADA') return 'badge-danger'
  return 'badge-warning'
}

function claseEstadoInvitacion(estado: string | null): string {
  if (estado === 'UTILIZADA') return 'badge-success'
  if (estado === 'PENDIENTE') return 'badge-warning'
  if (estado === 'EXPIRADA') return 'badge-danger'
  return 'badge-neutral'
}

function RegistroFirmaFisicaModal({
  convenioId,
  firmaInicial,
  firmasDisponibles,
  onCerrar,
}: {
  convenioId: number
  firmaInicial: FirmaConvenio
  firmasDisponibles: FirmaConvenio[]
  onCerrar: () => void
}) {
  const cliente = useQueryClient()
  const notify = useNotifications()
  const [firmaIds, setFirmaIds] = useState<number[]>([firmaInicial.id])
  const [fechaFirma, setFechaFirma] = useState('')
  const [archivo, setArchivo] = useState<File | null>(null)

  const registrar = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      firmaIds.forEach((firmaId) => datos.append('firma_ids', String(firmaId)))
      datos.append('fecha_firma', fechaFirma)
      datos.append('archivo', archivo!)
      return apiFetch(`/convenios/${convenioId}/firmas/fisicas`, {
        method: 'POST',
        body: datos,
      })
    },
    onSuccess: async () => {
      notify({
        type: 'success',
        message: firmaIds.length === 1
          ? 'La firma física fue registrada con su evidencia.'
          : `Se registraron ${firmaIds.length} firmas físicas con la misma evidencia.`,
      })
      onCerrar()
      await cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'firmas'] })
    },
    onError: (error) => notify({
      type: 'error',
      message: error instanceof Error ? error.message : 'No fue posible registrar la firma física.',
    }),
  })

  function alternarFirma(firmaId: number, seleccionada: boolean) {
    setFirmaIds((actuales) => seleccionada
      ? [...actuales, firmaId]
      : actuales.filter((id) => id !== firmaId))
  }

  return (
    <ConfirmacionModal
      titulo="Registrar firma física"
      confirmar="Registrar firma física"
      procesando="Registrando…"
      pendiente={registrar.isPending}
      confirmarDeshabilitado={!archivo || !fechaFirma || firmaIds.length === 0}
      onConfirmar={() => registrar.mutate()}
      onCerrar={onCerrar}
    >
      <div className="firma-fisica-resumen">
        <p><strong>Firmante:</strong> {firmaInicial.nombre_firmante ?? '—'}</p>
        <p><strong>Cargo:</strong> {firmaInicial.cargo_firmante ?? '—'}</p>
        <p><strong>Rol:</strong> {etiqueta(firmaInicial.rol_firmante)}</p>
      </div>
      <label className="form-group" htmlFor="evidencia-firma-fisica">
        <span className="form-label">Documento firmado (PDF) *</span>
        <input
          id="evidencia-firma-fisica"
          className="form-control"
          type="file"
          accept="application/pdf,.pdf"
          required
          onChange={(event) => setArchivo(event.currentTarget.files?.[0] ?? null)}
        />
      </label>
      <label className="form-group" htmlFor="fecha-firma-fisica">
        <span className="form-label">Fecha de firma *</span>
        <input
          id="fecha-firma-fisica"
          className="form-control"
          type="date"
          value={fechaFirma}
          required
          onChange={(event) => setFechaFirma(event.target.value)}
        />
      </label>
      <fieldset className="firmas-fisicas-seleccion">
        <legend>Firmas físicas incluidas en el mismo documento</legend>
        {firmasDisponibles.map((firma) => (
          <label key={firma.id}>
            <input
              type="checkbox"
              checked={firmaIds.includes(firma.id)}
              onChange={(event) => alternarFirma(firma.id, event.target.checked)}
            />
            <span>
              <strong>{etiqueta(firma.rol_firmante)}</strong>
              <small>{firma.nombre_firmante} · {firma.cargo_firmante}</small>
            </span>
          </label>
        ))}
      </fieldset>
    </ConfirmacionModal>
  )
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
  const [firmaFisicaSeleccionada, setFirmaFisicaSeleccionada] = useState<number | null>(null)
  const [confirmarFormalizacion, setConfirmarFormalizacion] = useState(false)
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
  const formalizar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/firmas/formalizar`, { method: 'POST' }),
    onSuccess: async () => {
      setConfirmarFormalizacion(false)
      notify({ type: 'success', message: 'El convenio fue formalizado y pasó a estado Vigente.' })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['convenio', convenioId] }),
        cliente.invalidateQueries({ queryKey: ['convenios', convenioId, 'elaboracion'] }),
        cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'historial'] }),
        cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'firmas'] }),
      ])
    },
    onError: (error) => notify({
      type: 'error',
      message: error instanceof Error ? error.message : 'No fue posible formalizar el convenio.',
    }),
  })

  if (proceso.isPending) return <p className="estado-pagina">Cargando proceso de firmas…</p>
  if (proceso.isError || !proceso.data) return null
  const datos = proceso.data
  const completadas = datos.firmas.filter((firma) => firma.estado === 'FIRMADA').length
  const electronicas = datos.firmas.filter((firma) => firma.modalidad === 'ELECTRONICA')
  const fisicasPendientes = datos.firmas.filter(
    (firma) => firma.modalidad === 'FISICA' && firma.estado === 'PENDIENTE',
  )
  const algunaInvitacion = electronicas.some((firma) => firma.invitaciones.length > 0)
  const todasConfiguradas = datos.firmas.length === 7 && datos.firmas.every((firma) => firma.configurada)

  return (
    <section className="card seguimiento-firmas">
      <div className="revision-contraparte-cabecera">
        <div>
          <h2>Proceso de firmas</h2>
          <p className="section-help">
            {datos.estado === 'COMPLETADO' ? 'Versión contractual definitiva' : 'Versión congelada del proceso'}: {datos.version_numero}
          </p>
        </div>
        <span className={`badge ${completadas === 7 ? 'badge-success' : 'badge-warning'}`}>{completadas} de 7 firmas completadas</span>
      </div>
      <div className="firmas-lista">
        {datos.firmas.map((firma) => {
          const invitacion = invitacionReciente(firma)
          return (
            <article className="firma-seguimiento" key={firma.id}>
              <div className="firma-seguimiento-cabecera"><strong>{firma.orden}. {etiqueta(firma.rol_firmante)}</strong><span className={`badge ${claseEstadoFirma(firma.estado)}`}>{etiqueta(firma.estado)}</span></div>
              {datos.estado === 'CONFIGURACION' ? <ConfiguracionFirma convenioId={convenioId} firma={firma} /> : (
                <dl className="proyecto-datos">
                  <dt>Nombre</dt><dd>{firma.nombre_firmante ?? '—'}</dd><dt>Cargo</dt><dd>{firma.cargo_firmante ?? '—'}</dd>
                  <dt>Correo</dt><dd>{firma.correo_firmante ?? '—'}</dd><dt>Modalidad</dt><dd>{etiqueta(firma.modalidad)}</dd>
                  <dt>Fecha de firma</dt><dd>{firma.modalidad === 'FISICA' ? fechaFisica(firma.fecha_firma) : fecha(firma.fecha_firma)}</dd>
                  {firma.modalidad === 'FISICA' ? (
                    <><dt>Evidencia</dt><dd>{firma.documento ? <a href={`/api/convenios/${convenioId}/documentos/${firma.documento.id}/contenido`} target="_blank" rel="noreferrer">Ver/descargar {firma.documento.nombre_archivo}</a> : 'Pendiente de registro'}</dd></>
                  ) : (
                    <><dt>Invitación</dt><dd><span className={`badge ${claseEstadoInvitacion(invitacion?.estado ?? null)}`}>{invitacion ? etiqueta(invitacion.estado) : 'No disponible'}</span></dd></>
                  )}
                </dl>
              )}
              {datos.estado === 'EN_CURSO' && firma.modalidad === 'ELECTRONICA' && firma.estado === 'PENDIENTE' && invitacion && (
                <button className="btn btn-outline btn-small" type="button" disabled={reenviar.isPending} onClick={() => reenviar.mutate(firma.id)}>Reenviar enlace</button>
              )}
              {datos.estado === 'EN_CURSO' && firma.modalidad === 'FISICA' && firma.estado === 'PENDIENTE' && (
                <button className="btn btn-outline btn-small" type="button" onClick={() => setFirmaFisicaSeleccionada(firma.id)}>Registrar firma física</button>
              )}
            </article>
          )
        })}
      </div>
      <div className="page-toolbar">
        {datos.estado === 'CONFIGURACION' && <button className="btn btn-primary" type="button" disabled={!todasConfiguradas || iniciar.isPending} onClick={() => iniciar.mutate()}>{iniciar.isPending ? 'Iniciando…' : 'Iniciar proceso de firmas'}</button>}
        {datos.estado === 'EN_CURSO' && electronicas.length > 0 && !algunaInvitacion && <button className="btn btn-primary" type="button" disabled={enviar.isPending} onClick={() => enviar.mutate()}>{enviar.isPending ? 'Enviando…' : 'Enviar invitaciones electrónicas'}</button>}
      </div>
      {datos.estado === 'EN_CURSO' && completadas === 7 && (
        <section className="formalizacion-convenio">
          <div>
            <h3>Todas las firmas obligatorias han sido registradas.</h3>
            <p>Al formalizar, esta versión quedará como versión contractual definitiva y el convenio pasará a estado Vigente.</p>
          </div>
          <button className="btn btn-primary" type="button" onClick={() => setConfirmarFormalizacion(true)}>
            Formalizar convenio
          </button>
        </section>
      )}
      {firmaFisicaSeleccionada !== null && fisicasPendientes.some((firma) => firma.id === firmaFisicaSeleccionada) && (
        <RegistroFirmaFisicaModal
          convenioId={convenioId}
          firmaInicial={fisicasPendientes.find((firma) => firma.id === firmaFisicaSeleccionada)!}
          firmasDisponibles={fisicasPendientes}
          onCerrar={() => setFirmaFisicaSeleccionada(null)}
        />
      )}
      {confirmarFormalizacion && (
        <ConfirmacionModal
          titulo="Formalizar convenio"
          confirmar="Formalizar convenio"
          procesando="Formalizando…"
          pendiente={formalizar.isPending}
          onConfirmar={() => formalizar.mutate()}
          onCerrar={() => setConfirmarFormalizacion(false)}
        >
          <p>Se cerrará el proceso de firmas de la versión {datos.version_numero}.</p>
          <p>Esta versión quedará como versión contractual definitiva y el convenio pasará a estado Vigente.</p>
        </ConfirmacionModal>
      )}
    </section>
  )
}
