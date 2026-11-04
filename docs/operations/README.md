# Manuales operativos — ORI Manager

| Documento | Fuente / estado |
|---|---|
| [Production Release Runbook](production-release.md) | Flujo aprobado de promoción `develop` → `main` y recuperación |
| [Supabase](supabase.md) | Privilegios, TLS, conexiones y migraciones |
| [Conciliación de convenios](conciliacion-convenios.md) | Propuesta de CLI y estrategia de scheduler; **no confundir con job en ejecución** |
| [Ejemplo de workflow de conciliación](conciliacion-convenios.workflow.yml.example) | Archivo `.example`, no ejecutado por GitHub Actions |
| [Regularización de códigos de convenio](regularizacion-codigos-convenio.md) | Procedimiento de HT-06 CA-08; **implementado y probado, sin autorización para datos reales** |

Las migraciones de staging se disparan con push a `develop`; las de producción con push a `main`, después de las validaciones configuradas. Render utiliza `After CI Checks Pass`. No ejecutar `alembic downgrade` sin evaluación de datos y compatibilidad.

[Drive — Gestión de Releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb): decisiones, planes, actas, respaldos verificables y evidencias. Los secretos y respaldos sensibles nunca deben publicarse en documentación compartida.
