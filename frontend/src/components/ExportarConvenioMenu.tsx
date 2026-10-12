import { useEffect, useRef, useState } from 'react'

import { ApiError, apiFetchArchivo } from '../app/api'
import { descargarBlob } from '../app/descargas'
import { useNotifications } from '../app/notifications/useNotifications'
import { ModalDatosIncompletosExportacion } from './ModalDatosIncompletosExportacion'

interface Props {
  convenioId: number
}

type FormatoExportacion = 'pdf' | 'excel'

/** Campos pendientes del error de exportación: `campos_faltantes` (HU-24) o `faltantes`. */
function camposFaltantesDe(detalle: unknown): string[] {
  if (!detalle || typeof detalle !== 'object') return []
  const lista = 'campos_faltantes' in detalle ? detalle.campos_faltantes
    : 'faltantes' in detalle ? detalle.faltantes
      : null
  return Array.isArray(lista) ? lista.filter((campo): campo is string => typeof campo === 'string') : []
}

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
      // La exportación se publica en /api/v1 (apiFetchArchivo antepone /api).
      const { blob, nombreArchivo } = await apiFetchArchivo(
        `/v1/convenios/${convenioId}/exportar?formato=${formato}`,
      )
      // FE-02: nombre de Content-Disposition o, si no viene, la convención estándar.
      descargarBlob(blob, nombreArchivo ?? `Convenio_${convenioId}.${formato === 'excel' ? 'xlsx' : 'pdf'}`)
      notify({ type: 'success', message: 'Documento generado y descargado correctamente' })
    } catch (error) {
      if (!(error instanceof ApiError)) {
        notify({
          type: 'error',
          message: error instanceof Error ? error.message : 'Error inesperado al descargar el archivo.',
        })
        return
      }

      // TAREA FE-03 (CA-03): Interceptar error 422/400 de datos incompletos
      const faltantes = camposFaltantesDe(error.detail)
      if ((error.status === 422 || error.status === 400) && faltantes.length > 0) {
        setCamposFaltantes(faltantes)
        setModalErrorAbierto(true)
        return
      }

      if (error.status === 403) {
        notify({ type: 'error', message: 'No cuenta con permisos para exportar este convenio.' })
        return
      }

      notify({ type: 'error', message: error.message || `Error al generar el documento (${error.status})` })
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
