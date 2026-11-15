# PR #181 — Cierre técnico del directorio público

Referencia técnica HU-09; identificador oficial pendiente de confirmación por
colisión con HT-09. Véanse [contrato y decisiones pendientes](../hu/hu-09-directorio-publico.md).

Se integra `origin/develop` (`3dc3626`) mediante merge normal sin conflictos.
Se conserva el trabajo del directorio y la corrección de HU-31 ya integrada,
sin cambios propios a HU-31. Vigencia estricta, identidad obligatoria y pruebas
del router real se incluyen junto con esta documentación.

## Validación local

PostgreSQL 18 aislado: `ori_manager_hu09_review_20261115`, migrado a
`0b2fb1bed5b2`. Ejecución desde el contenedor de desarrollo con `APP_ENV=test`
y `DATABASE_NAME` apuntando exclusivamente a esa base.

- Directorio backend: 52 aprobadas.
- Directorio frontend por router real: 8 aprobadas.
- Backend completo: **3017 aprobadas**, sin fallos ni errores (576,20 s).
  Incluye 221 regresiones de HT-06/HU-10/HU-27/HT-10 y las 152 pruebas de
  HU-31 (96 de acciones de renovación), sin modificar esa historia.
- Ruff completo (`src`, `tests`, `migrations`), TypeScript, ESLint y build:
  aprobados. Build advierte tamaño de bundle; no falla la compilación.
- Suite frontend completa: **951 aprobadas en 51 archivos** (40,38 s), incluida
  navegación/permisos del router y los 8 casos del directorio.

Los logs y JUnit se conservan localmente en `/tmp/ori-hu09-*` del contenedor y
`backend/var/hu09-review/` (excluidos del commit).
En Windows, Vitest usa `--pool=threads --maxWorkers=2`.
La suite completa frontend se ejecutó sobre copia Linux del código, con fuente
idéntica comprobada mediante `diff -qr`, lock idéntico comprobado por SHA-256 y
dependencias locales validadas con `npm ls --depth=0`. La ejecución sobre montaje
Windows se detuvo por lentitud después de completar la suite en Linux. Una
primera copia omitió `dist` de dependencias e impidió arrancar Vitest; se corrigió
antes de la ejecución completa, sin cambiar fuentes ni lock.
Ruff requiere copia con modos Linux 0644 porque el montaje Windows marca todos
los archivos como ejecutables; no se ignora EXE002 en la configuración.

Comandos ejecutados en `backend`: `.venv/bin/alembic upgrade head`,
`.venv/bin/pytest tests/test_hu09_directorio_publico.py -q` y
`.venv/bin/pytest -q --junitxml=/tmp/ori-hu09-backend-full.xml`.
Ruff: `.venv/bin/ruff check <copia-Linux>` de `src`, `tests`, `migrations` y
`pyproject.toml`. En `frontend`: `npm run typecheck`, `npm run lint`,
`npm run build`, `npm test -- src/pages/DirectorioConveniosPage.test.tsx
--pool=threads --maxWorkers=2` y `npm test -- --pool=threads --maxWorkers=2`.
`git diff --check` pasa. Los 20 avisos backend son de deprecación de
Starlette/httpx/anyio y `datetime.utcnow`, no errores de HU-31.

## Decisiones elevadas al líder técnico

### Incidencia detectada por CI durante el cierre

El primer CI del commit `c68802b` aprobó frontend y ambos CodeQL, pero backend
terminó con 3016 aprobadas y un fallo HU-27: el fixture genera una identificación
hexadecimal aleatoria y ocasionalmente produce solo dígitos. En ese caso HU-26
también la comparaba con `convenio.id` (INTEGER PostgreSQL), causando
`NumericValueOutOfRange` para `221551610907`.
La corrección mínima limita solo la comparación numérica por ID al máximo int4;
conserva las búsquedas textuales por identificación/código/objeto. El caso de
combinación con fechas ahora usa esa identificación numérica determinista tanto
para formalización como para vigencia. No modifica HU-31 ni sus fixtures.
Validación posterior a esta corrección: 108 pruebas específicas aprobadas,
Ruff y `git diff --check` aprobados. La validación global definitiva queda a
cargo del CI remoto; no se repiten las suites locales para publicar este ajuste.

La integración GitHub devolvió 403 al actualizar la descripción y publicar el
comentario a `tech-leads`; la alternativa con autenticación Git devolvió 500 y
no hay navegador conectado. No se afirma que esas escrituras se publicaron.
Las decisiones se entregan versionadas para revisión del equipo y en el reporte
final al solicitante. La descripción original del PR sigue desactualizada.

### Funcionalidad

- Confirmar el ID oficial y la ficha del backlog; HT-09 ya es bitácora.
- Resolver autorización/clasificación institucional para CA-06 y revisión de
  contenido libre de los campos públicos. No existe ese mecanismo en el modelo
  revisado; vigencia y lista blanca no lo sustituyen. CA-06 no se declara cerrado.

## Checklist

- [x] Integración normal, filtros, identidad y lista blanca.
- [x] Documentación de API/UI, permisos, alternos, riesgos y recuperación.
- [x] Validación global local completa.
- [ ] Checks remotos finales: se verificarán tras el push; consultar el PR
  para la evidencia del SHA final, sin confundir esta evidencia local con CI.
- [ ] Confirmación funcional de CA-06 y trazabilidad del backlog.
- [ ] Aceptación QA/UAT (no sustituida por CI).

No se realiza merge a develop. Las decisiones funcionales pendientes se reportan
sin inventar una política institucional.
