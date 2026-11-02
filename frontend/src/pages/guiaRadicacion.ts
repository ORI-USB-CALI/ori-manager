// Pasos de la guía de radicación para las ocho secciones del formulario de
// solicitud (HU-39 FE02). Solo es configuración: el motor de HU-38 los filtra
// por rol y centra las explicaciones esenciales si un destino deja de ser visible.
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
const AYUDA_TELEFONO = ' Para teléfonos fuera de Colombia, incluya el indicativo con +. Puede indicar una extensión de 1 a 6 dígitos con ext; al guardar se conserva como ;ext=.'

/* Contrato integrado de SolicitudPage, SolicitudCampos y _errores_radicacion (HT-14). */
export const PASOS_SECCIONES_SOLICITUD: PasoRecorrido[] = [
  {
    destino: D.solicitante,
    mantenerSinDestino: true,
    roles: ['SOLICITANTE_INTERNO'],
    titulo: '1. Información del solicitante',
    descripcion:
      'Identifica a quien presenta la solicitud. Sus datos se precargan desde su perfil y se guardan como copia en '
      + 'esta solicitud. Revise el nombre y su cargo, obligatorios para radicar. La Facultad o Dependencia '
      + 'y el Programa académico o Unidad requeridos dependen de su vinculación en la Universidad.',
  },
  {
    destino: D.solicitante,
    mantenerSinDestino: true,
    roles: ['SOLICITANTE_EXTERNO'],
    titulo: '1. Información del solicitante',
    descripcion:
      'Identifica a quien presenta la solicitud. Sus datos se precargan desde su perfil y se guardan como copia en '
      + 'esta solicitud. Revise el nombre, el tipo de documento, la Identificación y la Empresa o Entidad: son obligatorios '
      + 'para radicar. La identificación debe corresponder al tipo elegido. Si es NIT, escriba la base sin DV '
      + 'y registre su dígito de verificación en el campo separado.',
  },
  {
    destino: D.contraparte,
    mantenerSinDestino: true,
    titulo: '2. Información de la contraparte',
    descripcion:
      'Datos de la institución o entidad con la que se propone el convenio: nombre, tipo de entidad, tipo y número '
      + 'de identificación, correo institucional, país, ciudad, teléfono y dirección. Si la entidad es una empresa, '
      + 'el sector económico es obligatorio. El país se elige de la lista y la ciudad se escribe como texto. '
      + 'La identificación se valida según su tipo. Si es NIT, escriba la base y el dígito de verificación por separado. '
      + 'La ciudad admite de 2 a 120 caracteres; no se comprueba su existencia geográfica. '
      + 'La dirección admite de 5 a 200 caracteres con letras y un número o dos referencias separadas por coma o barra, '
      + 'también para zonas rurales. No se verifica su existencia física.' + AYUDA_TELEFONO,
  },
  {
    destino: D.contactoContraparte,
    mantenerSinDestino: true,
    titulo: '3. Contacto de contraparte',
    descripcion:
      'Persona de la contraparte con quien la ORI coordinará la gestión de la solicitud. Registre su nombre, cargo, '
      + 'teléfono y correo electrónico; todos son obligatorios para radicar.' + AYUDA_TELEFONO,
  },
  {
    destino: D.convenio,
    mantenerSinDestino: true,
    titulo: '4. Información del convenio',
    descripcion:
      'Describe el convenio que se propone. Seleccione el tipo de convenio e indique el tiempo estimado de vigencia, '
      + 'la justificación, el objeto, las actividades de cada una de las partes, las metas esperadas, la implicación '
      + 'financiera y los requisitos para la renovación. Todos son obligatorios para radicar.',
  },
  {
    destino: D.supervisorUsb,
    mantenerSinDestino: true,
    titulo: '5. Supervisor o encargado de ejecución USB',
    descripcion:
      'Persona de la Universidad de San Buenaventura responsable de acompañar la ejecución del convenio. '
      + 'Registre su nombre, cargo, teléfono y correo electrónico; todos son obligatorios para radicar.' + AYUDA_TELEFONO,
  },
  {
    destino: D.supervisorContraparte,
    mantenerSinDestino: true,
    titulo: '6. Supervisor o encargado de ejecución de la contraparte',
    descripcion:
      'Persona de la contraparte responsable de la ejecución del convenio. Registre su nombre, cargo, teléfono y '
      + 'correo electrónico; todos son obligatorios para radicar.' + AYUDA_TELEFONO,
  },
  {
    destino: D.documentacion,
    mantenerSinDestino: true,
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
    mantenerSinDestino: true,
    titulo: '8. Observaciones adicionales',
    descripcion:
      'Espacio opcional para información complementaria que no haya incluido en las secciones anteriores.',
  },
]
