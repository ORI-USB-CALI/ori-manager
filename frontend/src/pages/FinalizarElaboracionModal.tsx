import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import type { Convenio } from './epica02'

interface Props {
  convenioId: number
  valores: Record<string, string | number | null>
  onFinalizado: () => Promise<unknown>
  onErrorValidacion: (error: unknown) => void
  onCerrar: () => void
}

function texto(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'No fue posible completar la operación.'
}

export function FinalizarElaboracionModal({ convenioId, valores, onFinalizado, onErrorValidacion, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)
  const notify = useNotifications()

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  const finalizar = useMutation({
    mutationFn: () => apiFetch<Convenio>(`/convenios/${convenioId}/elaboracion/finalizar`, {
      method: 'POST',
      body: JSON.stringify(valores),
    }),
    onSuccess: async () => {
      await onFinalizado()
      dialogo.current?.close()
      notify({ type: 'success', message: 'Elaboración finalizada. El convenio quedó en revisión jurídica.' })
    },
    onError: (error) => {
      onErrorValidacion(error)
      dialogo.current?.close()
      notify({ type: 'error', message: texto(error) })
    },
  })

  return (
    <dialog ref={dialogo} className="modal" onClose={onCerrar} aria-labelledby="finalizar-modal-titulo">
      <div className="modal-header">
        <h2 id="finalizar-modal-titulo">Finalizar elaboración</h2>
        <button type="button" className="btn-icon" aria-label="Cerrar" onClick={() => dialogo.current?.close()}>
          ×
        </button>
      </div>

      <section className="modal-section">
        <p>
          Esta acción congela la información del convenio tal como está ahora y abre una ronda de
          revisión jurídica. El convenio dejará de ser editable desde esta pantalla.
        </p>
        <p className="texto-secundario">¿Confirma que desea finalizar la elaboración?</p>
      </section>

      <div className="modal-acciones">
        <button type="button" className="btn btn-outline" onClick={() => dialogo.current?.close()} disabled={finalizar.isPending}>
          Cancelar
        </button>
        <button type="button" className="btn btn-primary" onClick={() => finalizar.mutate()} disabled={finalizar.isPending}>
          {finalizar.isPending ? 'Finalizando…' : 'Confirmar y enviar a Jurídica'}
        </button>
      </div>
    </dialog>
  )
}
