# Lote 1 — Auditoría visual de detalles

Auditoría previa a implementación sobre `origin/develop` (`f352c94`). Rutas contrastadas con `frontend/src/app/router.tsx`; búsqueda transversal de dl/dt/dd, etiquetas, resúmenes y tarjetas en páginas y componentes. Directorio, tablas y adaptación de revisiones jurídicas quedan fuera de alcance.

| Archivo / ruta o contexto | Problema identificado | Acción aplicada |
|---|---|---|
| SolicitudRecibidaPage.tsx — /ori/solicitudes/:solicitudId | Grilla de etiquetas separadas de valores; contacto continuo, supervisores concatenados; tarjetas juntas | Campos compartidos; separar institución/contacto, supervisores, entidad/unidad/programa y país/ciudad; prosa amplia y separación de tarjetas |
| ConvenioDetallePage.tsx — /convenios/:convenioId | Información base local y resúmenes alineados a derecha | Campos compartidos, objeto amplio, alcance legible y separación del resumen |
| HistorialConvenioContenido.tsx — /convenios/:convenioId/historial y pestaña Historial | Rondas sin estilos e invitaciones con grilla propia | Campos compartidos en rondas, contraparte e invitaciones; separar fecha/usuario de resolución y tarjetas |
| AliadoDetallePage.tsx — /aliados/:aliadoId | dl sin estilos, tarjetas consecutivas | Migrar solo consulta; etiqueta de identificación legible y separación de tarjetas |
| ConvenioVersionPage.tsx — /convenios/:convenioId/versiones/:numero | Panel a derecha y snapshot con display:contents | Campos compactos; snapshot completo, editor intacto |
| ConvenioElaboracionPage.tsx — /convenios/:convenioId/elaboracion | proyecto-datos con sobrescrituras locales | Migrar solo resumen compacto |
| RevisionContrapartePage.tsx — /revisiones-contraparte/:revisionId | Resumen lateral a derecha | Migrar resumen compacto |
| RevisionContrapartePublicaPage.tsx — /revision-contraparte | Resumen proyecto-datos | Migrar solo metadatos |
| FirmaConvenioPublicaPage.tsx — /firma-convenio | Resumen proyecto-datos | Migrar solo metadatos |
| RevisionFinalConvenio.tsx — detalle | Resumen proyecto-datos | Migrar solo metadatos |
| SeguimientoFirmasConvenio.tsx — detalle y modal de evidencia | Firmantes y evidencia a derecha | Migrar lectura; acciones intactas |
| EvaluacionConvenio.tsx — detalle | Comentarios largos a derecha | Migrar lectura; comentarios amplios, formulario intacto |
| TableroConveniosPage.tsx — /convenios/tablero | Se examinó su dl | Sin cambios: grilla compacta con etiquetas diferenciadas y wrap adecuados |
| SolicitudHistorialPage.tsx / VersionesSolicitud.tsx — /solicitudes/:solicitudId/historial y /ori/solicitudes/:solicitudId/historial | Se examinó cronología y comparación | Sin cambios: fechas, títulos, autoría y columnas diferenciados |
| VersionesConvenio.tsx y lista en elaboración | Se examinaron metadatos de versiones | Sin cambios: tarjetas con título, etiquetas en negrita, fecha, contexto y enlaces identificables |
| LineaTiempoConvenio.tsx / ObservacionesJuridicas.tsx — historial | Se examinaron eventos y respuestas | Sin cambios: jerarquía propia; conservar estructura y estados |
| DocumentoAprobadoFirmaPage.tsx — /convenios/:convenioId/firmas/documento-aprobado | Se examinó cabecera documental | Sin cambios: cabecera diferenciada; documento oficial fuera de alcance |
| AccionVolver.tsx / retornoVolver.ts / docs/hu/ht-12-accion-volver.md | Borde negro de 2px y subrayado | Solo CSS existente: borde secundario de 1.5px, peso 600 y sin subrayado; foco oscuro intacto; ninguna modificación de lógica |

Las demás páginas examinadas corresponden a formularios, tablas, directorio o cronologías con estilos propios; no se amplía el alcance a esas áreas.

## Implementación

`DetalleCampos` genera un dl; `CampoLectura` agrupa dt/dd dentro de un div válido. No hay controles editables ni roles ARIA redundantes. Etiquetas secundarias de 13px y valores principales con peso 600. Separación de 4px dentro de cada campo y 20px/24px entre campos. La grilla calcula hasta dos columnas según el ancho disponible de la tarjeta; `compacto` conserva una columna en paneles y `amplio` ocupa toda la fila.

Se retiran `.proyecto-datos`, `.snapshot-campo`, las grillas particulares del historial y las sobrescrituras duplicadas de gestorConvenios.css. `.detalle-secciones` y `.detalle-grupo` resuelven espaciado sin cambiar globalmente .card ni .page.

Los vacíos usan —; booleanos directos Sí/No; cero se conserva. Correos, nombres, identificaciones, teléfonos y hashes ajustan línea sin elipsis ni recorte; `pre-wrap` conserva saltos de línea. Se reutiliza enumLabel para solicitante, tipo de contraparte, alcance e identificación. Fechas, duraciones y estados conservan sus formateadores existentes. El snapshot mantiene su serialización original.

## Comparación antes/después y QA manual pendiente

No se capturaron imágenes ni se ejecutó un navegador visual automatizado. Estas comparaciones describen el JSX/CSS antes/después y no acreditan aceptación visual. No se accedió a staging ni se conoce su dominio en esta sesión.

En el dominio de staging, comparar el despliegue anterior de develop con el de esta rama, usando los mismos registros. Obtener los IDs desde los listados y abrir estas rutas:

| Ruta | Antes | Después y pasos |
|---|---|---|
| /ori/solicitudes/{solicitudId} | Etiquetas en columna separada, contacto continuo y supervisores unidos por puntos | Desde /ori/solicitudes, abrir Ver. Comprobar institución/contacto, ambos supervisores con campos individuales, decisión y observaciones multilínea |
| /convenios/{convenioId} | Información base con grilla local | Desde /convenios, abrir detalle autorizado y Resumen. Etiquetas encima del valor; objeto a todo el ancho |
| /convenios/{convenioId}/historial | Rondas planas, resolución concatenada | Abrir Historial. Verificar jurídicas 1 y 2, contraparte y final separadas, estado, versiones, responsables, invitaciones, observaciones y respuestas intactos |
| /aliados/{aliadoId} | Lista sin separación visual | Desde /aliados, abrir perfil. Revisar los seis campos; Editar datos y Cancelar mantienen valores, permisos y validaciones; comprobar enlaces de convenios |
| /convenios/{convenioId}/versiones/{numero} | Panel a derecha y snapshot en celdas | Desde Historial, abrir Ver contenido. Panel vertical con autor/fecha/etapa y snapshot completo; documento sigue sin edición |
| /revision-contraparte y /firma-convenio | Metadatos alineados a derecha | Usar enlaces reales de invitaciones QA válidas, conservando sus parámetros. Revisar resumen, correos largos, documento y acciones existentes |

Repetir en **1440×900, 1280×800, 768×1024, 390×844 y 360×740**. Comprobar hasta dos campos cuando caben, paneles verticales, sin desbordamientos por nombres/correos/hashes ni pérdida de saltos de línea. Revisar zoom 200%, Tab/Shift+Tab/Enter y foco visible de Volver.

Usar Administrador, Gestor, Revisor y solicitantes interno/externo solo en sus rutas autorizadas. Con Revisor: Consulta → Historial → Versión → Volver sin acceso operativo. Con Gestor: entrar desde consulta filtrada y verificar regreso con filtros. Las pruebas automatizadas de roles usan HTTP simulado, no certifican autorizaciones reales del servidor.

## Control de alcance

Solo presentación frontend y documentación. No se modificaron backend, datos, permisos, router, contratos API, endpoints, validaciones, guardado, etapas, decisiones, revisión jurídica, versionamiento, renovaciones ni firmas. AccionVolver.tsx y retornoVolver.ts permanecen intactos. Sin cambios en contenido jurídico, PDFs, documentos almacenados, dependencias, branding, correos, filtros o tablas.

## Validación local — 16/11/2026

| Verificación | Resultado |
|---|---|
| `npm run typecheck` (frontend) | Aprobado |
| `npm run lint` (frontend) | Aprobado |
| Suite dirigida con `--maxWorkers=2` | 193 pruebas aprobadas en 13 archivos: solicitud recibida, detalle, historial, aliado, versión, Volver, elaboración, contraparte pública/autenticada, revisión final y firmas |
| `npm test -- --maxWorkers=2` (frontend, ejecución final) | **1062 pruebas aprobadas en 56 archivos**, 81.32 s |
| `npm run build` (frontend) | Aprobado; aviso de bundle JS >500 kB (1131.18 kB) |
| `git diff --check` | Aprobado |
| Accesibilidad | Revisión semántica dl/div/dt/dd; sin nuevos controles; valores completos; pruebas de teclado/retorno y contraste de texto, borde secundario y foco de Volver aprobadas |
| Navegador / resoluciones | No ejecutado; seguir los pasos manuales anteriores en las cinco resoluciones |

La suite completa incluye pruebas existentes de rutas/permisos y de lectura histórica. Se agregan dos pruebas del perfil de aliado: consulta sin controles para quien no puede editar y entrada/cancelación de edición con identificación restringida. La prueba de borde de Volver ahora verifica el color secundario real y mantiene el mínimo 3:1; no se relajan los umbrales de contraste ni las aserciones funcionales.

Vitest emite dos avisos conocidos de jsdom sobre navegación a otro documento durante exportaciones; no hay fallos ni pruebas omitidas. La primera ejecución completa aprobó 1060 pruebas en 55 archivos; la ejecución final incorpora las dos nuevas de aliado. La revisión automatizada no sustituye QA visual ni pruebas de autorización real con backend.

