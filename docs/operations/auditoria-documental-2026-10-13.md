# Auditoría documental — Sprint 1 a Sprint 3

**Fecha:** 13/10/2026. **Base técnica:** `develop` observado en el commit `ffb2e97a00535ec274d896895d2e9d4c1517c1b2`. **Fuente de estados:** exportación Notion de 45 HU/HT aportada por el equipo. No se ha cambiado ningún estado en el backlog.

## Hallazgos confirmados

| Hallazgo | Medida propuesta en este paquete |
|---|---|
| README describía modelo antiguo de tres roles | Sustituir por navegación y códigos actuales del backend |
| `docs/operations/supabase.md` decía migración de producción manual | Actualizar con `Production DB Migrations` automática condicionada a CI en push `main` |
| Revisión Alembic `56626120dc9a (head)` presentada como estado actual en manual Supabase | Etiquetar como baseline histórico; consultar `alembic current/heads` por ambiente |
| Faltaban índices generales y documentación consolidada de Sprint 1 y Sprint 2 | Agregar índice, resúmenes por sprint y matriz de HU |
| Sprint 3 está en curso con estados variados | Registrar literalmente `Estado` de cada historia sin inferencia técnica |
| No existía política formal de documentación por commit | Nueva política y PR template con control de cambios documentales |
| README anterior indicaba seis firmas, pero la descripción y CA de HU-15 exportada registran siete | Conservamos el texto de la HU-15 en su ficha y señalamos discrepancia para confirmación PO antes de R1, sin alterar el backlog |
| GitHub Wiki requiere navegación consistente | Preparar portada `docs/wiki/Home.md` y publicar separadamente al tener permiso |

## Elementos que NO se alteran automáticamente

- `docs/hu11-solicitudes.md` y `docs/ht01-validacion.md`: contienen decisiones y evidencias técnicas específicas; se enlazan, no se borran.
- `docs/operations/production-release.md`: el flujo central coincide con `.github/workflows/ci.yml` y `render.production.yaml` en el corte revisado.
- `docs/operations/conciliacion-convenios.md`: es una propuesta técnica con `workflow.yml.example` que no activa programador. Contiene referencias temporales a una rama inicial y a ausencia previa de HU-32; dado que `develop` ya tiene migración de HU-32, verificar con su autor antes de reescribir afirmaciones históricas de pruebas. No declarar programador habilitado.
- No ejecutar migraciones, cambiar secretos ni tocar Render/Supabase: auditoría de documentos solamente.

## Cierre

La recuperación documental no sustituye las especificaciones individuales de todas las HU y sus pruebas. A partir de la aprobación de la política, cada cambio funcional nuevo debe ampliar el documento técnico que corresponda en su propio commit. Para material histórico adicional que no exista, vincular PR y evidencia antes de completar detalles no observados.
