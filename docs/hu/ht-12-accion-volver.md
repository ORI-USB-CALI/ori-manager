# HT-12 — Acción de navegación Volver

Referencia técnica de [PR #168](https://github.com/ORI-USB-CALI/ori-manager/pull/168), destinado a `develop`. Relacionada con HT-03 (usabilidad de revisión e historial) y su incidencia [QA #143](https://github.com/ORI-USB-CALI/ori-manager/issues/143), que reporta bajo contraste e inconsistencias de presentación. Este documento no declara la historia terminada ni la incidencia resuelta: falta aceptación de QA.

## Objetivo y alcance

Una acción Volver identificable, con contraste suficiente, foco visible y posición uniforme al inicio de las vistas de convenios. Debe regresar al contexto inmediato y conservar el origen de los recorridos de varios niveles, incluidos los filtros de consulta.

Correcciones de esta revisión:

- **H-01:** los enlaces a pantallas secundarias no transmitían el origen del detalle; el cambio de pestaña también descartaba `location.state`. El retorno consumía una ruta sin restaurar el retorno propio de su destino.
- **H-02:** el error de lectura de Elaboración omitía la acción Volver.
- **H-03:** faltaba esta ficha y su entrada en el índice documental.

Solo frontend y documentación. Sin cambios en API, permisos, backend, datos, dependencias, HU-38, HU-39 o HT-14. Se conservan las condiciones que habilitan cada enlace y la autorización del servidor.

## Componente reutilizable

`frontend/src/components/AccionVolver.tsx` usa un `Link` de React Router con nombre accesible textual y flecha decorativa (`aria-hidden`). Está antes del encabezado, fuera del degradado, dentro de `.accion-volver-barra`. Mantiene las clases compartidas `.btn.accion-volver` en éxito y error.

Propiedades:

- `alternativo: Retorno`: destino interno definido por la pantalla cuando no hay contexto válido.
- `estado?: unknown`: propiedad preexistente para entregar explícitamente el retorno propio del destino. Se valida y se limita al contrato; si se omite, el componente entrega el `estado` del retorno seleccionado. Un valor explícito inválido no se propaga.

No se usa `navigate(-1)`: el historial del navegador puede incluir sitios externos o pantallas ajenas al recorrido.

## Contrato de navegación

Definido en `frontend/src/components/retornoVolver.ts`:

```ts
interface Retorno {
  to: string
  texto: string
  estado?: EstadoVolver
}
interface EstadoVolver {
  volver: Retorno
}
```

`volverA(ubicacion, texto)` construye un retorno a `pathname + search` y conserva únicamente el retorno anterior validado de `ubicacion.state`. Los consumidores anteriores que solo envían `{ volver: { to, texto } }` siguen funcionando.

Ejemplo en Elaboración después de Renovaciones → Detalle → Elaboración:

```ts
{
  volver: {
    to: '/convenios/41',
    texto: 'Volver al convenio',
    estado: {
      volver: {
        to: '/renovaciones?estado=PENDIENTE_DE_DECISION',
        texto: 'Volver al panel de renovaciones'
      }
    }
  }
}
```

Al volver desde Elaboración, el detalle recibe exclusivamente el estado con retorno a Renovaciones. Al volver desde el detalle, el panel recibe estado vacío. No se agrega la pantalla abandonada a la cadena de vuelta.

`retornoSeguro(estado, rutaActual?)` valida cada nivel, reconstruye objetos con solo los campos permitidos y elimina ciclos. Si una pantalla ya aparece en la cadena, se recupera el retorno de su visita original; cambiar la búsqueda no convierte esa misma ruta en otra pantalla. Así, Elaboración → Versión → Elaboración vuelve después al detalle y a su listado, sin alternar indefinidamente con Versión.

El cambio entre Resumen e Historial conserva el retorno validado y todos los parámetros existentes de la URL. Los enlaces desde historial y elaboración hacia una versión conservan el contexto inmediato y sus ancestros. La navegación desde firmas a Elaboración por cambio sustancial también conserva ese retorno, sin modificar la operación de negocio.

### Filtros jurídicos

Revisiones Jurídicas antes guardaba los filtros únicamente en estado local. Para cumplir CA-03, sus tres filtros se leen y escriben en la URL: `buscar`, `tipo` (nombre del tipo) y `responsable` (ID). Se sigue filtrando la misma respuesta en memoria; no cambia la consulta HTTP ni sus permisos. Cada edición reemplaza la entrada actual del navegador. Limpiar elimina solo esos tres parámetros y conserva los demás. Esto permite regresar, recargar o compartir la URL sin perder los filtros, sin incorporar almacenamiento global ni un refactor de tablas.

## Validaciones y destinos alternativos

Se conserva el rechazo de rutas externas: protocolo absoluto, `//host`, `/\host`, rutas relativas y caracteres de control. Límite de ruta: 2048 caracteres. El texto debe ser no vacío y tener como máximo 80 caracteres. Se descartan campos adicionales y ancestros inválidos; un retorno inmediato inválido usa el alternativo de la pantalla. La lectura se limita a ocho retornos y detecta referencias circulares; las cadenas truncadas terminan en los alternativos existentes.

La validación de estado evita redirecciones externas; no representa un permiso de acceso ni verifica que cada ruta interna exista en el servidor. Las rutas generadas por los enlaces corresponden a rutas existentes del módulo. El estado manipulado nunca concede permisos: las protecciones de rutas y API continúan aplicándose.

| Pantalla sin contexto válido | Destino alternativo |
|---|---|
| Detalle de proyecto/en trámite, cancelado o sin firma | Tablero de convenios |
| Detalle de convenio formalizado | Consulta de convenios |
| Error al consultar detalle | Tablero de convenios |
| Elaboración, Gestor/Administrador con ID válido | Detalle del convenio |
| Elaboración, Revisor ORI | Consulta de convenios |
| Elaboración con ID inválido, otros roles | Tablero de convenios |
| Historial independiente, Revisor ORI | Consulta de convenios |
| Historial independiente, otros roles | Detalle del convenio |
| Versión histórica, Revisor ORI o ID inválido | Consulta de convenios |
| Versión histórica, otros roles con ID válido | Detalle con `pestana=historial` |
| Documento aprobado para firma (éxito/error), Revisor ORI | Consulta de convenios |
| Documento aprobado para firma (éxito/error), otros roles | Detalle del convenio |

**HU-21:** un Revisor ORI puede consultar el historial de un convenio sin acceso a su detalle operativo. La Consulta mantiene `puede_ver_detalle`: abre el detalle si es verdadero y el historial independiente si es falso. El historial y sus versiones preservan ese camino. Un acceso directo del Revisor a historial o versión vuelve a Consulta. Un contexto válido que realmente procede del detalle puede regresar a ese detalle. No se agregan permisos ni se elude la autorización HTTP.

Un acceso directo o nueva pestaña sin estado usa los alternativos. Una recarga puede conservar `history.state` según el navegador; si lo conserva, se revalida, y si falta o es inválido se usa el alternativo. No se garantiza recuperar filtros que nunca se recibieron.

## Pantallas integradas

| Origen o vista | Integración |
|---|---|
| Tablero, Consulta, Renovaciones, Revisiones Jurídicas, perfil del Aliado y Reporte de convenios activos | Enlaces al detalle/historial con `volverA`; incluye el enlace de confirmación de renovación creada |
| Detalle | Volver uniforme, conservación entre pestañas, enlace a Elaboración con contexto |
| Elaboración | Volver en éxito y error de consulta; enlaces de versiones con contexto |
| Historial independiente y pestaña Historial | Volver con contexto; listado de versiones con retorno encadenado |
| Versión histórica | Volver al historial/proyecto de origen; enlace a Elaboración con contexto; alternativo por rol |
| Seguimiento de firmas | Enlace a documento aprobado y transición a Elaboración con contexto |
| Documento aprobado para firma | Volver compartido tanto en éxito como en error, restaurando el origen del detalle |

## Criterios de aceptación y accesibilidad

- **CA-01:** texto, borde y foco `#1a1d20`; superficie `#ffffff` y fondo/hover `#f8f9fa`. Contraste calculado desde los archivos CSS reales: **16.93:1** sobre la superficie y **16.06:1** sobre fondo/hover (texto ≥ 4.5:1 y borde/foco ≥ 3:1). El foco usa contorno sólido de 3px separado 2px del borde. Se conserva el estilo compartido del PR; su aceptación visual sigue pendiente de QA.
- **CA-02:** una sola acción al inicio, mismas clases, flecha, semántica y tratamiento visual en las vistas integradas y sus errores. La barra se oculta al imprimir el documento aprobado conforme al estilo existente.
- **CA-03:** retorna al contexto inmediato, preserva `search` y restaura el origen del detalle. Las visitas repetidas se colapsan para evitar ciclos; los accesos directos usan alternativos seguros por pantalla y rol.

Tab y Shift+Tab usan el orden nativo; Enter activa el enlace. No se introducen `tabIndex` positivos ni manejadores de teclado propios. La acción permanece en el flujo normal y puede ajustar su texto en espacios estrechos. La revisión del CSS y el DOM no sustituye las comprobaciones visuales en navegadores y dispositivos de QA.

## Pruebas y evidencia

`frontend/src/pages/NavegacionVolver.test.tsx` integra las páginas reales con HTTP y editor simulados:

1. Renovaciones filtradas → Detalle → Elaboración → Detalle → Renovaciones con la misma URL.
2. Tablero → Detalle → Elaboración → Detalle → Tablero.
3. Revisiones Jurídicas filtradas → Detalle → Elaboración → Detalle → mismos filtros.
4. Consulta filtrada → Detalle → pestaña Historial → Versión → Historial → Consulta.
5. Consulta filtrada, Revisor sin detalle operativo → Historial independiente → Versión → Historial → Consulta, sin pedir detalle ni elaboración.
6. Detalle → Elaboración → Versión → Elaboración → Detalle → Tablero, sin ciclo.
7. Consulta → Detalle → Documento aprobado (éxito o HTTP 409) → Detalle → Consulta.
8. URL directa de historial/versión/documento aprobado como Revisor → Consulta; error de Elaboración sin contexto como Revisor → Consulta.
9. URL directa de Elaboración → Detalle → Tablero.
10. Elaboración con HTTP 403/404/500: acción antes del error genérico, clic/Tab/Shift+Tab/Enter y alternativo seguro; HTTP 503 desde el detalle conserva el origen.
11. Confirmación de renovación creada → Detalle → panel de renovaciones con su filtro actualizado y parámetros ajenos conservados.

`AccionVolver.test.tsx` verifica rutas externas, tipos inválidos, ancestros no válidos, descarte de campos ajenos, estados profundos/circulares, contrato anterior, navegación por teclado, posición, clases y contraste/foco. `RevisionesJuridicasPage.test.tsx` verifica filtros URL y limpieza sin eliminar parámetros ajenos. Las suites existentes de detalle, elaboración, historial, versión, Consulta y versiones se ejecutan como regresión.

### Archivos de esta corrección

- Contrato y componente: `frontend/src/components/retornoVolver.ts`, `frontend/src/components/AccionVolver.tsx`.
- Enlaces secundarios: `frontend/src/components/VersionesConvenio.tsx`, `frontend/src/components/SeguimientoFirmasConvenio.tsx`.
- Pantallas: `frontend/src/pages/ConvenioDetallePage.tsx`, `frontend/src/pages/ConvenioElaboracionPage.tsx`, `frontend/src/pages/ConvenioVersionPage.tsx`, `frontend/src/pages/DocumentoAprobadoFirmaPage.tsx`, `frontend/src/pages/RenovacionesPage.tsx`, `frontend/src/pages/RevisionesJuridicasPage.tsx`.
- Pruebas: `frontend/src/components/AccionVolver.test.tsx`, `frontend/src/components/HistorialConvenioContenido.test.tsx`, `frontend/src/pages/NavegacionVolver.test.tsx` (nuevo), `frontend/src/pages/RevisionesJuridicasPage.test.tsx`. El cambio en el montaje del historial aporta el Router requerido por sus enlaces, sin cambiar sus aserciones funcionales.
- Documentación: esta ficha (nueva) y `docs/README.md`.

### Validaciones de esta corrección

Resultados de ejecución local del 01/11/2026, en el contenedor de desarrollo `ori-manager-workspace-1`, directorio `/workspace/frontend`; no se ejecuta CI remoto ni se accede a Staging/Producción.

| Comando | Resultado |
|---|---|
| `npm test -- src/components/AccionVolver.test.tsx src/pages/NavegacionVolver.test.tsx src/pages/ConvenioElaboracionPage.test.tsx src/pages/ConvenioDetallePage.test.tsx src/pages/ConvenioVersionPage.test.tsx src/pages/ConvenioHistorialPage.test.tsx src/pages/RevisionesJuridicasPage.test.tsx src/components/VersionesConvenio.test.tsx src/pages/ConsultaConveniosPage.test.tsx` | Aprobado: 134 pruebas en nueve archivos en la primera validación específica |
| `npm test -- src/components/AccionVolver.test.tsx src/pages/NavegacionVolver.test.tsx src/components/HistorialConvenioContenido.test.tsx src/pages/RevisionesJuridicasPage.test.tsx` | Aprobado: 49 pruebas en cuatro archivos; las dos comprobaciones añadidas después por rol se validan en la suite completa |
| `npm run typecheck` | Aprobado, salida 0 |
| `npm test` | Primera ejecución: salida 1; tres pruebas de historial sin Router y siete timeouts de inicio de workers (343 pruebas aprobadas y tres fallidas, siete archivos sin ejecutar). Corregido el montaje y repetida toda la suite en la fila siguiente |
| `npm test -- --maxWorkers=2` | Aprobado, salida 0: **420 pruebas en 34 archivos**, 364.03 s, incluidos los 18 recorridos finales de navegación; sin pruebas omitidas ni errores pendientes |
| `npm run lint` | Aprobado, salida 0, sobre el diff final |
| `npm run build` | Aprobado, salida 0; 218 módulos. Aviso de chunk JS de 1056.20 kB (> 500 kB) y aviso de tiempos de plugins; sin errores de build |
| `git diff --check` | Aprobado, salida 0 |

El primer intento de `npm run typecheck` en Windows no pudo iniciar TypeScript (`tsc` no disponible); se usa el entorno del contenedor. Las comprobaciones iniciales detectaron TS7022/TS2339 en el normalizador; se simplificó la construcción de la cadena antes de la validación final. La primera suite completa falló por tres pruebas de historial montadas sin Router y siete timeouts de inicio de workers: se agregó MemoryRouter a ese montaje y se repitió toda la suite con dos workers, sin cambiar la configuración del proyecto ni omitir pruebas. Las pruebas específicas posteriores del normalizador, historial y recorridos aprobaron (49 casos en cuatro archivos, antes de añadir dos comprobaciones adicionales por rol, también aprobadas en la suite completa). La suite completa emite dos mensajes de jsdom sobre navegación a otro documento en las pruebas de exportación; esas pruebas aprueban y no aparecen errores no controlados en el resultado final.

## Limitaciones y QA pendiente

- Las pruebas de navegación usan MemoryRouter/jsdom y respuestas HTTP controladas: no certifican permisos reales ni integración de extremo a extremo con backend.
- QA debe aceptar CA-01/02/03 con Gestor, Administrador y Revisor ORI, incluyendo un convenio fuera del alcance operativo del Revisor, cambios reales de etapa y errores de red.
- Pendiente comprobar foco visible y secuencia Tab/Shift+Tab/Enter en la aplicación completa, zoom 200/400 %, reflujo a 320px y dispositivos móviles, Firefox/Safari, recarga real y apertura en otra pestaña.
- El contexto de ocho niveles cubre los recorridos del módulo; al excederlo se descarta el tramo más antiguo y se usan alternativos seguros. No se conserva un historial ilimitado.
- No se cambia el estado oficial de la historia ni se cierra #143 sin aceptación de QA.

## Compatibilidad y reversión

La ampliación `Retorno.estado` es opcional. Los estados previos sin cadena siguen funcionando; si falta estado se usan las rutas alternativas existentes. No requiere migración de datos, configuración, API ni nuevas dependencias. URLs jurídicas anteriores sin filtros siguen mostrando la lista completa.

Para revertir, retirar conjuntamente los cambios frontend de HT-12 y esta documentación mediante el flujo normal de revisión; en un despliegue, restaurar el artefacto frontend anterior. No hay operaciones de base de datos ni cambios de permisos que revertir. Revertir solo el contrato perdería el retorno de varios niveles; conservar juntas las integraciones y sus pruebas.
