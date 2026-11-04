/**
 * Nombre del archivo según la cabecera Content-Disposition. Se prefiere
 * `filename*` (RFC 5987, admite tildes y eñes) y después `filename`.
 */
export function nombreArchivoDesdeContentDisposition(cabecera: string | null): string | null {
  if (!cabecera) return null

  const extendido = /filename\*\s*=\s*[^']*'[^']*'([^;]+)/i.exec(cabecera)
  if (extendido) {
    try {
      return decodeURIComponent(extendido[1].trim().replace(/^"|"$/g, ''))
    } catch {
      // Codificación inválida: se intenta con `filename`.
    }
  }

  const simple = /filename\s*=\s*(?:"([^"]*)"|([^;]+))/i.exec(cabecera)
  const nombre = (simple?.[1] ?? simple?.[2])?.trim()
  return nombre || null
}

/** Dispara la descarga de un Blob con un enlace temporal invisible. */
export function descargarBlob(blob: Blob, nombreArchivo: string): void {
  const url = window.URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  enlace.style.display = 'none'
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  // Revocar en el mismo ciclo puede cancelar la descarga en algunos navegadores.
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0)
}
