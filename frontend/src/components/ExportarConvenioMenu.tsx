import { useEffect, useRef, useState } from 'react'

import { useNotifications } from '../app/notifications/useNotifications'
import { ModalDatosIncompletosExportacion } from './ModalDatosIncompletosExportacion'

interface Props {
  convenioId: number
}

type FormatoExportacion = 'pdf' | 'excel'

export function ExportarConvenioMenu({ convenioId }: Props) {
  const [abierto, setAbierto] = useState(false)
  const [descargando, setDescargando] = useState(false)
  const [formatoActivo, setFormatoActivo] = useState<FormatoExportacion | null>(null)
  const [modalErrorAbierto, setModalErrorAbierto] = useState(false)
  const [camposFaltantes, setCamposFaltantes] = useState<string[]>([])

  const contenedorRef = useRef<HTMLDivElement>(null)
  const notify = useNotifications()

  // Cerrar al hacer clic fuera o presionar Escape
  useEffect(() => {
    function manejarClicFuera(evento: MouseEvent) {
      if (contenedorRef.current && !contenedorRef.current.contains(evento.target as Node)) {
        setAbierto(false)
      }
    }

    function manejarEscape(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setAbierto(false)
      }
    }

    if (abierto) {
      document.addEventListener('mousedown', manejarClicFuera)
      document.addEventListener('keydown', manejarEscape)
    }

    return () => {
      document.removeEventListener('mousedown', manejarClicFuera)
      document.removeEventListener('keydown', manejarEscape)
    }
  }, [abierto])

  async function ejecutarDescarga(formato: FormatoExportacion) {
    setDescargando(true)
    setFormatoActivo(formato)
    setAbierto(false)

    try {
      const respuesta = await fetch(`/api/v1/convenios/${convenioId}/exportar?formato=${formato}`, {
        credentials: 'include',
      })

      if (!respuesta.ok) {
        // En caso de error, el backend envía un JSON informativo
        const cuerpoTexto = await respuesta.text()
        let datosError: Record<string, unknown> | null = null
        try {
          datosError = JSON.parse(cuerpoTexto) as Record<string, unknown>
        } catch {
          // El cuerpo no era JSON
        }

        // TAREA FE-03 (CA-03): Interceptar error 422/400 de datos incompletos
        if (respuesta.status === 422 || respuesta.status === 400) {
          const detalle = datosError && typeof datosError === 'object' && 'detail' in datosError
            ? datosError.detail
            : datosError

          const faltantes = (detalle && typeof detalle === 'object' && 'faltantes' in detalle && Array.isArray((detalle as { faltantes: unknown }).faltantes)
            ? (detalle as { faltantes: string[] }).faltantes
            : (detalle && typeof detalle === 'object' && 'campos_faltantes' in detalle && Array.isArray((detalle as { campos_faltantes: unknown }).campos_faltantes)
              ? (detalle as { campos_faltantes: string[] }).campos_faltantes
              : null))

          if (faltantes && faltantes.length > 0) {
            setCamposFaltantes(faltantes)
            setModalErrorAbierto(true)
            return
          }
        }

        if (respuesta.status === 403) {
          notify({ type: 'error', message: 'No cuenta con permisos para exportar este convenio.' })
          return
        }

        const mensaje = (datosError && typeof datosError.detail === 'string'
          ? datosError.detail
          : (datosError && typeof datosError.detail === 'object' && datosError.detail && 'message' in datosError.detail
            ? String((datosError.detail as { message: unknown }).message)
            : `Error al generar el documento (${respuesta.status})`))

        notify({ type: 'error', message: mensaje })
        return
      }

      // Descargar el archivo binario (PDF o Excel)
      const blob = await respuesta.blob()
      const disposition = respuesta.headers.get('Content-Disposition')
      let nombreArchivo = `Convenio_${convenioId}.${formato === 'excel' ? 'xlsx' : 'pdf'}`
      if (disposition) {
        const match = /filename=["']?([^"';]+)["']?/i.exec(disposition)
        if (match && match[1]) {
          nombreArchivo = match[1]
        }
      }

      const urlDescarga = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = urlDescarga
      link.download = nombreArchivo
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(urlDescarga)

      notify({
        type: 'success',
        message: `Convenio exportado en ${formato.toUpperCase()} correctamente.`,
      })
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Error inesperado al descargar el archivo.',
      })
    } finally {
      setDescargando(false)
      setFormatoActivo(null)
    }
  }

  return (
    <>
      <div className="exportar-menu-contenedor" ref={contenedorRef}>
        <button
          type="button"
          className="btn btn-exportar"
          onClick={() => setAbierto((prev) => !prev)}
          disabled={descargando}
          aria-expanded={abierto}
          aria-haspopup="menu"
          aria-label="Exportar o generar documento del convenio"
        >
          {descargando ? (
            <>
              <span className="spinner-descarga" aria-hidden="true" />
              <span>{formatoActivo === 'excel' ? 'Generando Excel…' : 'Generando PDF…'}</span>
            </>
          ) : (
            <>
              {/* Icono Descarga / Exportar */}
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>Exportar / Generar Documento</span>
              {/* Icono Flecha hacia abajo */}
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ transform: abierto ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}
                aria-hidden="true"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </>
          )}
        </button>

        {abierto && !descargando && (
          <div className="exportar-menu-desplegable" role="menu">
            <button
              type="button"
              role="menuitem"
              className="exportar-menu-item"
              onClick={() => ejecutarDescarga('pdf')}
            >
              {/* Icono PDF */}
              <svg
                className="icono-pdf"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <path d="M9 13h2a1.5 1.5 0 0 0 1.5-1.5V11A1.5 1.5 0 0 0 11 9.5H9v6" />
                <path d="M15 9.5v6" />
              </svg>
              <div className="exportar-menu-item-texto">
                <strong>Exportar como PDF</strong>
                <small>Documento oficial con membrete y firmas</small>
              </div>
            </button>

            <button
              type="button"
              role="menuitem"
              className="exportar-menu-item"
              onClick={() => ejecutarDescarga('excel')}
            >
              {/* Icono Excel */}
              <svg
                className="icono-excel"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="8" y1="13" x2="16" y2="13" />
                <line x1="8" y1="17" x2="16" y2="17" />
                <line x1="12" y1="9" x2="12" y2="21" />
              </svg>
              <div className="exportar-menu-item-texto">
                <strong>Exportar como Excel</strong>
                <small>Hoja de cálculo estructurada (.xlsx)</small>
              </div>
            </button>
          </div>
        )}
      </div>

      {modalErrorAbierto && (
        <ModalDatosIncompletosExportacion
          camposFaltantes={camposFaltantes}
          onCerrar={() => setModalErrorAbierto(false)}
        />
      )}
    </>
  )
}
