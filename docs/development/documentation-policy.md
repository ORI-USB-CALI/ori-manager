# Política de documentación continua

**Aplicación:** commits futuros a partir de la adopción de esta política en `develop`. No se presupone que los commits históricos la cumplieran. Responsable: autor de la HU/cambio; revisión: code reviewer y líder técnico.

## Documentar en cada commit

**Todo commit nuevo con impacto funcional debe incluir la documentación impactada en el mismo commit**. Para un cambio exclusivamente documental utilizar `docs/*`.

| Cambio | Evidencia documental mínima |
|---|---|
| HU/FIX/HT | Objetivo, referencia a la historia, comportamiento, permisos, errores/alternos y pruebas |
| API o UI | Rutas, validación, permisos, navegación o interacción afectada |
| Modelo/migración | Tablas, relaciones, Alembic, compatibilidad y recuperación |
| Correo/Graph/infraestructura | Variables sin secretos, dependencias, controles y procedimiento de despliegue |
| Refactor | Contrato conservado, impacto y regresiones |
| Solo pruebas | Qué comportamiento queda cubierto y dónde ver resultados |
| Sin impacto documental | Justificación concreta en commit y PR; nunca agregar archivo vacío para simular cumplimiento |

Para una nueva historia, crear o ampliar un documento bajo `docs/hu/` o un archivo especializado existente y enlazarlo desde el índice. Registrar el alcance real y **no** marcar completada una HU por inferencia de código.

## Fuentes de verdad

- **Estado de HU:** backlog oficial exportado/actualizado. Respetar `Sin iniciar`, `En curso`, `Pruebas`, `Terminado`.
- **Contratos técnicos:** código, tests, migraciones y documentación versionada.
- **Releases/aceptaciones:** fichas, actas y decisiones en Drive, PR/commit/tag correspondiente en GitHub.
- **Wiki:** directorio técnico con enlaces a `docs/`, no copia divergente.

## Flujo en cada PR

1. Confirmar HU/CA, sprint, estado y dependencias antes del cambio.
2. Añadir documentación pertinente **en cada commit** junto con el código.
3. Completar el checklist de PR (HU/HT, documentos, pruebas, seguridad, rollback cuando corresponda).
4. Revisar coherencia con permisos, contrato HTTP, migraciones, campos de datos e interfaces.
5. Integrar por PR hacia `develop`. En promoción a `main`, registrar versión, evidencias y aceptación en Drive.
6. Anotar cambios posteriores de historias cerradas sin reescribir falsamente su fecha o estado histórico.

## Criterios de revisión

Enlaces relativos correctos; no secretos ni credenciales; documentar limitaciones y qué se probó exactamente; distinguir CI de UAT; mencionar estados técnicos sin reemplazar el estado de la HU. Las pruebas integrales del sistema se planifican al final del Sprint 5.

### Adopción progresiva

En esta auditoría no agregamos un workflow bloqueante retrospectivo que pueda romper PR de Sprint 3 ya iniciados. Una comprobación automatizada por commit podrá activarse posteriormente con excepciones documentadas y una ventana de transición aprobada.
