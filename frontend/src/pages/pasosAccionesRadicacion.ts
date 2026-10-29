/**
 * HU-39 FE-03: pasos informativos de acciones y seguimiento.
 *
 * Configuración independiente de FE-01/FE-02: el tipo es compatible con
 * PasoRecorrido del motor de HU-38, pero no lo importa hasta la integración.
 * No ejecuta operaciones sobre solicitudes ni realiza llamadas a la API.
 *
 * Los destinos coinciden con los data-tour del formulario compartido de HU-39.
 * Los pasos sin destino son orientaciones generales en un globo no anclado.
 */
export interface PasoAccionRadicacion {
  destino?: string
  titulo: string
  descripcion: string
}

const PASOS_ACCIONES: readonly PasoAccionRadicacion[] = [
  {
    destino: 'solicitud-documentacion',
    titulo: 'Adjuntar documentos',
    descripcion:
      'En Documentación, seleccione el tipo de soporte, elija un archivo PDF, JPG o PNG de hasta 10 MB y pulse Adjuntar. '
      + 'Para radicar se necesita al menos un documento de representación legal de la contraparte. '
      + 'Si todavía no hay borrador, adjuntar puede guardarlo primero. La guía no carga archivos por usted.',
  },
  {
    destino: 'solicitud-guardar-borrador',
    titulo: 'Guardar borrador',
    descripcion:
      'Use Guardar borrador para conservar la información y continuar después sin radicarla. '
      + 'Si la solicitud fue devuelta, este botón puede mostrarse como Guardar cambios. '
      + 'Avanzar por esta guía no guarda los datos automáticamente.',
  },
  {
    destino: 'solicitud-radicar',
    titulo: 'Radicar la solicitud',
    descripcion:
      'Cuando haya diligenciado los campos obligatorios y adjuntado los soportes requeridos, '
      + 'pulse Radicar solicitud. Si fue devuelta, verá Volver a radicar. '
      + 'El sistema verifica los requisitos antes de radicar. La guía solo explica esta acción: no la ejecuta.',
  },
  {
    titulo: 'Cómo corregir errores de validación',
    descripcion:
      'Si aparece un error, revise el mensaje junto al campo o en la sección Documentación, '
      + 'corrija los datos y vuelva a intentar la acción. Compruebe los campos obligatorios, '
      + 'el formato del correo y del teléfono y el tipo y número de identificación. '
      + 'En un NIT, el número y el dígito de verificación se diligencian por separado. '
      + 'Los errores del servidor también pueden indicar qué campo debe corregirse.',
  },
]

const PASO_DEVOLUCION: PasoAccionRadicacion = {
  titulo: 'Corregir una solicitud devuelta',
  descripcion:
    'Si el estado es DEVUELTA, lea las Observaciones de devolución ORI, corrija los datos '
    + 'y soportes señalados, guarde sus cambios y use Volver a radicar cuando esté listo. '
    + 'El recorrido no modifica la solicitud por usted.',
}

const PASO_SEGUIMIENTO: PasoAccionRadicacion = {
  titulo: 'Consultar Mis solicitudes',
  descripcion:
    'Para consultar el estado y el seguimiento de sus trámites, vaya a Mis solicitudes. '
    + 'Desde este formulario puede utilizar Volver para regresar al listado de solicitudes. '
    + 'La guía no cambia de página ni envía solicitudes automáticamente.',
}

/** Devuelve nuevos pasos para evitar mutaciones entre distintas aperturas del tour. */
export function crearPasosAccionesRadicacion(esDevuelta = false): PasoAccionRadicacion[] {
  return [
    ...PASOS_ACCIONES.map((paso) => ({ ...paso })),
    ...(esDevuelta ? [{ ...PASO_DEVOLUCION }] : []),
    { ...PASO_SEGUIMIENTO },
  ]
}
