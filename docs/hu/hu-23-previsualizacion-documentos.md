# HU-23 — Previsualizar documentos adjuntos

## 1. Objetivo y relación con otras historias

El objetivo de **HU-23** es permitir a los usuarios internos autorizados de la ORI previsualizar documentos adjuntos directamente desde la interfaz web de ORI Manager, facilitando la consulta ágil de su contenido sin tener que descargarlos previamente al almacenamiento local ni abandonar su flujo de trabajo.

### Relación y dependencias
- **HU-11 (Radicación y gestión de solicitudes):** Provee la estructura y almacenamiento de documentos adjuntos asociados a las solicitudes radicadas (`Documento` con tipos como `CAMARA_COMERCIO`, `RUT`, `CEDULA_REPRESENTANTE_LEGAL`, etc.).
- **HU-22 (Carga y gestión de documentos de soporte de convenios):** Provee la carga y consulta de documentos de soporte en formato PDF para convenios en trámite o activos.
- **HU-23** se apoya en los modelos, almacenamiento y endpoints existentes introducidos por HU-11 y HU-22, incorporando la capacidad de previsualización interactiva y el parámetro de disposición en la entrega HTTP.

---

## 2. Alcance funcional del MVP

- **Formato admitido para previsualización:** Únicamente archivos de tipo **PDF** (`application/pdf`, `application/x-pdf` o con firma mágica `%PDF-`).
- **Otros formatos (ej. `.xlsx`, `.docx`, imágenes):** No se previsualizan interactivamente en este MVP; se informa al usuario mediante un estado amigable de formato no compatible y se conserva la acción de descarga directa autenticada.
- **Modo de visualización:** Estrictamente de **solo lectura**. La previsualización no altera, versiona ni edita el archivo en el almacenamiento.
- **Modal interactivo:** El visualizador se despliega dentro de un diálogo modal accesible sin redirigir al usuario ni alterar su estado de navegación.

---

## 3. Componentes y pantallas integradas

### Componente principal
- `frontend/src/components/DocumentoPreviewModal.tsx`: Componente reutilizable implementado sobre el elemento nativo `<dialog>`, accesible mediante teclado (<kbd>Esc</kbd>), con identificación del documento, gestión segura del foco y limpieza de memoria (`URL.revokeObjectURL`).

### Pantallas integradas
1. **Soportes de convenios (`SoportesConvenio.tsx`):**
   - El botón «Ver» de cada documento de soporte abre el modal de previsualización sin recargar la página. Conserva el botón «Descargar» autenticado.
2. **Solicitudes recibidas (`SolicitudRecibidaPage.tsx`):**
   - En la sección «Documentos adjuntos», cada documento cuenta con la acción «Previsualizar» para abrir el modal, y el botón «Descargar».
3. **Detalle de convenio / Revisión jurídica (`ConvenioDetallePage.tsx`):**
   - En la sección «Documentos asociados» durante la etapa `REVISION_AVAL_JURIDICO`, la acción «Ver» abre el modal de previsualización para el Revisor ORI.
4. **Revisión final del convenio (`RevisionFinalConvenio.tsx`):**
   - En la sección «Documentos asociados», la acción «Ver» abre el modal de previsualización.

---

## 4. Criterios de aceptación (CA)

| Criterio | Descripción y comportamiento implementado |
|---|---|
| **CA-01 — Iniciar la previsualización** | Al seleccionar «Previsualizar» o «Ver» en un documento PDF, se abre el modal dentro de ORI Manager sin descargar previamente ni abandonar la página. |
| **CA-02 — Mostrar el documento seleccionado** | Renderiza el PDF en un `<iframe>` de solo lectura y presenta el nombre del archivo en la cabecera del visor. |
| **CA-03 — Cerrar y regresar al contexto** | Al cerrar (vía botón «×», botón «Cerrar» o tecla <kbd>Esc</kbd>), regresa a la pantalla y sección original, restaurando el foco y conservando el estado. |
| **CA-04 — Conservar la descarga** | La opción de descarga autenticada permanece disponible tanto en las listas documentales como en el interior del modal (`disposicion=attachment`). |
| **CA-05 — Respetar permisos y alcance** | El backend valida la sesión, los permisos y la relación del documento con la solicitud o convenio autorizado, bloqueando accesos cruzados con `403 Forbidden` y no exponiendo rutas internas ni URLs públicas. |
| **CA-06 — Manejar archivos no compatibles** | Si el archivo no es un PDF válido (o su tipo MIME es incompatible), el sistema muestra un mensaje informativo y ofrece descarga directa cuando el usuario tenga autorización. |
| **CA-07 — Manejar errores de consulta** | Informa con claridad problemas de autenticación (401), permisos (403), documento inexistente o no vigente (404), fallos de almacenamiento (502) o error de red, permitiendo reintentar. |
| **CA-08 — Integración y accesibilidad** | Componente con atributos WAI-ARIA (`aria-modal="true"`, `aria-labelledby`), soporte completo de teclado, diseño responsivo para móviles y escritorio, y sin efectos de modificación sobre los documentos. |

---

## 5. Reglas de negocio

- **RN-01:** El MVP de HU-23 previsualiza exclusivamente archivos PDF.
- **RN-02:** Se reutilizan la entidad `Documento`, el almacenamiento físico/S3 y los endpoints documentales existentes.
- **RN-03:** La previsualización no reemplaza la descarga ni modifica el archivo.
- **RN-04:** El acceso a los documentos depende estrictamente de los permisos y del alcance operativo asignado a cada usuario.
- **RN-05:** El rol Revisor ORI solo accede a los documentos de convenios para los que tenga autorización expresa; HU-23 no le concede acceso general a solicitudes recibidas ni a la gestión de soportes.
- **RN-06:** Los archivos se entregan mediante endpoints autenticados con cookies de sesión seguras, sin generar enlaces públicos ni exponer rutas de almacenamiento.
- **RN-07:** Se impiden accesos por manipulación de identificadores (IDOR) y se evitan cachés compartidas de contenido sensible mediante cabeceras `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`.
- **RN-08:** Los formatos no compatibles conservan la consulta de metadatos y la descarga cuando el usuario tenga permiso.
- **RN-09:** La consulta es de solo lectura y no produce registros en el historial de versiones ni mutaciones en la entidad.

---

## 6. Roles autorizados y restricciones

| Rol | Alcance sobre HU-23 |
|---|---|
| **Administrador ORI** | Acceso general a previsualizar y descargar documentos de solicitudes y convenios dentro de su alcance. |
| **Gestor ORI** | Acceso a previsualizar y descargar documentos de solicitudes recibidas y convenios asignados. |
| **Revisor ORI** | **Restricción específica (RN-05):** Únicamente puede previsualizar documentos de los convenios asignados en etapa de revisión jurídica. No tiene acceso a solicitudes recibidas ni a la carga/gestión de soportes. |
| **Solicitante Interno / Externo** | No acceden a la previsualización interna de la bandeja ORI; sus accesos se limitan estrictamente a sus solicitudes propias según HU-11. |
| **Usuario anónimo** | Sin acceso (retorna `401 Unauthorized`). |

---

## 7. Endpoints documentales utilizados

Los endpoints existentes fueron fortalecidos para admitir el parámetro de consulta `disposicion`:

1. **Documentos de Convenios:**
   - `GET /api/convenios/{convenio_id}/documentos/{documento_id}/contenido?disposicion={inline|attachment}`
   - `GET /api/convenios/{convenio_id}/documentos/{documento_id}/descargar?disposicion={inline|attachment}`
2. **Documentos de Solicitudes Recibidas:**
   - `GET /api/solicitudes/recibidas/{solicitud_id}/documentos/{documento_id}/contenido?disposicion={inline|attachment}`

### Parámetros y cabeceras
- `disposicion=inline`: Indica al navegador o cliente que el contenido está destinado a visualización directa.
- `disposicion=attachment`: Fuerza la descarga del archivo como adjunto.
- Cabeceras de seguridad incorporadas:
  - `Content-Disposition: inline; filename*=UTF-8''...` o `attachment; filename*=UTF-8''...`
  - `X-Content-Type-Options: nosniff`
  - `Cache-Control: no-store`

---

## 8. Mecanismo de entrega autenticada y seguridad

1. La petición se realiza desde el cliente mediante `apiFetchArchivo`, que incluye las credenciales de sesión (`credentials: 'include'`).
2. El backend verifica la sesión activa, los permisos del rol y la relación del documento con la solicitud o convenio.
3. El archivo se transmite como flujo binario (`StreamingResponse` / `FileResponse`) con su tipo MIME correspondiente.
4. En el frontend, el blob recibido se verifica:
   - Se valida que el tipo MIME no sea incompatible (ej. `text/html`, imágenes, etc.).
   - Se inspecciona la firma mágica del contenido binario (`%PDF-`).
   - Solo tras validar el formato se genera una URL temporal local mediante `URL.createObjectURL(blob)`.
   - Al cerrar el diálogo o desmontar el componente, se ejecuta `URL.revokeObjectURL` para liberar la memoria.

---

## 9. Tratamiento de formatos incompatibles y errores

- **Extensión o MIME no PDF:** El componente detecta antes de la petición si el MIME explícito o la extensión corresponden a formatos incompatibles. No realiza peticiones innecesarias y muestra el estado `preview-no-compatible`.
- **Respuesta no PDF (ej. HTML por error o MIME incorrecto):** Si el servidor retorna un tipo distinto o el contenido carece de la firma `%PDF-`, el visualizador rechaza renderizarlo en el iframe y activa el estado de incompatibilidad.
- **Sesión expirada (401):** Mensaje claro indicando la necesidad de reiniciar sesión.
- **Permiso denegado (403):** Mensaje informando que el usuario no tiene autorización para consultar el documento.
- **Documento no encontrado o no vigente (404):** Mensaje indicando que el archivo no existe o no está activo.
- **Error de almacenamiento (502):** Mensaje amigable con botón «Reintentar».

---

## 10. Pruebas y validaciones ejecutadas

### Frontend
- `frontend/src/components/DocumentoPreviewModal.test.tsx` (19 tests):
  - Carga y renderizado de PDF en iframe.
  - Cierre y restauración accesible del foco.
  - Formato no compatible inicial (ej. `.xlsx`, `.pdf` con MIME `image/png` o `image/jpeg`).
  - Validación post-descarga (respuesta `text/html` o contenido corrupto sin `%PDF-`).
  - Errores HTTP 401, 403, 404, 502 y errores de red con reintento.
  - Comprobación de `puedeDescargar={false}`.
  - Cierre mediante evento `cancel` (tecla Escape).
  - Limpieza de `blobUrl` al desmontar.
- `frontend/src/components/SoportesConvenio.test.tsx` (9 tests): Integración en soportes y permisos.
- `frontend/src/pages/SolicitudRecibidaPage.test.tsx` (14 tests): Integración en solicitudes recibidas.
- `frontend/src/pages/ConvenioDetallePage.test.tsx` (6 tests): Integración en revisión jurídica por Revisor ORI.
- `frontend/src/components/RevisionFinalConvenio.test.tsx` (2 tests): Integración en revisión final.
- **Total Frontend:** 54 pruebas unitarias e integrales aprobadas.

### Backend
- `backend/tests/test_hu23_previsualizacion_documentos.py` (21 tests):
  - Parámetro `disposicion=inline` y `disposicion=attachment`.
  - Validación de cabeceras seguras (`X-Content-Type-Options`, `Cache-Control`).
  - Validación de permisos por rol (Gestor ORI, Revisor ORI, Solicitante).
  - Casos 401, 403, 404 y protección contra IDOR.

---

## 11. Limitaciones conocidas y validaciones de QA

1. **Formatos no PDF:** Las hojas de cálculo (`.xlsx`) y documentos Word (`.docx`) no cuentan con visor integrado en el MVP; requieren ser descargados para su consulta.
2. **Validación en dispositivos reales:** Aunque el diseño cuenta con adaptaciones CSS responsivas (`max-width: 640px`), la experiencia visual en navegadores móviles específicos debe ser certificada por el equipo de QA en el entorno de Staging.
3. **Estado de aceptación:** El paso de las pruebas automatizadas y del CI no constituye por sí solo la aprobación definitiva de la historia; esta requiere la validación funcional del Product Owner y QA.

---

## 12. Seguridad, compatibilidad y reversión

- **Seguridad:** No se publican enlaces directos al almacenamiento ni se generan tokens públicos. Se previene la inyección de contenidos externos en iframes mediante validación de firma PDF y MIME.
- **Compatibilidad:** Todos los cambios en endpoints conservan compatibilidad hacia atrás con los clientes que no envíen el parámetro `disposicion` (asumiendo `inline` por defecto o manteniendo el flujo previo).
- **Reversión:** Los cambios se limitan a componentes de presentación en frontend y parámetros opcionales en routers de FastAPI, sin modificaciones en el esquema de base de datos (`ALTER TABLE`), por lo que una reversión de código no requiere migraciones de esquema inversas.
