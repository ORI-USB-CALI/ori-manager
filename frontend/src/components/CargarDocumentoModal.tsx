import { type ChangeEvent, type DragEvent, useEffect, useRef, useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'

export interface CargarDocumentoModalProps {
  convenioId: number
  onCerrar: () => void
  onDocumentoCargado?: () => void
}

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function CargarDocumentoModal({
  convenioId,
  onCerrar,
  onDocumentoCargado,
}: CargarDocumentoModalProps) {
  const notify = useNotifications()
  const dialogo = useRef<HTMLDialogElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [archivo, setArchivo] = useState<File | null>(null)
  const [errorLocal, setErrorLocal] = useState<string | null>(null)
  const [dragSobre, setDragSobre] = useState(false)
  const [subiendo, setSubiendo] = useState(false)

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  const validarYEstablecerArchivo = (file: File | null) => {
    setErrorLocal(null)
    if (!file) {
      setArchivo(null)
      return
    }

    const nombre = file.name.toLowerCase()
    const esExtensionPdf = nombre.endsWith('.pdf')

    if (!esExtensionPdf) {
      setErrorLocal('Solo se permiten documentos en formato PDF')
      setArchivo(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    const limite20MB = 20 * 1024 * 1024
    if (file.size > limite20MB) {
      setErrorLocal('El archivo supera el tamaño máximo permitido (20 MB)')
      setArchivo(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setArchivo(file)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!subiendo) {
      setDragSobre(true)
    }
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragSobre(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragSobre(false)
    if (subiendo) return

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0]
      validarYEstablecerArchivo(file)
    }
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validarYEstablecerArchivo(e.target.files[0])
    }
  }

  const handleSubir = async () => {
    if (!archivo) return
    if (!archivo.name.toLowerCase().endsWith('.pdf')) {
      setErrorLocal('Solo se permiten documentos en formato PDF')
      return
    }

    setSubiendo(true)
    setErrorLocal(null)

    try {
      const formData = new FormData()
      formData.append('archivo', archivo)

      await apiFetch(`/convenios/${convenioId}/documentos`, {
        method: 'POST',
        body: formData,
      })

      notify({ type: 'success', message: 'Documento cargado correctamente' })
      if (onDocumentoCargado) onDocumentoCargado()
      dialogo.current?.close()
    } catch (err: unknown) {
      const mensaje =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No fue posible cargar el documento'
      setErrorLocal(mensaje)
      notify({ type: 'error', message: mensaje })
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <dialog
      ref={dialogo}
      className="modal modal-cargar-documento"
      onCancel={(event) => {
        if (subiendo) event.preventDefault()
      }}
      onClose={onCerrar}
      aria-labelledby="cargar-documento-modal-titulo"
    >
      <div className="modal-header">
        <h2 id="cargar-documento-modal-titulo">Cargar documento soporte (PDF)</h2>
        <button
          type="button"
          className="btn-icon"
          aria-label="Cerrar"
          onClick={() => dialogo.current?.close()}
          disabled={subiendo}
        >
          ×
        </button>
      </div>

      <section className="modal-section">
        <p className="section-help">
          Selecciona o arrastra el archivo en formato PDF asociado a este convenio (máx. 20 MB).
        </p>

        {errorLocal && (
          <div className="alert-error" role="alert" style={{ marginBottom: '1rem' }}>
            {errorLocal}
          </div>
        )}

        <div
          className={`dropzone ${dragSobre ? 'dropzone-active' : ''} ${subiendo ? 'dropzone-disabled' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => {
            if (!subiendo) fileInputRef.current?.click()
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !subiendo) {
              fileInputRef.current?.click()
            }
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            disabled={subiendo}
          />

          <div className="dropzone-contenido">
            <svg
              className="dropzone-icono"
              viewBox="0 0 24 24"
              width="40"
              height="40"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>

            {archivo ? (
              <div className="dropzone-archivo-info">
                <span className="dropzone-archivo-nombre">📄 {archivo.name}</span>
                <span className="dropzone-archivo-tamano">({tamanoLegible(archivo.size)})</span>
              </div>
            ) : (
              <div>
                <p className="dropzone-texto-principal">
                  Arrastra tu archivo PDF aquí o <strong>haz clic para examinar</strong>
                </p>
                <small className="dropzone-texto-secundario">Solo archivos .pdf hasta 20 MB</small>
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="modal-acciones">
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => dialogo.current?.close()}
          disabled={subiendo}
        >
          Cancelar
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleSubir}
          disabled={!archivo || Boolean(errorLocal) || subiendo}
        >
          {subiendo ? (
            <span className="spinner-container">
              <span className="spinner" aria-hidden="true" />
              Subiendo documento…
            </span>
          ) : (
            'Subir documento PDF'
          )}
        </button>
      </div>
    </dialog>
  )
}
