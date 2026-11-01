import { useEffect, useRef, useState } from 'react'

import { ApiError, apiFetchArchivo } from '../app/api'

export interface DocumentoPreviewModalProps {
  nombreArchivo: string
  urlContenido: string
  urlDescarga?: string
  tipoMime?: string
  puedeDescargar?: boolean
  onCerrar: () => void
}

export function DocumentoPreviewModal({
  nombreArchivo,
  urlContenido,
  urlDescarga,
  tipoMime,
  puedeDescargar = true,
  onCerrar,
}: DocumentoPreviewModalProps) {
  const dialogo = useRef<HTMLDialogElement>(null)
  const focoPrevioRef = useRef<HTMLElement | null>(null)

  // Criterio principal: tipoMime registrado si existe; de lo contrario, extensión del nombre como indicio inicial
  const tipoMimeNormalizado = tipoMime?.trim().toLowerCase()
  const esPdfInicial = tipoMimeNormalizado
    ? (tipoMimeNormalizado === 'application/pdf' || tipoMimeNormalizado === 'application/x-pdf')
    : nombreArchivo.toLowerCase().endsWith('.pdf')

  const [incompatible, setIncompatible] = useState(!esPdfInicial)
  const [cargando, setCargando] = useState(esPdfInicial)
  const [error, setError] = useState<string | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [intento, setIntento] = useState(0)
  const [abierto, setAbierto] = useState(true)
  const [accesoDenegado, setAccesoDenegado] = useState(false)
  const blobUrlRef = useRef<string | null>(null)
  const peticionRef = useRef<AbortController | null>(null)
  const cierreNotificadoRef = useRef(false)
  const mostrarDescarga = puedeDescargar && !accesoDenegado

  function liberarUrl() {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current)
      blobUrlRef.current = null
    }
  }

  // URL para descarga autenticada con attachment
  const descargaUrl = urlDescarga ?? (
    urlContenido.includes('disposicion=inline')
      ? urlContenido.replace('disposicion=inline', 'disposicion=attachment')
      : `${urlContenido}${urlContenido.includes('?') ? '&' : '?'}disposicion=attachment`
  )

  const normalizarRutaApi = (url: string): string => {
    return url.startsWith('/api') ? url.slice(4) : url
  }

  useEffect(() => {
    if (!dialogo.current?.open) {
      focoPrevioRef.current = document.activeElement as HTMLElement | null
    }
    dialogo.current?.showModal()

    return () => {
      if (focoPrevioRef.current?.isConnected) focoPrevioRef.current.focus()
    }
  }, [])

  useEffect(() => {
    if (!abierto) return
    const controlador = new AbortController()
    peticionRef.current = controlador

    async function ejecutar() {
      liberarUrl()
      setBlobUrl(null)
      setError(null)
      setAccesoDenegado(false)
      setIncompatible(!esPdfInicial)
      setCargando(esPdfInicial)
      if (!esPdfInicial) return

      try {
        const ruta = normalizarRutaApi(urlContenido)
        const resultado = await apiFetchArchivo(ruta, controlador.signal)
        if (controlador.signal.aborted) return

        // 1. Validar tipo MIME retornado por la respuesta
        const mimeRespuesta = resultado.blob.type?.trim().toLowerCase()
        if (mimeRespuesta && mimeRespuesta !== 'application/pdf' && mimeRespuesta !== 'application/x-pdf') {
          setIncompatible(true)
          setCargando(false)
          return
        }

        // 2. Validar firma mágica del PDF (%PDF-)
        let encabezado = ''
        try {
          encabezado = await resultado.blob.slice(0, 5).text()
        } catch {
          encabezado = ''
        }
        // Blob.text() no es cancelable: comprobar de nuevo antes de crear recursos o estado.
        if (controlador.signal.aborted) return

        if (!encabezado.startsWith('%PDF-')) {
          setIncompatible(true)
          setCargando(false)
          return
        }

        const url = URL.createObjectURL(resultado.blob)
        blobUrlRef.current = url
        setBlobUrl(url)
        setError(null)
        setIncompatible(false)
      } catch (err: unknown) {
        if (controlador.signal.aborted) return
        if (err instanceof ApiError) {
          setAccesoDenegado(err.status === 401 || err.status === 403)
          if (err.status === 401) {
            setError('Sesión expirada o no autenticada. Por favor inicie sesión nuevamente.')
          } else if (err.status === 403) {
            setError('No tiene permiso para consultar este documento.')
          } else if (err.status === 404) {
            setError('El documento solicitado no fue encontrado o no está vigente.')
          } else if (err.status === 502) {
            setError('No fue posible recuperar el documento almacenado. Intente nuevamente.')
          } else {
            setError('No fue posible cargar el documento. Intente nuevamente.')
          }
        } else {
          setError('No fue posible conectar con el servidor. Compruebe su conexión e intente nuevamente.')
        }
      } finally {
        if (!controlador.signal.aborted) {
          setCargando(false)
        }
      }
    }

    void ejecutar()

    return () => {
      controlador.abort()
      liberarUrl()
      if (peticionRef.current === controlador) peticionRef.current = null
    }
  }, [urlContenido, esPdfInicial, intento, abierto])

  const manejarReintentar = () => {
    peticionRef.current?.abort()
    liberarUrl()
    setBlobUrl(null)
    setError(null)
    setIncompatible(!esPdfInicial)
    setCargando(esPdfInicial)
    setIntento((actual) => actual + 1)
  }

  const manejarCerrar = () => {
    peticionRef.current?.abort()
    liberarUrl()
    dialogo.current?.close()
  }

  const manejarCierre = () => {
    if (cierreNotificadoRef.current) return
    cierreNotificadoRef.current = true
    peticionRef.current?.abort()
    liberarUrl()
    setAbierto(false)
    if (focoPrevioRef.current?.isConnected) focoPrevioRef.current.focus()
    onCerrar()
  }

  return (
    <dialog
      ref={dialogo}
      className="modal modal-preview"
      aria-labelledby="modal-preview-titulo"
      aria-modal="true"
      onCancel={(evento) => {
        evento.preventDefault()
        manejarCerrar()
      }}
      onClose={manejarCierre}
    >
      <div className="modal-header">
        <h2 id="modal-preview-titulo" title={nombreArchivo}>
          {nombreArchivo}
        </h2>
        <button
          type="button"
          className="btn-icon"
          aria-label="Cerrar previsualizador"
          onClick={manejarCerrar}
        >
          ×
        </button>
      </div>

      <section className="modal-section" aria-live="polite">
        {incompatible ? (
          <div className="preview-estado" data-testid="preview-no-compatible">
            <span className="preview-estado-icono" aria-hidden="true">⚠️</span>
            <h3>Formato no compatible con el visor</h3>
            <p className="preview-estado-mensaje">
              El formato de este archivo no puede previsualizarse mediante el visor del MVP.
              Actualmente solo se admite la previsualización de archivos PDF.
            </p>
            {mostrarDescarga && descargaUrl && (
              <a
                href={descargaUrl}
                className="btn btn-primary"
                download={nombreArchivo}
              >
                Descargar archivo
              </a>
            )}
          </div>
        ) : cargando ? (
          <div className="preview-estado" data-testid="preview-cargando">
            <div className="spinner-preview" aria-hidden="true" />
            <p className="preview-estado-mensaje">Cargando previsualización del documento…</p>
          </div>
        ) : error ? (
          <div className="preview-estado" data-testid="preview-error">
            <span className="preview-estado-icono" aria-hidden="true">⚠️</span>
            <h3 className="preview-estado-error">No se pudo cargar el documento</h3>
            <p className="preview-estado-mensaje">{error}</p>
            <div className="preview-acciones-error">
              {!accesoDenegado && <button
                type="button"
                className="btn btn-outline"
                onClick={manejarReintentar}
              >
                Reintentar
              </button>}
              {mostrarDescarga && descargaUrl && (
                <a
                  href={descargaUrl}
                  className="btn btn-primary"
                  download={nombreArchivo}
                >
                  Descargar archivo
                </a>
              )}
            </div>
          </div>
        ) : blobUrl ? (
          <iframe
            src={blobUrl}
            title={`Previsualización de ${nombreArchivo}`}
            className="preview-iframe"
            data-testid="preview-iframe"
          />
        ) : null}
      </section>

      <div className="modal-acciones">
        {mostrarDescarga && descargaUrl && (
          <a
            href={descargaUrl}
            className="btn btn-outline"
            download={nombreArchivo}
            style={{ marginRight: 'auto' }}
          >
            Descargar
          </a>
        )}
        <button
          type="button"
          className="btn btn-primary"
          onClick={manejarCerrar}
        >
          Cerrar
        </button>
      </div>
    </dialog>
  )
}

