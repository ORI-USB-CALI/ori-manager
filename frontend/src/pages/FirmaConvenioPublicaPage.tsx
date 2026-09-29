import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'
import { FirmaCanvas } from '../components/FirmaCanvas'

interface AccesoFirmaConvenio {
  identificador: string
  rol: string
  nombre_firmante: string
  cargo_firmante: string
  correo_firmante: string
  version_numero: number
  contenido: DocumentoConvenio
  expira_en: string
  estado: string
}

interface FirmaRegistrada {
  estado: string
  fecha_firma: string
}

type CodigoEnlace =
  | 'ENLACE_INVALIDO'
  | 'ENLACE_EXPIRADO'
  | 'ENLACE_NO_DISPONIBLE'
  | 'FIRMA_YA_REGISTRADA'

function tokenDesdeFragmento(): string | null {
  const parametros = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  return parametros.get('token')?.trim() || null
}

function codigoEnlace(error: unknown): CodigoEnlace | null {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object' || Array.isArray(error.detail)) return null
  if (!('codigo' in error.detail) || typeof error.detail.codigo !== 'string') return null
  const codigos: CodigoEnlace[] = ['ENLACE_INVALIDO', 'ENLACE_EXPIRADO', 'ENLACE_NO_DISPONIBLE', 'FIRMA_YA_REGISTRADA']
  return codigos.includes(error.detail.codigo as CodigoEnlace) ? error.detail.codigo as CodigoEnlace : null
}

function etiquetaRol(rol: string): string {
  return rol.toLowerCase().replaceAll('_', ' ').replace(/^./, (letra) => letra.toUpperCase())
}

function EstadoEnlace({ codigo }: { codigo: CodigoEnlace | 'ERROR' }) {
  const contenido = codigo === 'ENLACE_EXPIRADO'
    ? { titulo: 'Este enlace de firma ha expirado.', texto: 'Solicita a la Oficina de Relaciones Interinstitucionales un nuevo enlace para continuar.' }
    : codigo === 'FIRMA_YA_REGISTRADA'
      ? { titulo: 'La firma ya fue registrada.', texto: 'Esta invitación ya fue utilizada y no permite registrar una segunda firma.' }
      : codigo === 'ENLACE_NO_DISPONIBLE'
        ? { titulo: 'Este enlace ya no está disponible.', texto: 'El enlace fue reemplazado o el proceso ya no admite esta firma. Comunícate con la ORI si necesitas asistencia.' }
        : codigo === 'ENLACE_INVALIDO'
          ? { titulo: 'El enlace de firma no es válido.', texto: 'Verifica que abriste el enlace completo recibido por correo o solicita asistencia a la ORI.' }
          : { titulo: 'No se pudo cargar la elaboración de convenio.', texto: 'Intenta nuevamente. Si el problema continúa, comunícate con la ORI.' }
  return (
    <main className="revision-publica-main">
      <section className="card estado-vacio revision-publica-estado" role="alert">
        <span className="revision-publica-marca" aria-hidden="true">ORI</span>
        <h1>{contenido.titulo}</h1>
        <p>{contenido.texto}</p>
      </section>
    </main>
  )
}

export function FirmaConvenioPublicaPage() {
  const [token, setToken] = useState<string | null>(() => tokenDesdeFragmento())
  const [firma, setFirma] = useState<string | null>(null)
  const [confirmacion, setConfirmacion] = useState(false)
  const [finalizado, setFinalizado] = useState(false)
  const [codigoFinal, setCodigoFinal] = useState<CodigoEnlace | null>(null)

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`)
    }
  }, [])

  const acceso = useQuery({
    queryKey: ['firma-convenio-publica', 'acceso'],
    queryFn: () => apiFetch<AccesoFirmaConvenio>('/public/firma-convenio/acceso', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
    enabled: Boolean(token),
    retry: false,
    gcTime: 0,
  })

  const firmar = useMutation({
    mutationFn: () => apiFetch<FirmaRegistrada>('/public/firma-convenio/firmar', {
      method: 'POST',
      body: JSON.stringify({ token, firma, confirmacion }),
    }),
    onSuccess: () => {
      setFinalizado(true)
      setToken(null)
      setFirma(null)
    },
    onError: (error) => {
      const codigo = codigoEnlace(error)
      if (codigo) setCodigoFinal(codigo)
    },
  })

  let contenido: ReactNode
  if (finalizado) {
    contenido = (
      <main className="revision-publica-main">
        <section className="card estado-vacio revision-publica-estado" role="status">
          <span className="revision-publica-exito" aria-hidden="true">✓</span>
          <h1>Firma registrada correctamente.</h1>
          <p>La ORI continuará el proceso de firmas de la elaboración de convenio.</p>
        </section>
      </main>
    )
  } else if (codigoFinal) {
    contenido = <EstadoEnlace codigo={codigoFinal} />
  } else if (!token) {
    contenido = <EstadoEnlace codigo="ENLACE_INVALIDO" />
  } else if (acceso.isPending) {
    contenido = <main className="revision-publica-main"><p className="estado-pagina">Cargando elaboración de convenio…</p></main>
  } else if (acceso.isError) {
    contenido = <EstadoEnlace codigo={codigoEnlace(acceso.error) ?? 'ERROR'} />
  } else if (!acceso.data) {
    contenido = <EstadoEnlace codigo="ERROR" />
  } else {
    const datos = acceso.data
    contenido = (
      <main className="revision-publica-main">
        <section className="revision-publica-presentacion">
          <span className="badge badge-pendiente">Firma pendiente</span>
          <h1>Firma electrónica de elaboración de convenio</h1>
          <p>Revisa la versión presentada y registra personalmente tu firma.</p>
        </section>

        <section className="card revision-publica-resumen">
          <h2>Datos de la firma</h2>
          <dl className="proyecto-datos">
            <dt>Elaboración</dt><dd>{datos.identificador}</dd>
            <dt>Firmante</dt><dd>{datos.nombre_firmante}</dd>
            <dt>Cargo</dt><dd>{datos.cargo_firmante}</dd>
            <dt>Rol</dt><dd>{etiquetaRol(datos.rol)}</dd>
            <dt>Correo</dt><dd>{datos.correo_firmante}</dd>
            <dt>Versión</dt><dd>{datos.version_numero}</dd>
            <dt>Enlace válido hasta</dt><dd>{new Date(datos.expira_en).toLocaleString()}</dd>
          </dl>
        </section>

        <section className="card revision-publica-documento">
          <div className="editor-cabecera">
            <div>
              <h2>Versión {datos.version_numero} de la elaboración de convenio</h2>
              <p className="section-help">Documento recibido para consulta. Su contenido es de solo lectura.</p>
            </div>
            <span className="badge badge-neutral">Solo lectura</span>
          </div>
          <ConvenioEditor contenido={datos.contenido} editable={false} onChange={() => undefined} />
        </section>

        <section className="card revision-publica-acciones">
          <h2>Registrar firma electrónica</h2>
          <FirmaCanvas disabled={firmar.isPending} onFirma={setFirma} />
          <label className="conformidad-check">
            <input type="checkbox" checked={confirmacion} disabled={firmar.isPending} onChange={(event) => setConfirmacion(event.target.checked)} />
            <span>Confirmo que he revisado la versión presentada y manifiesto mi conformidad mediante esta firma electrónica.</span>
          </label>
          {firmar.isError && !codigoEnlace(firmar.error) && (
            <p className="alert-error" role="alert">{firmar.error instanceof Error ? firmar.error.message : 'No fue posible registrar la firma.'}</p>
          )}
          <div className="page-toolbar">
            <button className="btn btn-primary" type="button" disabled={!firma || !confirmacion || firmar.isPending} onClick={() => firmar.mutate()}>
              {firmar.isPending ? 'Registrando firma…' : 'Firmar elaboración de convenio'}
            </button>
          </div>
        </section>
      </main>
    )
  }

  return (
    <div className="revision-publica-shell">
      <header className="revision-publica-header"><div><strong>USB</strong><span>Oficina de Relaciones Interinstitucionales</span></div></header>
      {contenido}
      <footer className="revision-publica-footer">Universidad de San Buenaventura Cali · Firma electrónica de elaboración de convenio</footer>
    </div>
  )
}
