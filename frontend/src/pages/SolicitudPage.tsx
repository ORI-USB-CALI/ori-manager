import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { ETIQUETA_TIPO, TIPOS_IDENTIFICACION, type TipoAliado } from './epica02'
import { type DocumentoSolicitud, type Solicitud, type TipoDocumento, useCatalogosSolicitud, useSolicitud } from './solicitudes'

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

const PLACEHOLDERS_CAMPOS: Partial<Record<keyof Solicitud, string>> = {
  solicitante_nombre: 'Identifica a la persona responsable de presentar esta solicitud.',
  solicitante_correo: 'Correo registrado para identificar al solicitante en esta solicitud.',
  solicitante_unidad: 'Facultad o dependencia del solicitante dentro de la Universidad.',
  solicitante_programa: 'Programa académico o unidad a la que pertenece el solicitante.',
  solicitante_cargo: 'Cargo que desempeña el solicitante en su organización.',
  solicitante_documento: 'Documento de identidad asociado al solicitante externo.',
  solicitante_entidad: 'Organización a la que pertenece el solicitante externo.',
  nombre_aliado_propuesto: 'Registre el nombre oficial de la institución u organización contraparte.',
  identificacion_aliado_propuesto: 'Número de identificación jurídica de la entidad contraparte.',
  correo_aliado_propuesto: 'Correo institucional de la entidad, no de una persona de contacto.',
  sector_economico_aliado_propuesto: 'Indique el sector al que pertenece la empresa. Aplica cuando la contraparte es una empresa.',
  pais_aliado_propuesto: 'País donde se encuentra la entidad contraparte.',
  ciudad_aliado_propuesto: 'Ciudad donde se encuentra la entidad contraparte.',
  telefono_aliado_propuesto: 'Número telefónico institucional de la entidad contraparte.',
  direccion_aliado_propuesto: 'Dirección institucional de la entidad contraparte.',
  contacto_contraparte_nombre: 'Nombre de la persona designada como contacto por la contraparte.',
  contacto_contraparte_cargo: 'Cargo de la persona de contacto en la entidad contraparte.',
  contacto_contraparte_telefono: 'Teléfono de la persona de contacto designada por la contraparte.',
  contacto_contraparte_correo: 'Correo de la persona de contacto designada por la contraparte.',
  vigencia_estimada: 'Indique el tiempo estimado durante el cual se espera desarrollar el convenio.',
  justificacion: 'Explique la necesidad o razón que motiva la celebración del convenio.',
  objeto: 'Describa el propósito principal que se busca formalizar mediante el convenio.',
  actividades_por_parte: 'Describa las principales actividades o compromisos previstos para cada parte.',
  metas_esperadas: 'Indique los resultados que se espera alcanzar durante la ejecución del convenio.',
  implicacion_financiera: 'Indique si se contemplan compromisos o recursos financieros y descríbalos cuando corresponda.',
  requisitos_renovacion: 'Describa las condiciones previstas para considerar una futura renovación.',
  supervisor_usb_nombre: 'Nombre de la persona que acompañará la ejecución por parte de la USB.',
  supervisor_usb_cargo: 'Cargo de la persona encargada por parte de la USB.',
  supervisor_usb_telefono: 'Teléfono de contacto del encargado por parte de la USB.',
  supervisor_usb_correo: 'Correo de contacto del encargado por parte de la USB.',
  supervisor_contraparte_nombre: 'Nombre de la persona que acompañará la ejecución por la contraparte.',
  supervisor_contraparte_cargo: 'Cargo de la persona encargada por la contraparte.',
  supervisor_contraparte_telefono: 'Teléfono de contacto del encargado por la contraparte.',
  supervisor_contraparte_correo: 'Correo de contacto del encargado por la contraparte.',
}

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

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function SolicitudPage() {
  const params = useParams()
  const id = params.solicitudId ? Number(params.solicitudId) : null
  const navigate = useNavigate()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const formRef = useRef<HTMLFormElement>(null)
  const archivoRef = useRef<HTMLInputElement>(null)
  const solicitudIdRef = useRef<number | null>(id)
  const operacionEnCursoRef = useRef(false)
  const catalogos = useCatalogosSolicitud()
  const consulta = useSolicitud(id)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [tipoDocumento, setTipoDocumento] = useState<TipoDocumento>('CAMARA_COMERCIO')
  const solicitud = consulta.data
  const editable = !solicitud || solicitud.estado === 'BORRADOR'

  useEffect(() => {
    solicitudIdRef.current = id
  }, [id])

  async function ejecutarOperacion<T>(operacion: () => Promise<T>): Promise<T> {
    if (operacionEnCursoRef.current) throw new Error('Hay otra operación en curso.')
    operacionEnCursoRef.current = true
    try {
      return await operacion()
    } finally {
      operacionEnCursoRef.current = false
    }
  }

  function datosActuales(): Record<string, string | number | null> {
    if (!formRef.current) throw new Error('No fue posible leer el formulario.')
    return valoresFormulario(formRef.current)
  }

  async function asegurarBorradorActual(
    datos = datosActuales(),
  ): Promise<Solicitud> {
    const solicitudId = solicitudIdRef.current
    const resultado = solicitudId === null
      ? await apiFetch<Solicitud>('/solicitudes', { method: 'POST', body: JSON.stringify(datos) })
      : await apiFetch<Solicitud>(`/solicitudes/${solicitudId}`, { method: 'PATCH', body: JSON.stringify(datos) })

    solicitudIdRef.current = resultado.id
    queryClient.setQueryData(['solicitudes', resultado.id], resultado)
    if (solicitudId === null) {
      navigate(`/solicitudes/${resultado.id}`, { replace: true })
    }
    return resultado
  }

  const guardar = useMutation({
    mutationFn: () => ejecutarOperacion(() => asegurarBorradorActual()),
    onSuccess: async () => {
      setErrores({})
      notify({ type: 'success', message: 'Borrador guardado.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes'] })
    },
    onError: (error) => {
      setErrores(erroresServidor(error))
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible guardar.' })
    },
  })

  const radicar = useMutation({
    mutationFn: () => ejecutarOperacion(async () => {
      const datos = datosActuales()
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
      const borrador = await asegurarBorradorActual(datos)
      return apiFetch<Solicitud>(`/solicitudes/${borrador.id}/radicar`, { method: 'POST' })
    }),
    onSuccess: async (resultado) => {
      setErrores({})
      queryClient.setQueryData(['solicitudes', resultado.id], resultado)
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
    mutationFn: () => ejecutarOperacion(async () => {
      const archivo = archivoRef.current?.files?.[0]
      if (!archivo) throw new Error('Seleccione un archivo.')
      const borrador = await asegurarBorradorActual()
      const form = new FormData()
      form.set('tipo_documento', tipoDocumento)
      form.set('archivo', archivo)
      const documento = await apiFetch<DocumentoSolicitud>(`/solicitudes/${borrador.id}/documentos`, { method: 'POST', body: form })
      return { documento, solicitudId: borrador.id }
    }),
    onSuccess: async ({ solicitudId }) => {
      if (archivoRef.current) archivoRef.current.value = ''
      notify({ type: 'success', message: 'Documento adjuntado correctamente.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes', solicitudId] })
    },
    onError: (error) => {
      const servidor = erroresServidor(error)
      if (Object.keys(servidor).length) setErrores(servidor)
      notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible cargar el documento.' })
    },
  })

  const eliminar = useMutation({
    mutationFn: (documentoId: number) => ejecutarOperacion(async () => {
      const solicitudId = solicitudIdRef.current
      if (solicitudId === null) throw new Error('Solicitud no encontrada.')
      await apiFetch(`/solicitudes/${solicitudId}/documentos/${documentoId}`, { method: 'DELETE' })
      return solicitudId
    }),
    onSuccess: async (solicitudId) => {
      notify({ type: 'success', message: 'Documento eliminado.' })
      await queryClient.invalidateQueries({ queryKey: ['solicitudes', solicitudId] })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible eliminar.' }),
  })

  function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    guardar.mutate()
  }

  const operacionEnCurso = guardar.isPending || cargar.isPending || radicar.isPending || eliminar.isPending

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
  const erroresDocumentos = Object.entries(errores).filter(([key]) => key.startsWith('documentos.'))

  const campo = (nombre: keyof Solicitud, etiqueta: string, multilinea = false, precarga: string | null = null, requerido = true, placeholder = PLACEHOLDERS_CAMPOS[nombre]) => {
    const id = `solicitud-${String(nombre).replaceAll('_', '-')}`
    const errorId = `${id}-error`
    const propiedades = {
      id,
      className: `form-control ${errores[nombre] ? 'is-invalid' : ''}`,
      name: nombre,
      placeholder,
      defaultValue: String(solicitud?.[nombre] ?? precarga ?? ''),
      disabled: !editable,
      'aria-describedby': errores[nombre] ? errorId : undefined,
      'aria-invalid': Boolean(errores[nombre]),
    }
    return (
      <label className={`form-group ${multilinea ? 'form-span-2' : ''}`} htmlFor={id}><span className="form-label">{etiqueta}{requerido ? ' *' : ''}</span>
      {multilinea ? <textarea {...propiedades} /> : <input {...propiedades} />}
      {errores[nombre] && <span id={errorId} className="form-error">{errores[nombre]}</span>}
    </label>
    )
  }

  return (
    <>
      <section className="header-banner"><h1>{solicitud ? solicitud.consecutivo : 'Nueva solicitud'}</h1><p>{solicitud ? `Estado: ${solicitud.estado}` : 'Registre la información inicial. Puede guardar su avance en cualquier momento.'}</p></section>
      <form ref={formRef} className="solicitud-form" onSubmit={enviar}>
        <section className="card"><h2>1. Información del solicitante {perfilVisible?.tipo_usuario === 'INTERNO' ? 'interno' : 'externo'}</h2><p className="section-help">Los datos se precargan desde su perfil y se conservarán como snapshot de esta solicitud.</p><div className="form-grid">
          {campo('solicitante_nombre', 'Responsable y/o solicitante', false, perfilVisible?.nombre ?? null)}
          {campo('solicitante_correo', 'Correo del solicitante', false, perfilVisible?.correo ?? null, false)}
          {perfilVisible?.tipo_usuario === 'INTERNO' ? <>{campo('solicitante_unidad', 'Facultad / Dependencia', false, perfilVisible.unidad, tipoUnidad !== null && (tipoUnidad !== 'PROGRAMA' || Boolean(perfilVisible.unidad)))}{campo('solicitante_programa', 'Programa Académico / Unidad', false, perfilVisible.programa, tipoUnidad === 'PROGRAMA')}{campo('solicitante_cargo', 'Cargo', false, perfilVisible.cargo)}</> : <>{campo('solicitante_documento', 'Identificación', false, perfilVisible?.identificacion ?? null)}{campo('solicitante_entidad', 'Empresa / Entidad', false, perfilVisible?.entidad ?? null)}</>}
        </div></section>

        <section className="card"><h2>2. Información de la contraparte</h2><div className="form-grid">
          {campo('nombre_aliado_propuesto', 'Nombre de la entidad')}
          <label className="form-group" htmlFor="solicitud-tipo-entidad"><span className="form-label">Tipo de entidad *</span><select id="solicitud-tipo-entidad" aria-describedby={errores.tipo_aliado_propuesto ? 'solicitud-tipo-entidad-error' : undefined} aria-invalid={Boolean(errores.tipo_aliado_propuesto)} className={`form-control select ${errores.tipo_aliado_propuesto ? 'is-invalid' : ''}`} name="tipo_aliado_propuesto" defaultValue={solicitud?.tipo_aliado_propuesto ?? ''} disabled={!editable}><option value="">Seleccione el tipo de entidad</option>{TIPOS_ALIADO.map((tipo) => <option key={tipo} value={tipo}>{ETIQUETA_TIPO[tipo]}</option>)}</select>{errores.tipo_aliado_propuesto && <span id="solicitud-tipo-entidad-error" className="form-error">{errores.tipo_aliado_propuesto}</span>}</label>
          <label className="form-group" htmlFor="solicitud-tipo-identificacion"><span className="form-label">Tipo de identificación *</span><select id="solicitud-tipo-identificacion" aria-describedby={errores.tipo_identificacion_aliado_propuesto ? 'solicitud-tipo-identificacion-error' : undefined} aria-invalid={Boolean(errores.tipo_identificacion_aliado_propuesto)} className={`form-control select ${errores.tipo_identificacion_aliado_propuesto ? 'is-invalid' : ''}`} name="tipo_identificacion_aliado_propuesto" defaultValue={solicitud?.tipo_identificacion_aliado_propuesto ?? ''} disabled={!editable}><option value="">Seleccione el tipo de identificación</option>{TIPOS_IDENTIFICACION.map((tipo) => <option key={tipo}>{tipo}</option>)}</select>{errores.tipo_identificacion_aliado_propuesto && <span id="solicitud-tipo-identificacion-error" className="form-error">{errores.tipo_identificacion_aliado_propuesto}</span>}</label>
          {campo('identificacion_aliado_propuesto', 'Identificación')}{campo('correo_aliado_propuesto', 'Correo institucional de la entidad')}{campo('sector_economico_aliado_propuesto', 'Sector económico (obligatorio para empresa)', false, null, false)}
          {campo('pais_aliado_propuesto', 'País')}{campo('ciudad_aliado_propuesto', 'Ciudad')}{campo('telefono_aliado_propuesto', 'Teléfono institucional')}{campo('direccion_aliado_propuesto', 'Dirección')}
        </div></section>

        <section className="card"><h2>3. Contacto de contraparte</h2><div className="form-grid">{campo('contacto_contraparte_nombre', 'Nombre')}{campo('contacto_contraparte_cargo', 'Cargo')}{campo('contacto_contraparte_telefono', 'Teléfono')}{campo('contacto_contraparte_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>4. Información del convenio</h2><div className="form-grid">
          <label className="form-group" htmlFor="solicitud-tipo-convenio"><span className="form-label">Tipo de convenio *</span><select id="solicitud-tipo-convenio" aria-describedby={errores.tipo_convenio_id ? 'solicitud-tipo-convenio-error' : undefined} aria-invalid={Boolean(errores.tipo_convenio_id)} className={`form-control select ${errores.tipo_convenio_id ? 'is-invalid' : ''}`} name="tipo_convenio_id" defaultValue={solicitud?.tipo_convenio_id ?? ''} disabled={!editable}><option value="">Seleccione el tipo de convenio</option>{catalogos.data?.tipos_convenio.map((tipo) => <option key={tipo.id} value={tipo.id}>{tipo.nombre}</option>)}</select>{errores.tipo_convenio_id && <span id="solicitud-tipo-convenio-error" className="form-error">{errores.tipo_convenio_id}</span>}</label>
          {campo('vigencia_estimada', 'Tiempo estimado de vigencia')}{campo('justificacion', 'Justificación', true)}{campo('objeto', 'Objeto', true)}{campo('actividades_por_parte', 'Actividades por cada una de las partes', true)}{campo('metas_esperadas', 'Metas esperadas', true)}{campo('implicacion_financiera', 'Implicación financiera', true)}{campo('requisitos_renovacion', 'Requisitos para renovación', true)}
        </div></section>

        <section className="card"><h2>5. Supervisor o encargado de ejecución USB</h2><div className="form-grid">{campo('supervisor_usb_nombre', 'Nombre')}{campo('supervisor_usb_cargo', 'Cargo')}{campo('supervisor_usb_telefono', 'Teléfono')}{campo('supervisor_usb_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>6. Supervisor o encargado de ejecución de la contraparte</h2><div className="form-grid">{campo('supervisor_contraparte_nombre', 'Nombre')}{campo('supervisor_contraparte_cargo', 'Cargo')}{campo('supervisor_contraparte_telefono', 'Teléfono')}{campo('supervisor_contraparte_correo', 'Correo electrónico')}</div></section>

        <section className="card"><h2>7. Documentación</h2><p className="section-help">Adjunte los documentos de representación legal aplicables a la institución o entidad contraparte. Formatos permitidos: PDF, JPG y PNG. Tamaño máximo: 10 MB.</p>
          {(!solicitud || solicitud.documentos.length === 0) && <p className="section-help">Aún no hay documentos adjuntos.</p>}
          {solicitud?.documentos.map((doc) => <div className="document-row" key={doc.id}><span>{catalogos.data?.tipos_documento.find((tipo) => tipo.codigo === doc.tipo_documento)?.nombre}: {doc.nombre_original} · {tamanoLegible(doc.tamano_bytes)}</span>{editable && <button className="btn btn-outline btn-small" type="button" disabled={operacionEnCurso} onClick={() => eliminar.mutate(doc.id)}>Eliminar</button>}</div>)}
          {erroresDocumentos.length > 0 && <div id="solicitud-documentos-error">{erroresDocumentos.map(([key, value]) => <p className="form-error" key={key}>{value}</p>)}</div>}
          {editable && <div className="document-upload"><label className="form-group" htmlFor="solicitud-tipo-documento"><span className="form-label">Tipo de documento</span><select id="solicitud-tipo-documento" className="form-control select" value={tipoDocumento} disabled={operacionEnCurso} onChange={(event) => setTipoDocumento(event.target.value as TipoDocumento)}>{catalogos.data?.tipos_documento.map((tipo) => <option key={tipo.codigo} value={tipo.codigo}>{tipo.nombre}{tipo.es_representacion_legal ? ' · representación legal' : ''}</option>)}</select></label><label className="form-group" htmlFor="solicitud-archivo"><span className="form-label">Archivo</span><input id="solicitud-archivo" ref={archivoRef} className="form-control" type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={operacionEnCurso} aria-describedby={`solicitud-archivo-ayuda${erroresDocumentos.length ? ' solicitud-documentos-error' : ''}`} /><small id="solicitud-archivo-ayuda" className="form-help">Formatos permitidos: PDF, JPG y PNG. Máximo 10 MB.</small></label><button className="btn btn-outline" type="button" disabled={operacionEnCurso} onClick={() => cargar.mutate()}>{cargar.isPending ? 'Adjuntando…' : 'Adjuntar'}</button></div>}
        </section>

        <section className="card"><h2>8. Observaciones adicionales</h2><label className="form-group" htmlFor="solicitud-observaciones"><span className="form-label">Observaciones</span><textarea id="solicitud-observaciones" className="form-control" name="observaciones" defaultValue={solicitud?.observaciones ?? ''} disabled={!editable} placeholder="Agregue información complementaria que no haya sido incluida anteriormente." /></label></section>

        <div className="page-toolbar"><Link className="btn btn-outline" to="/solicitudes">Volver</Link>{editable && <><button className="btn btn-outline" type="submit" disabled={operacionEnCurso}>{guardar.isPending ? 'Guardando…' : 'Guardar borrador'}</button><button className="btn btn-primary" type="button" disabled={operacionEnCurso} onClick={() => radicar.mutate()}>{radicar.isPending ? 'Radicando…' : 'Radicar solicitud'}</button></>}</div>
      </form>
    </>
  )
}
