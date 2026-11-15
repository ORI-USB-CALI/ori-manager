# HT-17 - Vigencia contractual

Decisiones definidas por el lider tecnico para el cierre tecnico de #175 y PR #182.
No constituyen evidencia de aprobacion del PO/ORI. La aceptacion institucional debe quedar trazada en https://github.com/ORI-USB-CALI/ori-manager/issues/175.

## Reglas definitivas

- Inicio y duracion son entradas; el backend calcula y persiste vencimiento en la misma transaccion. El cliente puede omitirlo; si lo envia contradictorio recibe 422 con campo y motivo.
- Minimo cuatro meses para registro o cambio de vigencia. Inicio desde hoy en America/Bogota, sin anticipacion minima. No se modifica fecha de firma.
- Sumar meses calendario (ajustando dias inexistentes) y restar un dia. Si inicio es ultimo dia de mes, usar ultimo dia del mes destino. Ambos extremos inclusivos (HT-10).

| Inicio | Meses | Vencimiento |
|---|---|---|
| 01/01/2027 | 12 | 31/12/2027 |
| 15/01/2027 | 4 | 14/05/2027 |
| 31/01/2027 | 4 | 31/05/2027 |
| 31/10/2026 | 4 | 28/02/2027 |
| 29/02/2028 | 12 | 28/02/2029 |

## Borradores e historicos (CA-06)

La migracion c17a20261115 agrega vigencia_ht17=false sin reescribir fechas ni duraciones. Nuevos convenios y modificaciones expresas de vigencia activan la marca dentro de la transaccion. Abrir, consultar o reenviar valores sin cambios no activa la regla ni recalcula. Los convenios anteriores pueden seguir en tramite.

Los borradores admiten campos parciales. Antes de finalizar, los sujetos a HT-17 requieren inicio, duracion y vencimiento completos y coherentes. El paso del tiempo no vuelve retroactivo un inicio registrado validamente. Los historicos no se bloquean por convenciones o duraciones antiguas; siguen aplicando HT-08 y la prohibicion de formalizar vencidos.

Renovaciones no heredan fechas. Una duracion historica inferior a cuatro no se copia al nuevo periodo; debe definirse en elaboracion. Alertas, conciliacion Python/SQL y tareas siguen leyendo fecha_vencimiento persistida, sin formulas ni umbrales nuevos.

Frontend calcula solo al editar inicio o duracion; vencimiento es de solo lectura. La carga inicial conserva los valores del servidor.

## Validacion

Pruebas en test_ht17_cierre.py y test_ht17_duracion_vigencia.py: ejemplos, fin de mes, bisiestos, cambio de ano, medianoche Bogota, minimo, retroactividad, rangos, consistencia API, rechazo sin persistencia, historicos en tramite, alertas y vencimiento inclusivo. Regresiones HT-08, HT-10, HT-14, HU-12, HU-15 y HU-31, formularios, TypeScript, ESLint y Ruff. La validacion completa corresponde a GitHub Actions; sin despliegue manual ni merge a develop.
