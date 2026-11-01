// Pasos de la guía de radicación para las ocho secciones del formulario de
// solicitud (HU-39 FE02). Solo es configuración: el motor de HU-38 los filtra
// por rol y omite los destinos que no estén visibles.
import type { PasoRecorrido } from '../components/recorrido'

/**
 * Valores de `data-tour` de cada sección de `SolicitudPage.tsx` (HU-39 FE01).
 * El orden es el del formulario.
 */
export const DESTINOS_SECCIONES_SOLICITUD = {
  solicitante: 'solicitud-solicitante',
  contraparte: 'solicitud-contraparte',
  contactoContraparte: 'solicitud-contacto-contraparte',
  convenio: 'solicitud-convenio',
  supervisorUsb: 'solicitud-supervisor-usb',
  supervisorContraparte: 'solicitud-supervisor-contraparte',
  documentacion: 'solicitud-documentacion',
  observaciones: 'solicitud-observaciones',
} as const

/** Valores de `data-tour` de las acciones del formulario, para los pasos de HU-39 FE03. */
export const DESTINOS_ACCIONES_SOLICITUD = {
  ayuda: 'solicitud-ayuda',
  guardarBorrador: 'solicitud-guardar-borrador',
  radicar: 'solicitud-radicar',
} as const

const D = DESTINOS_SECCIONES_SOLICITUD

/* Las reglas que se mencionan son las vigentes (RN-08): obligatorios de
   `_errores_radicacion`, formatos de `core/validaciones.py` (HT-14) y la
   documentación de `services/documentos.py` en el backend. */
export const PASOS_SECCIONES_SOLICITUD: PasoRecorrido[] = [
  {
    destino: D.solicitante,
    roles: ['SOLICITANTE_INTERNO'],
    titulo: '1. Información del solicitante',
    descripcion:
      'Identifica a quien presenta la solicitud. Sus datos se precargan desde su perfil y se guardan como copia en '
      + 'esta solicitud. Revise el nombre, la Facultad o Dependencia, el Programa académico o Unidad cuando aplique '
      + 'y su cargo: son obligatorios para radicar.',
  },
  {
    destino: D.solicitante,
    roles: ['SOLICITANTE_EXTERNO'],
    titulo: '1. Información del solicitante',
    descripcion:
      'Identifica a quien presenta la solicitud. Sus datos se precargan desde su perfil y se guardan como copia en '
      + 'esta solicitud. Seleccione el tipo de documento y escriba el número: para NIT o cédula, solo los dígitos, sin '
      + 'puntos ni dígito de verificación. Si el tipo es NIT, el dígito de verificación va en su propio campo. '
      + 'El nombre, el tipo de documento, la identificación y la Empresa o Entidad son obligatorios para radicar.',
  },
  {
    destino: D.contraparte,
    titulo: '2. Información de la contraparte',
    descripcion:
      'Datos de la institución o entidad con la que se propone el convenio: nombre, tipo de entidad, tipo y número '
      + 'de identificación, correo institucional, país, ciudad, teléfono y dirección. El NIT se escribe sin el dígito '
      + 'de verificación, que tiene su propio campo. Si la entidad es una empresa, el sector económico es obligatorio. '
      + 'El país se elige de la lista y la ciudad se escribe como texto. Para teléfonos fuera de Colombia, incluya el '
      + 'indicativo con + (por ejemplo, +34 912 345 678). La dirección admite formatos urbanos, rurales e internacionales.',
  },
  {
    destino: D.contactoContraparte,
    titulo: '3. Contacto de contraparte',
    descripcion:
      'Persona de la contraparte con quien la ORI coordinará la gestión de la solicitud. Registre su nombre, cargo, '
      + 'teléfono y correo electrónico; todos son obligatorios para radicar.',
  },
  {
    destino: D.convenio,
    titulo: '4. Información del convenio',
    descripcion:
      'Describe el convenio que se propone. Seleccione el tipo de convenio e indique el tiempo estimado de vigencia, '
      + 'la justificación, el objeto, las actividades de cada una de las partes, las metas esperadas, la implicación '
      + 'financiera y los requisitos para la renovación. Todos son obligatorios para radicar.',
  },
  {
    destino: D.supervisorUsb,
    titulo: '5. Supervisor o encargado de ejecución USB',
    descripcion:
      'Persona de la Universidad de San Buenaventura responsable de acompañar la ejecución del convenio. '
      + 'Registre su nombre, cargo, teléfono y correo electrónico; todos son obligatorios para radicar.',
  },
  {
    destino: D.supervisorContraparte,
    titulo: '6. Supervisor o encargado de ejecución de la contraparte',
    descripcion:
      'Persona de la contraparte responsable de la ejecución del convenio. Registre su nombre, cargo, teléfono y '
      + 'correo electrónico; todos son obligatorios para radicar. El teléfono sigue las mismas reglas que el de la '
      + 'contraparte.',
  },
  {
    destino: D.documentacion,
    titulo: '7. Documentación',
    descripcion:
      'Seleccione el tipo de documento, elija el archivo y pulse Adjuntar. Se admiten archivos PDF, JPG y PNG de '
      + 'máximo 10 MB. Para radicar debe adjuntar al menos un documento de representación legal de la contraparte: '
      + 'Cámara de Comercio, RUT, Cédula del representante legal u Otro documento de representación legal (aparecen '
      + 'marcados en la lista). «Otro soporte» sirve como información complementaria, pero no reemplaza a los '
      + 'anteriores. Si la solicitud aún no está guardada, adjuntar un archivo guarda primero el borrador.',
  },
  {
    destino: D.observaciones,
    titulo: '8. Observaciones adicionales',
    descripcion:
      'Espacio opcional para información complementaria que no haya incluido en las secciones anteriores.',
  },
]
