import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  titulo: string
  confirmar: string
  procesando: string
  pendiente: boolean
  confirmarDeshabilitado?: boolean
  children: ReactNode
  onConfirmar: () => void
  onCerrar: () => void
}

export function ConfirmacionModal({ titulo, confirmar, procesando, pendiente, confirmarDeshabilitado = false, children, onConfirmar, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  return (
    <dialog
      ref={dialogo}
      className="modal"
      onCancel={(event) => {
        if (pendiente) event.preventDefault()
      }}
      onClose={onCerrar}
      aria-labelledby="confirmacion-modal-titulo"
    >
      <div className="modal-header">
        <h2 id="confirmacion-modal-titulo">{titulo}</h2>
        <button type="button" className="btn-icon" aria-label="Cerrar" onClick={() => dialogo.current?.close()} disabled={pendiente}>
          ×
        </button>
      </div>
      <section className="modal-section">{children}</section>
      <div className="modal-acciones">
        <button type="button" className="btn btn-outline" onClick={() => dialogo.current?.close()} disabled={pendiente}>Cancelar</button>
        <button type="button" className="btn btn-primary" onClick={onConfirmar} disabled={pendiente || confirmarDeshabilitado}>
          {pendiente ? procesando : confirmar}
        </button>
      </div>
    </dialog>
  )
}
