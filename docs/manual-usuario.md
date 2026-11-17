# Manual de usuario — ORI Manager

ORI Manager es la plataforma de la Oficina de Relaciones Interinstitucionales (ORI) de la Universidad de San Buenaventura Cali para gestionar los convenios de la Universidad: desde que alguien solicita un convenio hasta que se firma, se le hace seguimiento y se renueva.

**Dirigido a:** todas las personas que usan la plataforma. Para saber qué partes leer, busque su rol en la tabla de la sección 1.

> Este manual describe el funcionamiento integrado en la rama `develop` del proyecto. No reemplaza la aceptación de QA de cada historia ni indica que una función ya esté publicada en producción.

## Contenido

**Parte I — Conceptos**
1. [Roles: quién puede hacer qué](#1-roles-quién-puede-hacer-qué)
2. [De la solicitud al convenio](#2-de-la-solicitud-al-convenio)

**Parte II — Para todos**
3. [Crear cuenta, ingresar y recuperar la contraseña](#3-crear-cuenta-ingresar-y-recuperar-la-contraseña)
4. [Navegación, Inicio y notificaciones](#4-navegación-inicio-y-notificaciones)
5. [Directorio público de convenios](#5-directorio-público-de-convenios)

**Parte III — Solicitantes**
6. [Guía de bienvenida](#6-guía-de-bienvenida)
7. [Crear y radicar una solicitud](#7-crear-y-radicar-una-solicitud)
8. [Reglas de validación del formulario](#8-reglas-de-validación-del-formulario)
9. [Mis solicitudes: seguimiento y correcciones](#9-mis-solicitudes-seguimiento-y-correcciones)
10. [Revisiones de contraparte](#10-revisiones-de-contraparte)

**Parte IV — Equipo ORI**
11. [Solicitudes recibidas](#11-solicitudes-recibidas)
12. [Aliados](#12-aliados)
13. [Consulta, tablero y detalle de convenios](#13-consulta-tablero-y-detalle-de-convenios)
14. [Elaboración del convenio](#14-elaboración-del-convenio)
15. [Revisión jurídica](#15-revisión-jurídica)
16. [Revisión de la contraparte](#16-revisión-de-la-contraparte)
17. [Revisión final y firmas](#17-revisión-final-y-firmas)
18. [Seguimiento del convenio formalizado](#18-seguimiento-del-convenio-formalizado)
19. [Renovaciones](#19-renovaciones)
20. [Reportes y estadísticas](#20-reportes-y-estadísticas)
21. [Administración: usuarios y bitácora](#21-administración-usuarios-y-bitácora)

**Parte V — Referencia**
22. [Acción Volver](#22-acción-volver)
23. [Uso con teclado y en celular](#23-uso-con-teclado-y-en-celular)
24. [Preguntas frecuentes](#24-preguntas-frecuentes)

---

# Parte I — Conceptos

## 1. Roles: quién puede hacer qué

Cada cuenta tiene un rol, y la plataforma solo muestra las opciones que ese rol tiene permitidas.

| Rol | Quién es | Qué puede hacer | Lea las secciones |
|---|---|---|---|
| **Solicitante interno** | Personal de la Universidad (correo `@usbcali.edu.co` o `@correo.usbcali.edu.co`). | Crear, guardar y radicar solicitudes; consultar las suyas; revisar las elaboraciones de convenio que la ORI le envíe. | 3 a 10, 22 a 24 |
| **Solicitante externo** | Persona de una entidad aliada (cualquier otro correo). | Lo mismo que el solicitante interno. | 3 a 10, 22 a 24 |
| **Gestor ORI** | Personal de la ORI que tramita los convenios. | Revisar solicitudes recibidas; gestionar aliados y convenios (elaboración, contraparte, revisión final, firmas, soportes, evaluación, renovaciones); ver reportes. | 3 a 5, 11 a 20, 22 a 24 |
| **Revisor ORI** | Oficina jurídica. | Consultar aliados y convenios; hacer la revisión y el aval jurídico. | 3 a 5, 12, 13, 15, 18, 22 a 24 |
| **Administrador ORI** | Responsable de la plataforma en la ORI. | Todo lo del Gestor ORI, más administrar usuarios y consultar la bitácora de cambios. | 3 a 5, 11 a 24 |

## 2. De la solicitud al convenio

### El recorrido completo

1. Un **solicitante** diligencia y **radica** una solicitud de convenio.
2. La **ORI** la revisa y puede **aprobarla**, **devolverla** para que se corrija o **rechazarla**.
3. Si la aprueba, el **Gestor ORI** inicia la **elaboración** del proyecto de convenio.
4. La oficina **jurídica** lo revisa y lo aprueba (aval jurídico) o lo devuelve con observaciones.
5. La **contraparte** revisa la versión enviada y la aprueba o la devuelve con observaciones.
6. La **ORI** hace la **revisión final** y lo aprueba para firmas.
7. Se registran las **siete firmas** obligatorias y la ORI **formaliza** el convenio, que pasa a **Vigente**.
8. Durante su vigencia se registran **actividades**, **soportes** y una **evaluación**; antes de vencer, se decide si se **renueva**.

Radicar una solicitud **no** significa que el convenio ya exista: solo inicia el trámite.

### Etapas del convenio

| # | Etapa | Responsable |
|---|---|---|
| 1 | Solicitud | Solicitante |
| 2 | Elaboración | Gestor ORI |
| 3 | Revisión y aval jurídico | Oficina jurídica |
| 4 | Revisión de contraparte | Contraparte |
| 5 | Revisión final | ORI |
| 6 | Aprobación y proceso de firmas | ORI |
| 7 | Firma, archivo y seguimiento | ORI |

### Estados de una solicitud

| Estado | Qué significa | ¿Se puede editar? |
|---|---|---|
| **Borrador** | Guardada, aún no presentada a la ORI. | Sí |
| **Radicada** | Presentada a la ORI, pendiente de revisión. | No |
| **En estudio** | La ORI la está revisando. | No |
| **Devuelta** | La ORI pidió correcciones. | Sí |
| **Aprobada** | La ORI la aceptó; puede iniciarse la elaboración del convenio. | No |
| **Rechazada** | La ORI no la aceptó. Se muestra el motivo. | No |

### Estados de un convenio

| Estado | Qué significa |
|---|---|
| **En trámite** | Todavía no se ha formalizado. |
| **Vigente** | Formalizado y dentro de su vigencia. |
| **Por vencer** | Vigente, pero cerca de su fecha de vencimiento. |
| **Vencido** | Pasó su fecha de vencimiento. |
| **Renovado** | Se renovó mediante un nuevo convenio. |
| **Finalizado** | Terminó y no continúa. |
| **Cancelado** | Se canceló antes de terminar. |

**Código del convenio.** Mientras está en trámite se identifica como **Convenio provisional #N**. Al formalizarse recibe su código institucional, con la forma `USB-ORI-AAAA-NNNNN`.

---

# Parte II — Para todos

## 3. Crear cuenta, ingresar y recuperar la contraseña

### Crear una cuenta (solicitantes)

Las cuentas del equipo ORI las crea el Administrador ORI. Los solicitantes crean la suya:

1. En la pantalla de ingreso, pulse **Crear cuenta**.
2. Escriba su **correo**. La plataforma decide el tipo de cuenta por el dominio:
   - `@usbcali.edu.co` o `@correo.usbcali.edu.co` → **solicitante interno**. Se le pide nombre completo, **unidad organizacional** y cargo.
   - Cualquier otro dominio → **solicitante externo**. Se le pide nombre completo, documento de identidad, **entidad externa** y cargo.
3. Defina su contraseña y pulse **Crear cuenta**.
4. Revise su correo y abra el **enlace de verificación**. Vence en **24 horas**. Si no le llegó o se venció, use **Reenviar correo de verificación**.

No podrá iniciar sesión hasta verificar el correo.

**Política de contraseñas:** al menos 8 caracteres, con una mayúscula, una minúscula, un número y un carácter especial.

### Iniciar sesión

En **Iniciar sesión** escriba su correo y contraseña y pulse **Ingresar**. Una cuenta inactiva no puede ingresar; en ese caso, comuníquese con la ORI.

### Recuperar la contraseña

1. En la pantalla de ingreso, pulse **Olvidé mi contraseña**.
2. Escriba su correo y pulse **Enviar instrucciones**.
3. Abra el enlace que le llega al correo. Vence en **30 minutos**.
4. Escriba la nueva contraseña (que cumpla la política y sea **distinta de la actual**) y pulse **Actualizar contraseña**.

### Cerrar sesión

Use **Cerrar sesión**, en el encabezado.

## 4. Navegación, Inicio y notificaciones

### El encabezado

Aparece en todas las pantallas después de iniciar sesión:

- **ORI Manager:** lleva a Inicio.
- **Menú de navegación:** las secciones que su rol tiene permitidas. La sección actual queda resaltada.
- **Ayuda** (solo solicitantes): vuelve a mostrar la guía de bienvenida (sección 6).
- **Campana:** abre el centro de notificaciones y muestra cuántos asuntos tiene pendientes.
- **Su correo y su rol.**
- **Cerrar sesión.**

### Opciones del menú

Cada persona ve solo las opciones de su rol:

| Opción | Lleva a | Quién la ve |
|---|---|---|
| Inicio | Página de Inicio | Todos |
| Aliados | Gestión de aliados (sección 12) | Equipo ORI |
| Solicitudes › Solicitudes recibidas | Bandeja de la ORI (sección 11) | Gestor y Administrador ORI |
| Solicitudes › Mis solicitudes | Sus solicitudes (sección 9) | Solicitantes |
| Convenios › Consulta de convenios | Búsqueda de convenios (sección 13) | Equipo ORI |
| Convenios › Tablero de convenios | Convenios por etapa (sección 13) | Equipo ORI |
| Convenios › Crear convenio manual | Convenio sin solicitud previa (sección 13) | Gestor y Administrador ORI |
| Convenios › Revisiones jurídicas | Bandeja jurídica (sección 15) | Revisor ORI |
| Renovaciones | Panel de renovaciones (sección 19) | Gestor y Administrador ORI |
| Reportes / Estadísticas | Reportes (sección 20) | Gestor y Administrador ORI |
| Administración › Usuarios / Bitácora | Sección 21 | Administrador ORI |

### Inicio

La página de Inicio muestra **accesos rápidos** a las tareas de su rol: Nueva solicitud, Mis solicitudes, Revisiones de contraparte, Solicitudes recibidas, Tablero de convenios, Revisiones jurídicas, Aliados o Usuarios y roles, según corresponda.

- Si tiene elaboraciones de convenio pendientes de revisar como contraparte, aparece un aviso con el número pendiente.
- El equipo ORI ve además **Próximos vencimientos**: convenios que vencen en los próximos 120 días, agrupados en rangos de 0–30, 31–60, 61–90 y 91–120 días, con un enlace a **Ver gestión de renovaciones**.

### Centro de notificaciones

Pulse la **campana** para ver sus avisos:

- **Avisos de actividad:** por ejemplo, que una solicitud suya fue devuelta.
- **Vencimientos próximos** (equipo ORI).

El número sobre la campana cuenta los asuntos pendientes de atender. Los avisos se actualizan solos mientras usa la plataforma; también puede pulsar **Actualizar avisos**.

## 5. Directorio público de convenios

Cualquier persona puede consultar los **convenios vigentes** sin iniciar sesión, desde el enlace **Consultar convenios vigentes** de la pantalla de ingreso. Se navega con **Anterior** y **Siguiente**.

---

# Parte III — Solicitantes

## 6. Guía de bienvenida

Es un recorrido corto que presenta la plataforma.

### Cuándo aparece

- **Se abre sola** la primera vez que entra a Inicio.
- Si la termina o la omite, ya no se abre sola.
- Para verla de nuevo, pulse **Ayuda** en el encabezado. Si está en otra pantalla, la plataforma lo lleva a Inicio para mostrarla; al terminar aparece **Volver a la pantalla anterior**.

### Qué explica

- Qué es ORI Manager y cómo es el proceso de un convenio.
- Que radicar una solicitud no es lo mismo que formalizar un convenio.
- Los accesos rápidos de Inicio, el menú, la campana de notificaciones y el botón Ayuda.

Algunos pasos solo aparecen si su cuenta tiene esa opción. Por ejemplo, Revisiones de contraparte solo se muestra a quien debe revisar convenios.

### Cómo moverse en el recorrido

| Acción | Botón | Teclado |
|---|---|---|
| Paso siguiente | **Siguiente** | Flecha derecha → |
| Paso anterior | **Anterior** | Flecha izquierda ← |
| Salir | **Omitir** o la **X** | **Esc** |
| Terminar | **Finalizar** (último paso) | — |

Cada paso indica en cuál va, por ejemplo "3 de 11". **La guía solo informa:** no crea, guarda ni radica nada.

## 7. Crear y radicar una solicitud

### Iniciar

Pulse **Nueva solicitud** en Inicio. Sus datos personales se precargan desde su perfil y se guardan como una copia en la solicitud.

### Secciones del formulario

Los campos marcados con `*` son obligatorios para radicar.

1. **Información del solicitante.**
   - Interno: nombre, Facultad o Dependencia, Programa académico o Unidad cuando aplique, y cargo.
   - Externo: nombre, tipo de documento, identificación, dígito de verificación si es NIT, y Empresa o Entidad.
2. **Información de la contraparte:** nombre, tipo de entidad, tipo y número de identificación, correo institucional, país, ciudad, teléfono y dirección. Si la entidad es una empresa, el sector económico es obligatorio.
3. **Contacto de contraparte:** nombre, cargo, teléfono y correo.
4. **Información del convenio:** tipo de convenio, tiempo estimado de vigencia, justificación, objeto, actividades de cada parte, metas esperadas, implicación financiera y requisitos para la renovación.
5. **Supervisor o encargado de ejecución USB:** nombre, cargo, teléfono y correo.
6. **Supervisor o encargado de ejecución de la contraparte:** nombre, cargo, teléfono y correo.
7. **Documentación:** elija el tipo de documento, seleccione el archivo y pulse **Adjuntar**.
   - Formatos PDF, JPG o PNG, de hasta **10 MB**.
   - Para radicar se necesita al menos un documento de **representación legal** de la contraparte: Cámara de Comercio, RUT, Cédula del representante legal u Otro documento de representación legal.
   - "Otro soporte" sirve como información complementaria, pero no los reemplaza.
   - Si la solicitud aún no está guardada, adjuntar un archivo guarda primero el borrador.
8. **Observaciones adicionales:** opcional.

### Ayuda dentro del formulario

Pulse **Ayuda: cómo diligenciar la solicitud**, en la parte superior del formulario, para ver una guía paso a paso.

- Recorre las ocho secciones y luego las acciones: adjuntar documentos, guardar borrador, radicar, cómo corregir errores, corregir una solicitud devuelta (solo si la suya está Devuelta) y consultar Mis solicitudes.
- Se adapta a su tipo de cuenta.
- **Nunca se abre sola** y **no modifica** el formulario: no escribe, no guarda, no adjunta, no radica y no borra lo que ya escribió.
- Se maneja igual que la guía de bienvenida (sección 6).
- No puede estar abierta al mismo tiempo que la guía de bienvenida: mientras una está abierta, el botón de la otra aparece desactivado.

### Guardar borrador y radicar

| | Guardar borrador | Radicar solicitud |
|---|---|---|
| ¿Para qué? | Conservar lo avanzado y seguir después. | Presentar formalmente la solicitud a la ORI. |
| ¿Exige todos los campos? | No. | Sí: todos los `*` y al menos un documento de representación legal. |
| ¿Revisa el formato? | Sí, de los campos llenos. | Sí, de todos. |
| Después | Sigue en **Borrador**, editable. | Pasa a **Radicada** y ya no se puede editar. |

Si al radicar falta algo o hay un dato inválido, la solicitud **no se radica**: sigue editable y los campos con problema quedan marcados.

## 8. Reglas de validación del formulario

El formulario revisa cada dato **cuando usted sale del campo**. Si hay un problema:

- El mensaje aparece **debajo del campo** y el campo queda marcado en rojo.
- **No se pierde nada de lo que escribió.** Corrija el dato y el mensaje desaparece.

La plataforma vuelve a revisar todo al guardar y al radicar. Si detecta algo que el formulario no vio (por ejemplo, un teléfono con formato correcto pero que no existe en ese país), muestra el error junto al campo.

### Identificación

Primero elija el **tipo de documento**; la regla depende de él.

| Tipo | Qué se acepta | Ejemplo |
|---|---|---|
| NIT | De 5 a 10 dígitos, **sin** el dígito de verificación. Puntos y espacios se ignoran. | `900123456` o `900.123.456` |
| Cédula de ciudadanía | De 5 a 10 dígitos. Puntos y espacios se ignoran. | `1.144.000.000` |
| Cédula de extranjería | De 3 a 15 letras o dígitos. | `E1234567` |
| Pasaporte | De 5 a 20 letras o dígitos. | `AB123456` |
| Identificación fiscal extranjera u Otro | De 3 a 40 caracteres: letras, dígitos, espacios, guion, punto o barra, con al menos una letra o dígito. | `B-12345678` |

### Dígito de verificación (solo NIT)

Al elegir NIT aparece un campo aparte, **Dígito de verificación**:

- Escriba **un solo dígito**.
- Debe coincidir con el NIT, según el cálculo oficial de la DIAN.
- No lo escriba pegado al NIT (por ejemplo, `900123456-8`).

### Teléfonos

Aplica a los cuatro teléfonos del formulario.

- **Colombia:** sin indicativo, por ejemplo `602 555 1234` o `310 123 4567`.
- **Otro país:** con `+` y el indicativo, por ejemplo `+34 912 345 678`.
- Se permiten espacios, paréntesis, puntos y guiones.
- **Extensión:** `ext`, `extensión` o `x` seguido de 1 a 6 dígitos, por ejemplo `602 555 1234 ext 123`.
- No se aceptan letras en el número.

### País y ciudad

- El **país** se elige de la lista.
- La **ciudad** se escribe a mano: de 2 a 120 caracteres, empieza con una letra y solo admite letras, espacios, guion, punto o apóstrofo.

La plataforma **no comprueba** que la ciudad pertenezca al país.

### Dirección

- De 5 a 200 caracteres, con al menos una letra.
- Debe tener **un número**, **o** al menos dos referencias separadas por coma o barra.
- Signos permitidos: `# - . , / ° º ( ) '`.

Ejemplos válidos:

- `Calle 5 # 38-25`
- `Cra. 122 No. 6-65, Pance`
- `Vereda La Esperanza, Finca El Roble`
- `Km 3 vía Cali/Jamundí`
- `1600 Amphitheatre Pkwy`

"Campus universitario" solo no basta; escriba, por ejemplo, "Campus universitario, Pance". Un formato válido no significa que la plataforma haya comprobado que el lugar existe.

## 9. Mis solicitudes: seguimiento y correcciones

En **Mis solicitudes** está la lista de sus borradores y solicitudes radicadas, con consecutivo, contraparte, tipo de convenio, fecha de radicación y estado. Puede filtrar por estado.

- **Abrir una solicitud:** si está en Borrador o Devuelta, puede seguir editándola. En otro estado solo se consulta.
- **Historial:** muestra cada radicación y, si fue devuelta, las observaciones de esa devolución.
- **Solicitud devuelta:**
  1. Lea las **Observaciones de devolución ORI**, al comienzo de la solicitud.
  2. Corrija los datos y documentos indicados.
  3. Pulse **Guardar cambios** y después **Volver a radicar**.
- **Solicitud rechazada:** se muestra el **Motivo del rechazo ORI**.

## 10. Revisiones de contraparte

Si la ORI le envía la elaboración de un convenio para que la revise como solicitante, aparece en **Revisiones de contraparte** (en Inicio y en el aviso de pendientes).

1. Pulse **Revisar** en la elaboración pendiente.
2. Lea la versión enviada. Es exactamente la que se remitió para su decisión.
3. Elija una opción:
   - **Aprobar elaboración**.
   - **Devolver con observaciones:** debe escribir al menos una observación.

---

# Parte IV — Equipo ORI

## 11. Solicitudes recibidas

**Menú › Solicitudes › Solicitudes recibidas** muestra las solicitudes radicadas ante la ORI, con consecutivo, solicitante (interno o externo), contraparte, tipo de convenio, fecha de radicación, estado de la solicitud y, cuando existe, etapa y estado del convenio. Puede buscar y filtrar.

Pulse **Ver** para abrir una solicitud. Allí encuentra:

- Información del solicitante, contraparte propuesta y contacto, convenio solicitado y supervisores.
- **Documentos adjuntos**, con **Previsualizar** para los PDF.
- **Ver historial:** cada radicación y la opción **Comparar con la versión anterior**, que muestra qué cambió entre una radicación y otra.

### Decidir sobre una solicitud

Si la solicitud está Radicada o En estudio:

| Acción | Qué hace |
|---|---|
| **Aprobar** | Pide confirmación y deja la solicitud **Aprobada**. Aprobar **no** crea el convenio. |
| **Devolver** | Exige **Observaciones de devolución**. La solicitud vuelve al solicitante para que la corrija (**Confirmar devolución**). |
| **Rechazar** | Exige el **Motivo del rechazo**, que el solicitante podrá ver (**Confirmar rechazo**). |

Con la solicitud aprobada, pulse **Iniciar elaboración** para crear el convenio y abrir su elaboración. Si el convenio ya existe, el botón es **Ver convenio**.

## 12. Aliados

Un aliado es la entidad con la que la Universidad firma convenios. Cada entidad tiene un único registro, identificado por su NIT o documento.

- **Menú › Aliados:** lista con buscador por nombre o NIT/documento, y filtros por tipo, país y estado. Pulse **Ver perfil** para abrir uno.
- **Perfil del aliado:** información de la entidad y **Convenios asociados**, en cualquier estado.
- **Editar datos** (Gestor y Administrador): actualiza la información del aliado.
- **Inactivar / Reactivar** (Gestor y Administrador): no se puede inactivar un aliado que tenga convenios vigentes.

El Revisor ORI puede consultar aliados, pero no modificarlos.

## 13. Consulta, tablero y detalle de convenios

### Consulta de convenios

**Menú › Convenios › Consulta de convenios.** Muestra código, objeto, contraparte, tipo, estado, etapa, vigencia y formalización.

- Tiene buscador y filtros por fecha (**Desde** y **Hasta**).
- **Más filtros** agrega estado, tipo de contraparte y alcance (institucional o por programa).
- **Ver historial** abre la trazabilidad de un convenio.

### Tablero de convenios

**Menú › Convenios › Tablero de convenios.** Muestra los convenios en trámite agrupados por etapa, con contraparte y responsable. Pulse **Ver detalle** para abrir uno. La etapa avanza según el trámite; no se cambia a mano.

### Crear convenio manual

**Menú › Convenios › Crear convenio manual** (Gestor y Administrador) sirve para registrar un convenio que no viene de una solicitud.

1. Complete los datos iniciales. El aliado se puede elegir ahora o **Asociar más adelante**.
2. Pulse **Crear y abrir editor**.

### Detalle del convenio

Tiene dos pestañas: **Resumen** e **Historial**. Según la etapa y su rol, el Resumen muestra:

- Información base y documentos asociados.
- **Contraparte:** si quedó **Por definir**, el Gestor puede **Asignar contraparte** o **Corregir contraparte** eligiendo un aliado activo.
- Las secciones de la etapa actual: elaboración, revisión jurídica, revisión de contraparte, revisión final o firmas (secciones 14 a 17).
- Para convenios formalizados: línea de tiempo, soportes, actividades, evaluación y renovación (secciones 18 y 19).
- **Exportar / Generar Documento:**
  - Mientras está en trámite: un **documento de trabajo**, sin código oficial ni firmas.
  - Al estar formalizado: el **documento oficial**, con membrete y firmas.

## 14. Elaboración del convenio

Desde el detalle, pulse **Continuar elaboración**. Allí el Gestor ORI prepara el **proyecto de convenio**:

- **Datos clave del convenio:** tipo, alcance (institucional o por programa), fechas, implicación financiera, entre otros.
- **Documento jurídico:** el texto del convenio. Al empezar puede elegir **Usar información de la solicitud como base** o **Empezar documento contractual limpio**. Si cambia esa elección después, la plataforma pide **Confirmar reemplazo del documento**.
- **Guardar avance:** guarda el borrador sin crear una versión formal. Se indica si cambió el documento, los metadatos o ambos.
- **Observaciones pendientes:** las observaciones jurídicas, de contraparte o de revisión final se listan aquí. Las que **Obligan a corregir** deben atenderse; márquelas con **Marcar como atendida**.
- **Historial de versiones:** solo incluye versiones formales. Guardar avances no agrega versiones.
- **Continuar trámite:** envía el proyecto a la siguiente etapa. La plataforma verifica primero que no falte información obligatoria.

## 15. Revisión jurídica

Para el **Revisor ORI**.

1. **Menú › Convenios › Revisiones jurídicas** muestra los convenios pendientes de revisión y aval jurídico. Tiene buscador y filtros por tipo y responsable, que se conservan al volver o recargar la página.
2. Pulse **Revisar** para abrir el convenio.
3. Registre observaciones con **Nueva observación** e indique si **Obliga a corregir** o **No obliga a corregir**.
4. Decida:
   - **Aprobar revisión:** da el aval jurídico y el convenio pasa a la revisión de contraparte.
   - **Devolver a Elaboración:** el Gestor debe atender las observaciones y reenviar.

Cada ronda de revisión queda registrada. En **Observaciones jurídicas** se ve quién hizo cada observación, en qué revisión y cómo se atendió.

## 16. Revisión de la contraparte

Con el aval jurídico, el convenio pasa a revisión de la contraparte.

**Para el Gestor ORI (desde el detalle del convenio):**

- Cuando la versión está **Lista para envío**, se envía al aliado por correo con un enlace seguro.
- **Reenviar enlace al aliado** vuelve a mandar el enlace si hace falta.
- Si el solicitante debe revisarla, le aparece en sus **Revisiones de contraparte** (sección 10).

**Para la contraparte externa (desde el enlace del correo, sin iniciar sesión):**

1. Consulte la versión recibida. Es de solo lectura.
2. Elija una opción:
   - **Firmar y aprobar:** escriba nombre y cargo del firmante y firme en el recuadro.
   - **Devolver con observaciones:** escríbalas y pulse **Confirmar devolución**.

Si la contraparte devuelve el convenio, sus observaciones aparecen en la elaboración para que el Gestor las atienda y lo reenvíe.

## 17. Revisión final y firmas

### Revisión final ORI

La ORI verifica que la versión definitiva cumpla las condiciones:

- **Aprobar para firmas:** fija la versión que se firmará.
- **Devolver con observaciones:** exige una **Observación**, y el convenio vuelve a **Elaboración**.

### Proceso de firmas

Un convenio necesita **siete firmas obligatorias**:

1. Administrador ORI.
2. Revisor ORI.
3. Vicerrectoría Financiera.
4. Vicerrectoría Académica.
5. Secretaría.
6. Rector.
7. Parte solicitante.

Pasos:

1. Pulse **Iniciar proceso de firmas**. La versión aprobada queda protegida y ya no puede modificarse.
2. Registre cada firmante (nombre y cargo) con **Guardar firmante** y elija la **modalidad**:
   - **Electrónica:** pulse **Enviar invitaciones electrónicas**. Cada firmante recibe un enlace, revisa la versión y firma personalmente. Si un enlace no llegó, use **Reenviar enlace**.
   - **Física:** pulse **Registrar firma física** y cargue el **documento firmado (PDF)** con la **fecha de firma**. Un mismo documento puede incluir varias firmas físicas.
3. Siga el avance en **Proceso de firmas** hasta que aparezca **Todas las firmas obligatorias han sido registradas**.
4. Pulse **Formalizar convenio** y confirme. Esa versión queda como la versión contractual definitiva, el convenio pasa a **Vigente** y recibe su código institucional.

El **Documento aprobado para firma** se puede consultar desde el detalle del convenio.

## 18. Seguimiento del convenio formalizado

Desde el detalle de un convenio formalizado:

- **Línea de tiempo:** hitos de inicio de elaboración, activación y vencimiento, cada uno marcado como completado, pendiente, futuro o vencido.
- **Documentos de soporte:** PDF que respaldan la ejecución. Se cargan con **Cargar documento soporte (PDF)** y se pueden previsualizar o descargar.
- **Actividades de utilización:** actividades realizadas que evidencian el uso del convenio. Para cada una se registra actividad, descripción, fecha, responsable y observaciones opcionales, y se guarda con **Registrar actividad**.
- **Evaluación del convenio:** si fue funcional, una calificación de cumplimiento y comentarios sobre la experiencia (**Registrar evaluación**).
- **Historial:** pestaña **Historial**, con revisiones, observaciones, cambios de etapa y versiones formales. Cada versión anterior se abre en **solo lectura**.

## 19. Renovaciones

**Menú › Renovaciones** (Gestor y Administrador) lista los convenios próximos a vencer con su estado de seguimiento:

- **Pendiente de decisión.**
- **Renovación iniciada:** con **Ver renovación** se abre el nuevo convenio.
- **No se renovará:** se pide confirmar la decisión.

Pulse **Iniciar renovación** para crear una nueva elaboración a partir del convenio original. Un convenio finalizado también puede renovarse desde su detalle, si tiene fecha de vencimiento y una versión documental válida.

## 20. Reportes y estadísticas

- **Menú › Reportes — Reporte de convenios activos:**
  - Lista de convenios activos con aliado, tipo, unidad, vigencia y actividades registradas.
  - **Descargar PDF** o **Descargar Excel**.
- **Menú › Estadísticas — Reporte estadístico de convenios:**
  - Gráficos de convenios por categoría, con filtros.
  - **Ver tabla de datos** muestra los números de cada gráfico.
  - **Descargar PDF** o **Descargar Excel**.

## 21. Administración: usuarios y bitácora

Solo para el **Administrador ORI**.

### Usuarios

**Menú › Administración › Usuarios** lista las cuentas con nombre, correo, tipo (interno o externo), rol y estado.

- Pulse **Gestionar** para editar los datos de un usuario, **cambiar su rol** o **activarlo o desactivarlo**. Un usuario inactivo no puede iniciar sesión.
- Las cuentas del equipo ORI se crean con **Nuevo usuario**.
- La contraseña de los solicitantes no se cambia aquí: ellos la restablecen con **Olvidé mi contraseña**.

### Bitácora de cambios

**Menú › Administración › Bitácora** muestra **quién, cuándo y qué** cambió en la plataforma: fecha y hora, responsable (una persona o un **proceso automático**), acción, registro afectado, y valor anterior y nuevo.

Se puede filtrar por entidad, fechas (**Desde** y **Hasta**), usuario o número de registro, y ordenar por más recientes o más antiguos.

---

# Parte V — Referencia

## 22. Acción Volver

En las pantallas de convenios (detalle, elaboración, historial, versiones anteriores y documento aprobado para firma) hay un botón **Volver** al principio de la pantalla.

- Lo regresa a la pantalla de la que vino, aunque haya pasado por varias. Por ejemplo, Renovaciones → Detalle → Elaboración: desde Elaboración vuelve al Detalle, y desde el Detalle vuelve a Renovaciones.
- Los filtros de **Revisiones jurídicas** quedan en la dirección de la página, así que se conservan al volver, recargar o compartir el enlace.
- Si abrió la pantalla directamente (por ejemplo, desde un enlace), Volver lo lleva a una pantalla de partida según su rol, como el Tablero o la Consulta de convenios.

## 23. Uso con teclado y en celular

### En celular o tablet

- El menú se recoge en un botón con tres rayas (☰). Púlselo para abrirlo o cerrarlo.
- El menú también se cierra al elegir una opción, al pulsar fuera de él o con **Esc**.
- Su correo, su rol, la campana y Cerrar sesión siguen visibles en cualquier tamaño de pantalla.

### Con teclado

- **Tab** recorre los enlaces, botones y campos.
- **Enter** abre un enlace o despliega un grupo del menú.
- **Esc** cierra el menú, el panel de notificaciones o una guía, y devuelve el foco al botón que la abrió.
- En las guías: **flecha derecha** avanza y **flecha izquierda** retrocede.
- Los errores del formulario quedan asociados a su campo, para que los anuncien los lectores de pantalla.

## 24. Preguntas frecuentes

**No puedo iniciar sesión después de crear mi cuenta.**
Primero debe verificar su correo con el enlace que le llegó (vence en 24 horas). Si se venció, use **Reenviar correo de verificación**.

**El enlace para restablecer la contraseña dice "Enlace expirado".**
Ese enlace dura 30 minutos. Pida otro con **Olvidé mi contraseña**.

**Me registré como externo, pero soy de la Universidad.**
El tipo de cuenta depende del dominio del correo. Use su correo `@usbcali.edu.co` o `@correo.usbcali.edu.co`.

**No veo una opción del menú que necesito.**
El menú depende de su rol. Si cree que su rol no es el correcto, comuníquese con el Administrador ORI.

**La guía de bienvenida no se abrió sola.**
Solo se abre la primera vez que entra a Inicio. Use **Ayuda**.

**Aparece "No se pudo consultar (o guardar) el estado de la guía".**
Puede seguir usando la plataforma. Pulse el botón **Reintentar** que aparece junto al mensaje.

**El botón de una guía está desactivado.**
Hay otra guía abierta. Ciérrela con **Omitir**, la **X** o **Esc**.

**Las flechas no cambian el paso de la guía.**
Espere a que termine la animación del paso (menos de medio segundo) y vuelva a intentarlo.

**Me dice que el dígito de verificación no es correcto.**
El NIT va sin el dígito, y el dígito en su propio campo. Revise ambos.

**Mi teléfono internacional no se acepta.**
Escríbalo con `+` y el indicativo del país. Sin `+`, se interpreta como número de Colombia.

**No puedo radicar.**
Revise los campos en rojo y los marcados con `*`, y confirme que adjuntó al menos un documento de representación legal de la contraparte.

**No puedo editar mi solicitud.**
Solo se editan las solicitudes en **Borrador** o **Devuelta**. Una radicada ya está en manos de la ORI.

**La ORI aprobó mi solicitud, pero no veo el convenio.**
Aprobar la solicitud no crea el convenio. La ORI inicia la elaboración después, y el convenio sigue las etapas de la sección 2.

**No puedo inactivar un aliado.**
Tiene convenios vigentes. Solo se inactivan aliados sin convenios vigentes.

**¿Por qué el convenio dice "Convenio provisional"?**
Todavía no se ha formalizado. El código institucional se asigna al formalizarlo, después de completar las firmas.
