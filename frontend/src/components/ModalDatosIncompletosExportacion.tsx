import { useEffect, useRef } from 'react'

interface Props {
  camposFaltantes: string[]
  onCerrar: () => void
}

const NOMBRES_CAMPOS: Record<string, string> = {
  objeto: 'Objeto del convenio',
  tipo_convenio: 'Tipo de convenio',
  unidad_organizacional: 'Unidad organizacional solicitante',
  aliado: 'Entidad aliada',
  fecha_inicio: 'Fecha de inicio',
  fecha_vencimiento: 'Fecha de vencimiento',
  implicacion_financiera: 'Compromiso financiero',
}

function formatearNombreCampo(campo: string): string {
  if (campo in NOMBRES_CAMPOS) {
    return NOMBRES_CAMPOS[campo]
  }
  return campo.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function ModalDatosIncompletosExportacion({ camposFaltantes, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  return (
    <dialog
      ref={dialogo}
      className="modal modal-exportacion-error"
      onClose={onCerrar}
      aria-labelledby="modal-datos-incompletos-titulo"
    >
      <div className="modal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ color: '#d97706', flexShrink: 0 }}
            aria-hidden="true"
          >
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <h2 id="modal-datos-incompletos-titulo">No se puede generar el documento</h2>
        </div>
        <button
          type="button"
          className="btn-icon"
          aria-label="Cerrar"
          onClick={() => dialogo.current?.close()}
        >
          ×
        </button>
      </div>

      <section className="modal-section">
        <p style={{ marginBottom: '16px', lineHeight: 1.5 }}>
          El convenio no cuenta con la información requerida para emitir un documento oficial. Por favor complete los siguientes campos antes de continuar:
        </p>
        <ul style={{ paddingLeft: '24px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {camposFaltantes.map((campo) => (
            <li key={campo}>
              <strong>{formatearNombreCampo(campo)}</strong>
            </li>
          ))}
        </ul>
      </section>

      <div className="modal-acciones">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => dialogo.current?.close()}
        >
          Entendido
        </button>
      </div>
    </dialog>
  )
}
