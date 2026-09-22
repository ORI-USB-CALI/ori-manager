import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { ETIQUETA_TIPO, TIPOS_IDENTIFICACION, type TipoAliado } from './epica02'
import { type Solicitud, type TipoDocumento, useCatalogosSolicitud, useSolicitud } from './solicitudes'

const TIPOS_ALIADO: TipoAliado[] = ['UNIVERSIDAD', 'COLEGIO', 'EMPRESA', 'ENTIDAD_GUBERNAMENTAL']
const CAMPOS_REQUERIDOS = [
  'nombre_aliado_propuesto', 'tipo_identificacion_aliado_propuesto', 'identificacion_aliado_propuesto',
  'tipo_aliado_propuesto', 'correo_aliado_propuesto', 'contacto_contraparte_nombre',
  'pais_aliado_propuesto', 'ciudad_aliado_propuesto', 'telefono_aliado_propuesto',
  'direccion_aliado_propuesto', 'contacto_contraparte_cargo',
  'contacto_contraparte_telefono', 'contacto_contraparte_correo', 'tipo_convenio_id', 'justificacion', 'objeto',
  'actividades_por_parte', 'metas_esperadas', 'implicacion_financiera', 'vigencia_estimada',
  'requisitos_renovacion', 'supervisor_usb_nombre', 'supervisor_usb_cargo',
  'supervisor_usb_telefono', 'supervisor_usb_correo', 'supervisor_contraparte_nombre',
  'supervisor_contraparte_cargo', 'supervisor_contraparte_telefono', 'supervisor_contraparte_correo',
] as const

function erroresServidor(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object') return {}
  if (Array.isArray(error.detail)) {
    return Object.fromEntries(error.detail.flatMap((item: unknown) => {
      if (!item || typeof item !== 'object' || !('loc' in item) || !('msg' in item)) return []
      const loc = Array.isArray(item.loc) ? item.loc : []
      const field = loc.at(-1)
      return typeof field === 'string' && typeof item.msg === 'string' ? [[field, item.msg]] : []
    }))
  }
  if (!('errors' in error.detail)) return {}
  const errors = error.detail.errors
  return errors && typeof errors === 'object' ? errors as Record<string, string> : {}
}

function valoresFormulario(formulario: HTMLFormElement): Record<string, string | number | null> {
  const form = new FormData(formulario)
  const datos: Record<string, string | number | null> = {}
  for (const [clave, valor] of form.entries()) {
    if (typeof valor !== 'string') continue
    const limpio = valor.trim()
    datos[clave] = clave === 'tipo_convenio_id' ? (limpio ? Number(limpio) : null) : (limpio || null)
  }
  return datos
}

export function SolicitudPage() {
  const params = useParams()
  const id = params.solicitudId ? Number(params.solicitudId) : null
  const navigate = useNavigate()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const formRef = useRef<HTMLFormElement>(null)
  const archivoRef = useRef<HTMLInputElement>(null)
  const catalogos = useCatalogosSolicitud()
  const consulta = useSolicitud(id)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [tipoDocumento, setTipoDocumento] = useState<TipoDocumento>('CAMARA_COMERCIO')
  const solicitud = consulta.data
  const editable = !solicitud || solicitud.estado === 'BORRADOR'

  const guardar = useMutation({
    mutationFn: async (datos: Record<string, unknown>) => id === null
      ? apiFetch<Solicitud>('/solicitudes', { method: 'POST', body: JSON.stringify(datos) })
      : apiFetch<Solicitud>(`/solicitudes/${id}`, { method: 'PATCH', body: JSON.stringify(datos) }),
    onSuccess: async (resultado) => {
      setErrores({})
      notify({ type: 'success', message: 'Borrador guardado.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes'] })
      if (id === null) navigate(`/solicitudes/${resultado.id}`, { replace: true })
    },
    onError: (error) => {
      setErrores(erroresServidor(error))
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible guardar.' })
    },
  })

  const radicar = useMutation({
    mutationFn: async () => {
      if (id === null || !formRef.current) throw new Error('Guarde el borrador antes de radicar.')
      const datos = valoresFormulario(formRef.current)
      const locales: Record<string, string> = {}
      for (const campo of CAMPOS_REQUERIDOS) if (!datos[campo]) locales[campo] = 'Este campo es obligatorio'
      if (!datos.solicitante_nombre) locales.solicitante_nombre = 'Este campo es obligatorio'
      if (catalogos.data?.solicitante.tipo_usuario === 'INTERNO') {
        const tipoUnidad = catalogos.data.solicitante.tipo_unidad
        if (tipoUnidad === 'PROGRAMA') {
          if (!datos.solicitante_programa) locales.solicitante_programa = 'Este campo es obligatorio'
          if (catalogos.data.solicitante.unidad && !datos.solicitante_unidad) locales.solicitante_unidad = 'Este campo es obligatorio'
        } else if (tipoUnidad) {
          if (!datos.solicitante_unidad) locales.solicitante_unidad = 'Este campo es obligatorio'
        } else if (!datos.solicitante_unidad && !datos.solicitante_programa) {
          locales.solicitante_unidad = 'Ingrese la información organizacional aplicable'
        }
        if (!datos.solicitante_cargo) locales.solicitante_cargo = 'Este campo es obligatorio'
      } else {
        for (const campo of ['solicitante_documento', 'solicitante_entidad']) {
          if (!datos[campo]) locales[campo] = 'Este campo es obligatorio'
        }
      }
      if (datos.tipo_aliado_propuesto === 'EMPRESA' && !datos.sector_economico_aliado_propuesto) locales.sector_economico_aliado_propuesto = 'Es obligatorio para una empresa'
      if (Object.keys(locales).length) {
        setErrores(locales)
        throw new Error('Revise los campos obligatorios antes de radicar.')
      }
      await apiFetch<Solicitud>(`/solicitudes/${id}`, { method: 'PATCH', body: JSON.stringify(datos) })
      return apiFetch<Solicitud>(`/solicitudes/${id}/radicar`, { method: 'POST' })
    },
    onSuccess: async () => {
      setErrores({})
      notify({ type: 'success', message: 'Solicitud radicada correctamente.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes'] })
    },
    onError: (error) => {
      const servidor = erroresServidor(error)
      if (Object.keys(servidor).length) setErrores(servidor)
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible radicar.' })
    },
  })

  const cargar = useMutation({
    mutationFn: async () => {
      if (id === null) throw new Error('Guarde el borrador antes de adjuntar documentos.')
      const archivo = archivoRef.current?.files?.[0]
      if (!archivo) throw new Error('Seleccione un archivo.')
      const form = new FormData()
      form.set('tipo_documento', tipoDocumento)
      form.set('archivo', archivo)
      return apiFetch(`/solicitudes/${id}/documentos`, { method: 'POST', body: form })
    },
    onSuccess: async () => {
      if (archivoRef.current) archivoRef.current.value = ''
      notify({ type: 'success', message: 'Documento cargado.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes', id] })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible cargar el documento.' }),
  })

  const eliminar = useMutation({
    mutationFn: (documentoId: number) => apiFetch(`/solicitudes/${id}/documentos/${documentoId}`, { method: 'DELETE' }),
    onSuccess: async () => {
      notify({ type: 'success', message: 'Documento eliminado.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes', id] })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible eliminar.' }),
  })

  function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    guardar.mutate(valoresFormulario(event.currentTarget))
  }

  if (catalogos.isPending || (id !== null && consulta.isPending)) return <p className="estado-pagina">Cargando formulario…</p>
  if (catalogos.isError || consulta.isError) return <p className="alert-error">{catalogos.error?.message ?? consulta.error?.message}</p>
  const perfil = catalogos.data?.solicitante
  const tipoUnidad = perfil?.tipo_unidad ?? null
  const perfilVisible = solicitud ? {
    tipo_usuario: solicitud.tipo_solicitante,
    nombre: solicitud.solicitante_nombre,
    correo: solicitud.solicitante_correo,
    identificacion: solicitud.solicitante_documento,
    entidad: solicitud.solicitante_entidad,
    cargo: solicitud.solicitante_cargo,
    unidad: solicitud.solicitante_unidad,
    programa: solicitud.solicitante_programa,
  } : perfil

  const campo = (nombre: keyof Solicitud, etiqueta: string, multilinea = false, precarga: string | null = null, requerido = true) => (
    <label className={`form-group ${multilinea ? 'form-span-2' : ''}`}><span className="form-label">{etiqueta}{requerido ? ' *' : ''}</span>
      {multilinea ? <textarea className={`form-control ${errores[nombre] ? 'is-invalid' : ''}`} name={nombre} defaultValue={String(solicitud?.[nombre] ?? precarga ?? '')} disabled={!editable} /> : <input className={`form-control ${errores[nombre] ? 'is-invalid' : ''}`} name={nombre} defaultValue={String(solicitud?.[nombre] ?? precarga ?? '')} disabled={!editable} />}
      {errores[nombre] && <span className="form-error">{errores[nombre]}</span>}
    </label>
  )

  return (
    <>
      <section className="header-banner"><h1>{solicitud ? solicitud.consecutivo : 'Nueva solicitud'}</h1><p>{solicitud ? `Estado: ${solicitud.estado}` : 'Registre la información inicial y guárdela como borrador.'}</p></section>
      <form ref={formRef} className="solicitud-form" onSubmit={enviar}>
        <section className="card"><h2>1. Información del solicitante {perfilVisible?.tipo_usuario === 'INTERNO' ? 'interno' : 'externo'}</h2><p className="section-help">Los datos se precargan desde su perfil y se conservarán como snapshot de esta solicitud.</p><div className="form-grid">
          {campo('solicitante_nombre', 'Responsable y/o solicitante', false, perfilVisible?.nombre ?? null)}
          {campo('solicitante_correo', 'Correo del solicitante', false, perfilVisible?.correo ?? null, false)}
          {perfilVisible?.tipo_usuario === 'INTERNO' ? <>{campo('solicitante_unidad', 'Facultad / Dependencia', false, perfilVisible.unidad, tipoUnidad !== null && (tipoUnidad !== 'PROGRAMA' || Boolean(perfilVisible.unidad)))}{campo('solicitante_programa', 'Programa Académico / Unidad', false, perfilVisible.programa, tipoUnidad === 'PROGRAMA')}{campo('solicitante_cargo', 'Cargo', false, perfilVisible.cargo)}</> : <>{campo('solicitante_documento', 'Identificación', false, perfilVisible?.identificacion ?? null)}{campo('solicitante_entidad', 'Empresa / Entidad', false, perfilVisible?.entidad ?? null)}</>}
        </div></section>

        <section className="card"><h2>2. Información de la contraparte</h2><div className="form-grid">
          {campo('nombre_aliado_propuesto', 'Nombre de la entidad')}
          <label className="form-group"><span className="form-label">Tipo de entidad *</span><select className={`form-control select ${errores.tipo_aliado_propuesto ? 'is-invalid' : ''}`} name="tipo_aliado_propuesto" defaultValue={solicitud?.tipo_aliado_propuesto ?? ''} disabled={!editable}><option value="">Seleccione</option>{TIPOS_ALIADO.map((tipo) => <option key={tipo} value={tipo}>{ETIQUETA_TIPO[tipo]}</option>)}</select>{errores.tipo_aliado_propuesto && <span className="form-error">{errores.tipo_aliado_propuesto}</span>}</label>
          <label className="form-group"><span className="form-label">Tipo de identificación *</span><select className={`form-control select ${errores.tipo_identificacion_aliado_propuesto ? 'is-invalid' : ''}`} name="tipo_identificacion_aliado_propuesto" defaultValue={solicitud?.tipo_identificacion_aliado_propuesto ?? ''} disabled={!editable}><option value="">Seleccione</option>{TIPOS_IDENTIFICACION.map((tipo) => <option key={tipo}>{tipo}</option>)}</select>{errores.tipo_identificacion_aliado_propuesto && <span className="form-error">{errores.tipo_identificacion_aliado_propuesto}</span>}</label>
          {campo('identificacion_aliado_propuesto', 'Identificación')}{campo('correo_aliado_propuesto', 'Correo institucional de la entidad')}{campo('sector_economico_aliado_propuesto', 'Sector económico (obligatorio para empresa)', false, null, false)}
          {campo('pais_aliado_propuesto', 'País')}{campo('ciudad_aliado_propuesto', 'Ciudad')}{campo('telefono_aliado_propuesto', 'Teléfono institucional')}{campo('direccion_aliado_propuesto', 'Dirección')}
        </div></section>

        <section className="card"><h2>3. Contacto de contraparte</h2><div className="form-grid">{campo('contacto_contraparte_nombre', 'Nombre')}{campo('contacto_contraparte_cargo', 'Cargo')}{campo('contacto_contraparte_telefono', 'Teléfono')}{campo('contacto_contraparte_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>4. Información del convenio</h2><div className="form-grid">
          <label className="form-group"><span className="form-label">Tipo de convenio *</span><select className={`form-control select ${errores.tipo_convenio_id ? 'is-invalid' : ''}`} name="tipo_convenio_id" defaultValue={solicitud?.tipo_convenio_id ?? ''} disabled={!editable}><option value="">Seleccione</option>{catalogos.data?.tipos_convenio.map((tipo) => <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>)}</select>{errores.tipo_convenio_id && <span className="form-error">{errores.tipo_convenio_id}</span>}</label>
          {campo('vigencia_estimada', 'Tiempo estimado de vigencia')}{campo('justificacion', 'Justificación', true)}{campo('objeto', 'Objeto', true)}{campo('actividades_por_parte', 'Actividades por cada una de las partes', true)}{campo('metas_esperadas', 'Metas esperadas', true)}{campo('implicacion_financiera', 'Implicación financiera', true)}{campo('requisitos_renovacion', 'Requisitos para renovación', true)}
        </div></section>

        <section className="card"><h2>5. Supervisor o encargado de ejecución USB</h2><div className="form-grid">{campo('supervisor_usb_nombre', 'Nombre')}{campo('supervisor_usb_cargo', 'Cargo')}{campo('supervisor_usb_telefono', 'Teléfono')}{campo('supervisor_usb_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>6. Supervisor o encargado de ejecución de la contraparte</h2><div className="form-grid">{campo('supervisor_contraparte_nombre', 'Nombre')}{campo('supervisor_contraparte_cargo', 'Cargo')}{campo('supervisor_contraparte_telefono', 'Teléfono')}{campo('supervisor_contraparte_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>7. Documentación</h2><p className="section-help">Adjunte los documentos de representación legal aplicables a la institución o entidad contraparte. Formatos permitidos: PDF, JPG y PNG. Tamaño máximo: 10 MB.</p>
          {solicitud?.documentos.map((doc) => <div className="document-row" key={doc.id}><span>{catalogos.data?.tipos_documento.find((tipo) => tipo.codigo === doc.tipo_documento)?.nombre}: {doc.nombre_original}</span>{editable && <button className="btn btn-outline btn-small" type="button" onClick={() => eliminar.mutate(doc.id)}>Eliminar</button>}</div>)}
          {Object.entries(errores).filter(([key]) => key.startsWith('documentos.')).map(([key, value]) => <p className="form-error" key={key}>{value}</p>)}
          {editable && <div className="document-upload"><select className="form-control select" value={tipoDocumento} onChange={(event) => setTipoDocumento(event.target.value as TipoDocumento)}>{catalogos.data?.tipos_documento.map((tipo) => <option key={tipo.codigo} value={tipo.codigo}>{tipo.nombre}{tipo.es_representacion_legal ? ' · representación legal' : ''}</option>)}</select><input ref={archivoRef} className="form-control" type="file" accept=".pdf,.jpg,.jpeg,.png" /><button className="btn btn-outline" type="button" disabled={id === null || cargar.isPending} onClick={() => cargar.mutate()}>Adjuntar</button></div>}
        </section>

        <section className="card"><h2>8. Observaciones adicionales</h2><textarea className="form-control" name="observaciones" defaultValue={solicitud?.observaciones ?? ''} disabled={!editable} /></section>

        <div className="page-toolbar"><Link className="btn btn-outline" to="/solicitudes">Volver</Link>{editable && <><button className="btn btn-outline" type="submit" disabled={guardar.isPending}>{guardar.isPending ? 'Guardando…' : 'Guardar borrador'}</button><button className="btn btn-primary" type="button" disabled={id === null || radicar.isPending} onClick={() => radicar.mutate()}>{radicar.isPending ? 'Radicando…' : 'Radicar solicitud'}</button></>}</div>
      </form>
    </>
  )
}
