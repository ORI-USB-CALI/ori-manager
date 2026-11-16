# Lote 3 — Identidad institucional, directorio y correos

Inventario previo a implementación. Base: origin/develop posterior al merge de #197. Se buscaron nombres visibles, cabeceras, pies y todos los constructores de MensajeCorreo en frontend/backend.

| Contexto / archivos | Nombre actual / inconsistencia | Decisión |
|---|---|---|
| AppLayout / HeaderNav | ORI Manager correcto; pie «Sistema de Gestión ORI» | Conservar cabecera/navegación; explicitar producto y área en pie sin tocar rutas |
| HomePage / onboardingInicial | «Oficina de Relaciones Internacionales» | Usar Oficina de Relaciones Interinstitucionales solo en texto visible |
| DirectorioConveniosPage | Marca circular ORI, sin nombre del producto; pie omite Cali; tabla comprimida | Cabecera tipográfica compartida, contexto y pie institucional, jerarquía sobria y tabla optativa del Lote 2; conservar consulta y siete campos |
| LoginPage, RegistroPage (sus estados), RecuperarContrasenaPage, RestablecerContrasenaPage, VerificarCorreoPage | ORI Manager sin contexto universitario/área | Identidad tipográfica compartida de acceso, sin cambiar formularios o autenticación |
| FirmaConvenioPublicaPage / RevisionContrapartePublicaPage | Cabeceras USB/ORI distintas; uno de los pies omite Cali | Misma identidad pública y pie; contenido/acciones/tokens intactos |
| frontend/public/favicon.svg, icons.svg y assets | Recursos SVG de scaffold; sin logotipo universitario oficial ni autorización documentada | No descargar ni inventar escudo. Identidad tipográfica; favicon tipográfico del producto. Sprite sin uso institucional queda intacto |
| services/firma_electronica.py | HTML local sin estructura; texto ya identifica Universidad; rol/cargo y enlace fragmento | Plantilla compartida con contexto y CTA Revisar y firmar; preservar destinatario, asunto, enlace, texto, vigencia y transacción |
| services/contraparte_externa.py | HTML local duplicado; CC opcional y token en fragmento | Plantilla compartida; conservar CC, texto, enlace y vigencia |
| services/verificacion_correo.py | «ORI USB Cali» y HTML mínimo, enlace sin escape explícito | ORI Manager en mensajes visibles y asunto; plantilla con escape central, 24 horas y seguridad existentes |
| services/recuperacion_contrasena.py | «ORI USB Cali», HTML duplicado y enlace sin escape explícito | ORI Manager en mensajes visibles y asunto; plantilla con escape central, 30 minutos y seguridad existentes |
| services/correo.py | MensajeCorreo, CorreoLocal y CorreoBrevo ya separan HTML/texto | Sin cambios al adaptador, payload, errores ni reintentos; probar integración mediante dobles |
| Resto de servicios / notificaciones | Solo cuatro constructores reales de MensajeCorreo | No agregar envíos ni transformar notificaciones internas en correos |
| Documentos oficiales, identificadores, API y referencias históricas | Nombres técnicos/históricos | Fuera de cambios de denominación |

HU-09: la decisión institucional sobre publicación/confidencialidad de `docs/hu/hu-09-directorio-publico.md` permanece pendiente. El pulido visual no implica aprobación de CA-06 ni amplía campos o criterios de publicación.

Entornos: frontend Windows en copia temporal con dependencias propias, sin modificar node_modules compartido con Linux. Backend en Dev Container existente. Previsualizaciones con datos y tokens ficticios; sin envíos reales ni recursos externos obligatorios en HTML de correo.

## Implementación y justificación por archivo

- `IdentidadInstitucional.tsx`: nombre del producto, Universidad y área separados en una marca tipográfica; cabecera pública y pie compartidos. No pretende ser un logotipo oficial.
- `DirectorioConveniosPage.tsx`: contexto «Consulta pública», cabecera/pie, acceso a login, contenedor más amplio y columnas de la variante optativa del Lote 2. Las siete propiedades y sus valores, formateador de fechas, query, paginación y mensajes de error se conservan. Carga y error reciben superficie de tarjeta, con status/alert según corresponda.
- `LoginPage.tsx`, `RegistroPage.tsx`, `RecuperarContrasenaPage.tsx`, `RestablecerContrasenaPage.tsx`, `VerificarCorreoPage.tsx`: reemplazan solamente la marca de cada estado existente por el componente institucional; formularios y autenticación intactos.
- `FirmaConvenioPublicaPage.tsx` y `RevisionContrapartePublicaPage.tsx`: reutilizan cabecera/pie, sin tocar extracción de tokens ni decisiones.
- `AppLayout.tsx`: conserva ORI Manager en la cabecera y explicita producto/área en el pie. `HeaderNav.tsx` no requiere cambios.
- `HomePage.tsx` y `onboardingInicial.ts`: corrección textual de Internacionales a Interinstitucionales, sin cambiar recorridos.
- `index.css`: estilos acotados de identidad, cabecera, pie y directorio; separación del paginador. Se retiran reglas sin consumidores de login-brand, revision-publica-header/footer. No cambian variables ni estilos de los Lotes 1/2.
- `public/favicon.svg`: sustituye el gráfico de scaffold por las letras ORI en colores del producto; no es un escudo universitario. No se descargan imágenes.
- `services/plantillas_correo.py`: única presentación HTML, con tablas de maquetación, estilos inline, fuentes del sistema, título, contexto, CTA, vigencia, seguridad y pie. Escape central de **todos** los parámetros, incluidos atributos href; no acepta HTML crudo ni modifica URLs.
- Los cuatro servicios de correo solo sustituyen el HTML local por esta función. Firma conserva convenio/rol/cargo y CTA «Revisar y firmar»; contraparte conserva CC. En verificación/recuperación se renombra ORI USB Cali a ORI Manager en asunto y texto visible, preservando instrucciones, enlaces y seguridad. Firma y contraparte conservan su texto plano anterior. Las cuatro versiones texto siguen construidas independientemente.
- `scripts/previsualizar_correos.py`: llama a los cuatro servicios reales con CorreoLocal, objetos ficticios y un doble de sesión. No consulta DB ni el proveedor configurado. Solo genera archivos locales HTML/TXT con tokens explícitamente ficticios y dominios example.invalid.
- `tests/test_plantillas_correo.py`: estructura HTML balanceada, título, CTA, identidad, enlaces íntegros, tokens de prueba con caracteres especiales, vigencias, destinatarios/CC, inyección y payload/errores de Brevo mediante MockTransport.
- `DirectorioConveniosPage.test.tsx`: añade comprobación de identidad, siete encabezados, región enfocable y acceso a login por teclado. Las regresiones HU-09 siguen comprobando anonimato, lista blanca, errores y paginación.

Los nombres en PDFs/reportes exportados y referencias históricas no se modifican. Los recursos no autorizados no se presentan como institucionales. La configuración del remitente y los adaptadores `CorreoLocal`/`CorreoBrevo` permanecen intactos.

## Evidencia visual y previsualizaciones

Capturas de Chrome **157.0.8103.52** con datos ficticios. Antes: develop **6bd96b1**, posterior al merge #197. No se accedió a staging/producción ni se enviaron correos.

| Vista | Antes | Después |
|---|---|---|
| Directorio 1440×900 | [Captura](evidencia/lote3/antes-directorio-1440.png) | [Captura](evidencia/lote3/despues-directorio-1440.png) |
| Directorio 390×844 | [Captura](evidencia/lote3/antes-directorio-390.png) | [Captura](evidencia/lote3/despues-directorio-390.png) |

Estados móviles: [carga](evidencia/lote3/directorio-carga-390.png), [vacío](evidencia/lote3/directorio-vacio-390.png), [error genérico](evidencia/lote3/directorio-error-390.png).

| Correo | HTML / texto plano ficticios | Escritorio | Móvil |
|---|---|---|---|
| Firma | [HTML](evidencia/lote3/correos/firma.html) / [TXT](evidencia/lote3/correos/firma.txt) | [Captura](evidencia/lote3/firma-1440.png) | [Captura](evidencia/lote3/firma-390.png) |
| Contraparte | [HTML](evidencia/lote3/correos/contraparte.html) / [TXT](evidencia/lote3/correos/contraparte.txt) | [Captura](evidencia/lote3/contraparte-1440.png) | [Captura](evidencia/lote3/contraparte-390.png) |
| Verificación | [HTML](evidencia/lote3/correos/verificacion.html) / [TXT](evidencia/lote3/correos/verificacion.txt) | [Captura](evidencia/lote3/verificacion-1440.png) | [Captura](evidencia/lote3/verificacion-390.png) |
| Recuperación | [HTML](evidencia/lote3/correos/recuperacion.html) / [TXT](evidencia/lote3/correos/recuperacion.txt) | [Captura](evidencia/lote3/recuperacion-1440.png) | [Captura](evidencia/lote3/recuperacion-390.png) |

Se ejecutaron **1440×900, 1280×800, 768×1024, 390×844, 360×740 y 320×740**: seis comprobaciones del directorio y 24 de los cuatro correos. No hay overflow de página. La tabla permite alcanzar Estado en su propio contenedor. Cada correo conserva cabecera, CTA visible y foco nativo por Tab. Se inspeccionaron las capturas de escritorio/móvil y los estados alternos. Las medidas completas están en [antes](evidencia/lote3/antes-medidas.json), [después](evidencia/lote3/despues-medidas.json) y [correos](evidencia/lote3/correos-medidas.json).

Contraste calculado sobre blanco: rojo institucional #d91a2a **5.08:1**, secundario #5a626a **6.19:1**, principal #1a1d20 **16.93:1**. El CTA blanco sobre rojo mantiene 5.08:1 y subrayado; los enlaces son elementos a nativos, sin JavaScript.

### Reproducción segura

Desde backend, en el Dev Container:

```bash
uv run python scripts/previsualizar_correos.py --salida /workspace/docs/evidencia/lote3/correos
```

Esto usa exclusivamente CorreoLocal. Se pueden abrir los HTML localmente sin activar enlaces ni enviar mensajes. Los tokens FICTICIO_SIN_VALIDEZ_123 carecen de registro/validez.

El [script de navegador](evidencia/lote3/validar.cjs) usa Playwright instalado fuera del repositorio; admite ORI_PLAYWRIGHT_MODULE, ORI_CHROME_PATH y ORI_QA_BASE_URL. Se ejecuta desde la raíz con argumento antes/despues. En esta sesión el frontend se sirvió en http://127.0.0.1:5176 desde una copia temporal completa con su propio npm ci, sin tocar node_modules del workspace. El script intercepta solo datos ficticios y verifica que el directorio no solicite APIs privadas. Las previsualizaciones de correo navegan a about:blank para aislarlas del runtime SPA.

### Limitaciones y QA pendiente

Chrome no certifica Gmail, Outlook, Apple Mail, clientes antiguos ni modo oscuro. En Outlook pueden variar max-width, border-radius y espaciado; la información sigue siendo texto y tablas, sin depender de scripts, imágenes o fuentes remotas. Pendientes pruebas reales de recepción en clientes de correo autorizados por QA, lectores de pantalla, zoom real 200%/400% y Firefox/Safari. No se realizaron envíos reales para obtener estas capturas.

En staging, comprobar /directorio anónimo, paginación y estados alternos; /login, /registro, /recuperar-contrasena y los enlaces ficticios de QA para verificación, recuperación, firma y contraparte. Mantener la lista blanca y el criterio de vigencia. **La decisión institucional de confidencialidad/publicación de HU-09 sigue pendiente y no se declara resuelta.**

## Validación y entorno

| Verificación | Resultado |
|---|---|
| npm run typecheck | Aprobado en copia Windows aislada |
| npm run lint | Aprobado en copia Windows aislada |
| npm test -- --maxWorkers=2 | **1070 pruebas aprobadas en 58 archivos**, 88.50s |
| Suite dirigida final de directorio, revisión pública, onboarding y responsive | **37 pruebas aprobadas en 4 archivos** |
| npm run build | Aprobado; aviso de bundle JS >500kB (1134.55kB) |
| uv run pytest -q tests/test_plantillas_correo.py | **8 pruebas aprobadas** |
| uv run pytest -q | **3211 pruebas aprobadas**, 21 avisos, 481.35s, en base temporal vacía |
| Ruff sobre los siete archivos Python intervenidos | Aprobado con EXE002 omitido por permisos ejecutables del montaje Windows; sin cambios de infraestructura |
| git diff --check | Aprobado |

Los avisos backend corresponden a deprecaciones existentes de FastAPI/Starlette, parametrización y datetime.utcnow. Frontend emite los avisos conocidos de jsdom de navegación en exportaciones; no hay pruebas omitidas ni errores no controlados en los resultados finales.

### Incidente de validación local

La primera ejecución contra la base de desarrollo compartida encontró fallos de conciliación por registros ajenos a los fixtures. La reproducción con -x terminó con 1 fallo y 45 aprobadas; otra ejecución interrumpida registró 5 fallos y 197 aprobadas. No se modificaron pruebas para ocultarlos.

Al preparar el aislamiento se pasó DATABASE_URL, pero Settings utiliza DATABASE_NAME. La variable ignorada hizo que el primer intento ejecutara **la migración ya existente c17a20261115 → 3816fbbdff1a sobre la base local del contenedor**, añadiendo observacion_revision.requiere_correccion con su default existente. No se ejecutó downgrade automático sobre datos compartidos. No se accedió a staging/producción.

Se corrigió la variable a DATABASE_NAME=ori_manager_lote3_tests_20261116, se aplicaron las migraciones existentes en esa base temporal y se ejecutó toda la suite sin fallos. La base temporal se elimina al cerrar la validación. No se añadieron/modificaron archivos de migración, configuración ni infraestructura en el PR. La actualización de la base local compartida queda expresamente registrada para el líder técnico.

## Control de alcance

El código propuesto no cambia endpoints, contratos API, permisos, datos publicados, filtros/orden/paginación, autenticación, tokens, expiraciones, transacciones, reintentos, manejo de errores ni flujos de revisión/firma. No modifica proveedores, configuración de despliegue, migraciones, documentos oficiales, dependencias o estilos correctos de los Lotes 1 y 2. La intervención backend se limita a presentación HTML y denominación visible del producto, con pruebas y previsualización.

Un único PR hacia develop; sin merge ni auto-merge. Pendiente aprobación del líder técnico y QA manual.
