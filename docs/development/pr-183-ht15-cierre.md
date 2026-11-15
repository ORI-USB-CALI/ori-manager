# PR #183 — cierre de integración HT-15

Se integra `origin/develop` (26fe030) mediante merge normal en la rama de HT-15,
conservando HT-16, HT-17 y las funcionalidades ya integradas. El conflicto en la
prueba de migraciones conserva la comprobación contra la cabeza real de Alembic.

## Migraciones y vigencia

La cadena termina en `0b2fb1bed5b2 → c17a20261115 → 3816fbbdff1a`, con una única
cabeza. Se ajusta únicamente la dependencia de HT-15: no se agregan migraciones
ni se reescriben datos o snapshots históricos. Los convenios nuevos de las pruebas
HT-15 usan la fecha de dominio y el vencimiento calculado por HT-17, con 24 meses
de duración. Los antecedentes finalizados de renovación conservan fechas históricas
explícitas.

## Decisión de concurrencia

El endpoint HTTP de finalizar exige un cuerpo con `expected_revision` entero no
negativo. El cliente del editor ya envía la revisión de su estado base. El servicio
comprueba la revisión bajo el bloqueo del convenio antes de aplicar metadatos,
crear versiones o abrir rondas; una revisión obsoleta responde 409 y hace rollback.
Las llamadas internas sin formulario conservan el comportamiento existente y el
bloqueo pesimista. Se mantiene el commit único para versión, historial y revisión.
Las pruebas HTTP que no simulan conflictos leen primero la revisión vigente; las
pruebas de conflictos conservan revisiones explícitas, sin reintentos automáticos.

Se conservan las reglas aprobadas de V1, borradores, reutilización, observaciones
obligatorias y RJ1/RJ2. Las decisiones funcionales adicionales corresponden al líder
técnico; no se amplía el alcance ni se requiere consulta adicional al PO.

## Validación

- Ruff: sin errores.
- Alembic: upgrade completo en `ori_ht15_integration`, cabeza única y orden
  HT-17 → HT-15 comprobados; upgrade/downgrade/reaplicación con preservación de
  historia y catálogo verificados por `test_ht14_migraciones.py`.
- Primer bloque: cuatro archivos `test_ht15_*` y migraciones, 39 aprobados y dos
  fallos de vigencia en renovaciones. Se corrigió la fixture del convenio nuevo,
  conservando el antecedente histórico y todas las aserciones.
- Bloque posterior: 38 aprobados (30 casos HTTP afectados, los siete casos de
  revisiones jurídicas HT-15 y la comprobación explícita de la cadena Alembic).
- Contrato HTTP: tres casos explícitos aprobados (sin cuerpo, sin revisión y
  revisión obsoleta sin persistir cambios).
- Frontend: `ConvenioElaboracionPage.test.tsx`, 18 aprobados.
- `git diff --check`: sin errores. No se ejecutaron suites completas.

## Archivos del cierre

Además de los archivos heredados del merge de develop, el cierre modifica:

- `backend/migrations/versions/3816fbbdff1a_ht_15_observacion_que_obliga_a_corregir.py`.
- `backend/src/backend/api/routers/convenios.py` y `schemas/convenio.py`.
- Los cuatro archivos `backend/tests/test_ht15_*.py` y `test_ht14_migraciones.py`.
- Nuevo helper `backend/tests/helpers_revision.py`; adaptación de peticiones en
  pruebas HT-08, HT-13, HT-16, HT-17, HU-12, HU-13, HU-21 e integración HU-07/HU-17.
- `docs/README.md` y este registro.

Riesgo residual: la integración completa queda pendiente de GitHub Actions. El
contrato HTTP ahora rechaza clientes externos que omitan `expected_revision`;
el editor incluido ya la envía. Se conserva la API interna sin formulario para
los flujos existentes, protegida por el bloqueo y la transacción actuales.
La suite completa corresponde a GitHub Actions y su revisión al líder técnico.
No se realiza merge a develop, despliegue ni validación manual en navegador.
