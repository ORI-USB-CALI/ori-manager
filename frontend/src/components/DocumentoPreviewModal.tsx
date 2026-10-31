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

  const esPdf = (tipoMime && tipoMime === 'application/pdf') || nombreArchivo.toLowerCase().endsWith('.pdf')

  const [cargando, setCargando] = useState(esPdf)
  const [error, setError] = useState<string | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [intento, setIntento] = useState(0)
  const blobUrlRef = useRef<string | null>(null)

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
    focoPrevioRef.current = document.activeElement as HTMLElement | null
    dialogo.current?.showModal()

    return () => {
      focoPrevioRef.current?.focus()
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (!esPdf) return

    let cancelado = false

    async function ejecutar() {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }

      try {
        const ruta = normalizarRutaApi(urlContenido)
        const resultado = await apiFetchArchivo(ruta)
        if (cancelado) return
        const url = URL.createObjectURL(resultado.blob)
        blobUrlRef.current = url
        setBlobUrl(url)
        setError(null)
      } catch (err: unknown) {
        if (cancelado) return
        if (err instanceof ApiError) {
          if (err.status === 401) {
            setError('Sesión expirada o no autenticada. Por favor inicie sesión nuevamente.')
          } else if (err.status === 403) {
            setError('No tiene permiso para consultar este documento.')
          } else if (err.status === 404) {
            setError('El documento solicitado no fue encontrado o no está vigente.')
          } else if (err.status === 502) {
            setError(typeof err.detail === 'string' ? err.detail : (err.message || 'No fue posible recuperar el documento del almacenamiento.'))
          } else {
            setError(typeof err.detail === 'string' ? err.detail : (err.message || 'Error al recuperar el documento.'))
          }
        } else if (err instanceof Error) {
          setError(err.message)
        } else {
          setError('Ocurrió un error inesperado al cargar la previsualización.')
        }
      } finally {
        if (!cancelado) {
          setCargando(false)
        }
      }
    }

    void ejecutar()

    return () => {
      cancelado = true
    }
  }, [urlContenido, esPdf, intento])

  const manejarReintentar = () => {
    setCargando(true)
    setError(null)
    setIntento((actual) => actual + 1)
  }

  const manejarCerrar = () => {
    dialogo.current?.close()
  }

  return (
    <dialog
      ref={dialogo}
      className="modal modal-preview"
      aria-labelledby="modal-preview-titulo"
      aria-modal="true"
      onCancel={onCerrar}
      onClose={onCerrar}
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
        {!esPdf ? (
          <div className="preview-estado" data-testid="preview-no-compatible">
            <span className="preview-estado-icono" aria-hidden="true">⚠️</span>
            <h3>Formato no compatible con el visor</h3>
            <p className="preview-estado-mensaje">
              El formato de este archivo no puede previsualizarse mediante el visor del MVP.
              Actualmente solo se admite la previsualización de archivos PDF.
            </p>
            {puedeDescargar && descargaUrl && (
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
              <button
                type="button"
                className="btn btn-outline"
                onClick={manejarReintentar}
              >
                Reintentar
              </button>
              {puedeDescargar && descargaUrl && (
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
        {puedeDescargar && descargaUrl && (
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

