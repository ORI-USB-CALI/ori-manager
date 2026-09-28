import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'

interface Props {
  disabled?: boolean
  onFirma: (firma: string | null) => void
}

export function FirmaCanvas({ disabled = false, onFirma }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const dibujando = useRef(false)
  const [tieneTrazo, setTieneTrazo] = useState(false)

  function coordenadas(event: ReactPointerEvent<HTMLCanvasElement>) {
    const elemento = canvas.current
    if (!elemento) return null
    const rect = elemento.getBoundingClientRect()
    return {
      x: (event.clientX - rect.left) * (elemento.width / rect.width),
      y: (event.clientY - rect.top) * (elemento.height / rect.height),
    }
  }

  function iniciar(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (disabled || !canvas.current) return
    const punto = coordenadas(event)
    const contexto = canvas.current.getContext('2d')
    if (!punto || !contexto) return
    event.currentTarget.setPointerCapture(event.pointerId)
    contexto.strokeStyle = '#1a1d20'
    contexto.lineWidth = 4
    contexto.lineCap = 'round'
    contexto.lineJoin = 'round'
    contexto.beginPath()
    contexto.moveTo(punto.x, punto.y)
    contexto.lineTo(punto.x + 0.1, punto.y + 0.1)
    contexto.stroke()
    dibujando.current = true
    setTieneTrazo(true)
  }

  function dibujar(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (disabled || !dibujando.current || !canvas.current) return
    const punto = coordenadas(event)
    const contexto = canvas.current.getContext('2d')
    if (!punto || !contexto) return
    contexto.lineTo(punto.x, punto.y)
    contexto.stroke()
  }

  function finalizar() {
    if (!dibujando.current || !canvas.current) return
    dibujando.current = false
    onFirma(canvas.current.toDataURL('image/png'))
  }

  function limpiar() {
    if (disabled || !canvas.current) return
    canvas.current.getContext('2d')?.clearRect(0, 0, canvas.current.width, canvas.current.height)
    dibujando.current = false
    setTieneTrazo(false)
    onFirma(null)
  }

  return (
    <div className="firma-control">
      <p id="firma-instrucciones" className="section-help">Dibuja tu firma dentro del recuadro usando el mouse, lápiz o pantalla táctil.</p>
      <canvas
        ref={canvas}
        className="firma-canvas"
        width={800}
        height={240}
        aria-label="Área para dibujar la firma de conformidad"
        aria-describedby="firma-instrucciones"
        tabIndex={0}
        onPointerDown={iniciar}
        onPointerMove={dibujar}
        onPointerUp={finalizar}
        onPointerCancel={finalizar}
      />
      <div className="firma-acciones">
        <span className={`firma-estado ${tieneTrazo ? 'firma-estado-lista' : ''}`}>
          {tieneTrazo ? 'Firma registrada' : 'Firma pendiente'}
        </span>
        <button className="btn btn-outline btn-small" type="button" onClick={limpiar} disabled={disabled || !tieneTrazo}>
          Limpiar firma
        </button>
      </div>
    </div>
  )
}
