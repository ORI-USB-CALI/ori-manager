# HT-08 — Validar las fechas de vigencia al crear o elaborar un convenio

**Sprint:** 4 — Consultas · **Épica:** EP-03 · **Estimación:** 8 SP · **QA:** [#138](https://github.com/ORI-USB-CALI/ori-manager/issues/138).

## Comportamiento y criterios aprobados

- CA-01: rechazar un vencimiento anterior al día actual de `America/Bogota`.
- CA-02: rechazar un inicio posterior a la fecha de vencimiento.
- CA-03: aceptar un inicio anterior **o igual** al vencimiento, siempre que el vencimiento no haya pasado.
- Las fechas son opcionales mientras se elabora un borrador. Se validan los campos diligenciados.
- La igualdad inicio=vencimiento representa un cambio aprobado respecto de HU-12, que exigía vencimiento posterior estricto.

## Contratos y operaciones

| Operación | Regla aplicada |
| --- | --- |
| `POST /api/convenios` | Validación en creación desde solicitud o renovación |
| `POST /api/convenios/manual` | Validación en creación manual |
| `PATCH /api/convenios/{id}` | Valida cuando cambian las fechas |
| `PATCH /api/convenios/{id}/elaboracion` | Valida al cambiar fechas; permite editar otros campos históricos |
| `GET /api/convenios/{id}/elaboracion/validacion` | Incluye errores de vigencia en `faltantes` |
| `POST /api/convenios/{id}/elaboracion/finalizar` | Revalida antes de enviar a Jurídica |
| `POST /api/convenios/{id}/firmas/formalizar` | Impide formalizar convenios con vencimiento pasado |

Los errores controlados de vigencia se presentan como **HTTP 422**, con `detail.message` y `detail.faltantes` (`campo` y `motivo`). El frontend muestra errores de fecha anticipados; el backend conserva la validación autoritativa. Una fecha de vencimiento igual a hoy sigue siendo válida durante ese día en Bogotá.

## Seguridad y compatibilidad

- No se alteran roles/permisos ni se introducen endpoints públicos.
- No hay cambio de modelo de BD ni migración Alembic.
- Los convenios históricos no se reescriben automáticamente; editar datos no relacionados con fechas no se bloquea por una vigencia histórica inválida.
- Se centraliza `fecha_actual_dominio` en `backend/services/vigencia.py`; renovaciones y alertas usan el mismo calendario. El frontend calcula la misma fecha de dominio, sin depender de la ubicación del navegador.
- La validación no cambia estados contractuales, ni ejecuta conciliaciones o renueva convenios.

## Pruebas y seguimiento

- Backend: `backend/tests/test_ht08_validacion_vigencia.py`, HU-12, HU-30, ciclo de vida y renovación.
- Frontend: `frontend/src/pages/vigencia.test.tsx` y `frontend/src/pages/ConvenioNuevoPage.test.tsx`.
- Verificar manualmente `ConvenioElaboracionPage`: edición, error 422, guardado parcial, revalidación y formalización.
- Ejecutar checks del PR y QA en Staging; no marcar HT-08 terminada por el solo hecho de abrir un PR.
- Issue relacionado: [QA #138](https://github.com/ORI-USB-CALI/ori-manager/issues/138). Cerrarlo solo tras merge y verificación del flujo afectado.

## Reversión

Revertir el commit de HT-08 para recuperar la política de fechas anterior. Sin cambios de BD; documentar cualquier convenio creado durante el intervalo que pudiera tener fechas iguales.
