# Prompt inicial — Google Antigravity — ORI Manager

Estoy trabajando en **ORI Manager**.

Debes seguir las instrucciones del `AGENTS.md` disponible en la raíz del proyecto y utilizar las Skills de `.agents/skills/` cuando sean pertinentes.

Para esta tarea, la fuente de verdad funcional es la Historia de Usuario, tarea y criterios de aceptación que proporcionaré a continuación.

Antes de modificar archivos:

1. revisa completamente la tarea y sus criterios;
2. revisa el estado relevante del repositorio;
3. identifica decisiones funcionales faltantes o contradicciones;
4. no amplíes el alcance;
5. no agregues dependencias sin justificarlo y solicitar aprobación;
6. no ejecutes operaciones destructivas;
7. no hagas commit, push, PR, merge o despliegues sin autorización explícita;
8. si el cambio no es trivial, presenta primero un plan breve.

Al finalizar, informa:

- cambios realizados;
- archivos modificados;
- pruebas ejecutadas;
- resultados;
- criterios cubiertos;
- riesgos;
- pendientes;
- acciones humanas necesarias.

## TAREA 1: Modelado y persistencia de documentos de soporte

**Descripción:** Diseñar la entidad o tabla para almacenar la metadata de los documentos adjuntos y su relación con el convenio.

Detalle técnico:

- Crear la tabla/entidad convenio_documento con los campos: id, convenio_id (FK a convenio), nombre_original, storage_path (o URI del storage), tamano_bytes, mime_type, usuario_creacion_id, fecha_creacion
- Configurar la migración de base de datos (Flyway, Liquibase, TypeORM, Prisma, etc.)
- Establecer la relación 1:N entre Convenio y ConvenioDocumento.

## TAREA 2: Endpoint de subida de archivo y validación de seguridad (CA-01, CA-02)

**Descripción:** Implementar el servicio REST que recibe el archivo multipart, lo valida, lo sube al almacenamiento (S3/Azure Blob/Local) y guarda su metadata

Detalle técnico:

- Crear endpoint POST /api/v1/convenios/{id}/documentos.
- Validación de extensión y MIME: Comprobar no solo la extensión .pdf, sino también el "Magic Number" o encabezado binario del archivo para evitar inyecciones (%PDF- / application/pdf). Si no es válido, responder 400 Bad Request con mensaje "Solo se permiten documentos en formato PDF”.
- Límite de tamaño: Definir límite por archivo (ejemplo: máximo 10 MB o 20 MB). Si supera, responder 413 Payload Too Large.
- Almacenamiento: Guardar el archivo con un UUID o hash único para evitar colisiones de nombres (uuid.pdf), manteniendo el nombre original solo en la base de datos

## TAREA 3: Interfaz y lógica del componente de carga de archivo (CA-01, CA-02)

Descripción: Construir el modal o sección interactiva dentro del detalle del convenio para seleccionar y subir el archivo PDF.

Detalle técnico:

Crear componente con zona de arrastrar y soltar (Drag & Drop) y botón estándar de explorador de archivos.

Atributo nativo accept=".pdf,application/pdf".

Validación en cliente: Comprobar tamaño y extensión antes de enviar la petición. Si el usuario intenta subir otro tipo de archivo (ej. .docx, .jpg), mostrar alerta en pantalla: "Solo se permiten documentos en formato PDF", impidiendo el envío.

Mostrar barra de progreso o spinner de carga y deshabilitar el botón de subida mientras la petición esté en curso para evitar dobles envíos.

Manejo de notificaciones de éxito (toast "Documento cargado correctamente") y captura de errores del servidor.

Criterio de finalización (DoD): El usuario puede seleccionar un PDF válido, ver el estado de carga y recibir confirmación visual inmediata.


## DATO IMPORTANTE: AlGUNOS CRITERIOS NO ESTA AUN RELACIONADOS CON LA TAREAS ACTUALES, IGUAL TE LOS DEJO PARA QUE LOS TENGAS EN CUENTA
## CRITERIOS DE ACEPTACIÓN
 

Descripción:
Como Gestor ORI o Administrador ORI, quiero adjuntar documentos de soporte en formato PDF a un convenio activo, para mantener centralizada y actualizada la documentación generada durante su vigencia.

---

## Criterios de aceptación

---

### CA-01 — Adjuntar documento PDF

**Scenario:** Cargar un documento de soporte

**Given** que el usuario está autorizado para gestionar el convenio

**When** selecciona un archivo PDF y confirma la carga

**Then** el sistema debe asociar el documento al convenio correspondiente.

### CA-02 — Validar formato

**Scenario:** Intentar cargar un archivo no permitido

**Given** que el usuario intenta adjuntar un archivo que no es PDF

**When** confirma la carga

**Then** el sistema debe rechazar el archivo

**And** debe informar que solo se permiten documentos PDF.

### CA-03 — Conservar información del documento

**Scenario:** Consultar un documento cargado

**Given** que existe un documento adjunto

**When** el usuario consulta los documentos del convenio

**Then** debe poder identificar el archivo asociado al convenio.

### CA-04 — Controlar permisos

**Scenario:** Usuario sin autorización intenta cargar un documento

**Given** que el usuario no tiene permisos sobre el convenio

**When** intenta adjuntar un archivo

**Then** el sistema debe impedir la operación.