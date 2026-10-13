# Sprint 3 — Documentación (en curso)

**Referencia:** exportación de HU recibida el 13/10/2026. `Estado del sprint` aparece `En proceso` y se conserva cada `Estado` individual sin reinterpretarlo por código o commits.

| Estado de HU | Registros |
|---|---|
| **Terminado** | HU-21 — Historial de observaciones jurídicas |
| **En curso** | HU-18 — Bitácora; HU-20 — Línea de tiempo; HT-02 — Re-radicaciones; HT-03 — Usabilidad de revisión de contraparte |
| **Pruebas** | HU-22 — Documentos soporte; HU-24 — PDF; HU-26 — Búsqueda; HU-27 — Filtros por fecha; HU-28 — Filtros avanzados; HU-30 — Alertas; HU-31 — Renovaciones; HU-32 — Evaluación; HU-33 — Notificaciones; HU-34 — Reporte activos; HU-35 — Utilización; HU-36 — Reporte estado; HT-01 — Retroalimentación solicitudes |
| **Sin iniciar** | HU-10 — Crear convenio manualmente |

**Total:** 19 registros (1 terminado, 4 en curso, 13 en pruebas, 1 sin iniciar). Una historia en `Pruebas` no se da por `Terminado` únicamente porque tenga PR integrado en `develop` o pruebas automatizadas verdes.

## Organización por ámbitos

- EP-03/04: solicitudes, revisiones, observaciones, bitácora y línea de tiempo.
- EP-05: carga de documentos soporte y PDF.
- EP-06: búsqueda y filtros.
- EP-07: alertas, panel de renovaciones, evaluación y notificaciones.
- EP-08: reportes y registro de utilización.

Consultar [HT-01 — validación](../ht01-validacion.md), [conciliación de convenios](../operations/conciliacion-convenios.md) y [QA Sprint 3](https://drive.google.com/drive/folders/1aTVN1l-TRAwRvBQpexRHc-Zo7kGXx8oU).

La documentación de conciliación describe un **scheduler propuesto**, no activo. Los desarrollos técnicos pueden estar presentes en la rama sin haber sido formalmente aceptados.

## Próximas validaciones

1. QA termina las HU en `Pruebas` y las devoluciones que correspondan.
2. PO actualiza estados de las HU en el backlog (única fuente para declararlas terminadas).
3. Los cambios funcionales llevan su documentación específica en cada commit.
4. La prueba integral de todo el sistema se mantiene prevista **al finalizar Sprint 5**.
5. La promoción a `main` sigue las reglas del [runbook](../operations/production-release.md), no se realiza automáticamente por cierre de una HU.
