# Manual de usuario — ORI Manager

**Alcance de esta versión:** funciones entregadas en el Sprint 4. Explica cómo usar la navegación de la plataforma, la guía de bienvenida, la ayuda para diligenciar una solicitud, las validaciones del formulario y la acción Volver.

**Dirigido a:** solicitantes internos (personal de la Universidad) y solicitantes externos (entidades aliadas). La sección 6 aplica sobre todo al equipo de la ORI.

> Este manual describe el funcionamiento integrado en `develop`. No reemplaza la aceptación de QA de cada historia ni indica que la función ya esté publicada en producción.

## Contenido

1. [Navegación y encabezado](#1-navegación-y-encabezado)
2. [Guía de bienvenida (onboarding)](#2-guía-de-bienvenida-onboarding)
3. [Ayuda para diligenciar una solicitud](#3-ayuda-para-diligenciar-una-solicitud)
4. [Validación de los datos del formulario](#4-validación-de-los-datos-del-formulario)
5. [Guardar borrador y radicar](#5-guardar-borrador-y-radicar)
6. [Acción Volver en las vistas de convenios](#6-acción-volver-en-las-vistas-de-convenios)
7. [Preguntas frecuentes](#7-preguntas-frecuentes)

---

## 1. Navegación y encabezado

El encabezado aparece en todas las pantallas después de iniciar sesión. Contiene:

- **ORI Manager:** lleva a la página de Inicio.
- **Menú de navegación:** las secciones que su rol tiene permitidas. La sección en la que está queda resaltada.
- **Ayuda** (solo solicitantes): vuelve a mostrar la guía de bienvenida (ver sección 2).
- **Campana de notificaciones:** muestra cuántos asuntos tiene pendientes y abre el centro de notificaciones.
- **Su correo y su rol.**
- **Cerrar sesión.**

### En celular o tablet

En pantallas pequeñas el menú se recoge en un botón con tres rayas (☰).

- Pulse el botón para **abrir** el menú y púlselo otra vez para **cerrarlo**.
- El menú también se cierra al elegir una opción, al pulsar fuera de él o con la tecla **Esc**.
- Su correo, su rol, la campana y Cerrar sesión siguen visibles en cualquier tamaño de pantalla.

### Con teclado

- **Tab** recorre los enlaces y botones del encabezado.
- **Enter** abre un enlace o despliega un grupo del menú.
- **Esc** cierra el submenú o el menú abierto y devuelve el foco al botón que lo abrió.

---

## 2. Guía de bienvenida (onboarding)

Es un recorrido corto que presenta la plataforma a los solicitantes internos y externos.

### Cuándo aparece

- **Se abre sola** la primera vez que entra a la página de Inicio.
- Si la termina o la omite, no se vuelve a abrir sola.
- Puede verla de nuevo cuando quiera con el botón **Ayuda** del encabezado. Si está en otra pantalla, la plataforma lo lleva a Inicio para mostrarla. Al terminar aparece el botón **Volver a la pantalla anterior**.

### Qué explica

1. Qué es ORI Manager.
2. El proceso de un convenio: usted crea y radica la solicitud; la ORI la revisa y puede aceptarla, devolverla para corrección o rechazarla. Si la acepta, se elabora el convenio, se revisa, se aprueba y se firma.
3. Que **radicar una solicitud no significa que el convenio ya exista**: solo inicia el trámite.
4. Los accesos rápidos de Inicio: **Nueva solicitud**, **Mis solicitudes** y, si le corresponde, **Revisiones de contraparte**.
5. El menú de navegación, la campana de notificaciones y el botón Ayuda.

Algunos pasos solo aparecen si su cuenta tiene esa opción. Por ejemplo, Revisiones de contraparte solo se muestra a quien tiene que revisar convenios enviados por la ORI.

### Cómo moverse en el recorrido

| Acción | Botón | Teclado |
|---|---|---|
| Ir al paso siguiente | **Siguiente** | Flecha derecha → |
| Volver al paso anterior | **Anterior** | Flecha izquierda ← |
| Salir del recorrido | **Omitir** o la **X** | **Esc** |
| Terminar | **Finalizar** (en el último paso) | — |

En cada paso se indica en cuál va, por ejemplo "3 de 11".

**La guía solo informa:** no crea, guarda ni radica nada.

---

## 3. Ayuda para diligenciar una solicitud

Dentro del formulario de solicitud hay una guía que explica paso a paso cómo llenarlo.

### Cómo abrirla

1. Abra una solicitud nueva, o una suya en estado **Borrador** o **Devuelta**.
2. Pulse **Ayuda: cómo diligenciar la solicitud**, en la parte superior del formulario.

Esta guía **nunca se abre sola**: usted decide cuándo usarla. Las teclas y los botones son los mismos de la guía de bienvenida (Siguiente, Anterior, Omitir, X, Esc, Finalizar).

### Qué recorre

**Las ocho secciones del formulario:**

1. Información del solicitante.
2. Información de la contraparte.
3. Contacto de contraparte.
4. Información del convenio.
5. Supervisor o encargado de ejecución USB.
6. Supervisor o encargado de ejecución de la contraparte.
7. Documentación.
8. Observaciones adicionales.

**Después, las acciones del formulario:**

- Adjuntar documentos.
- Guardar borrador.
- Radicar la solicitud.
- Cómo corregir errores de validación.
- Corregir una solicitud devuelta. Este paso solo aparece si su solicitud está **Devuelta**.
- Consultar Mis solicitudes.

Las explicaciones se adaptan a su tipo de cuenta. Por ejemplo, al solicitante externo se le explica el tipo de documento y el dígito de verificación; al interno, la Facultad o Dependencia.

### Lo que la guía no hace

- No escribe ni cambia datos del formulario.
- No guarda borradores, no adjunta archivos y no radica.
- Lo que ya había escrito se conserva al abrirla y al cerrarla.

### Una guía a la vez

No pueden estar abiertas al mismo tiempo la guía de bienvenida y la ayuda del formulario. Mientras una está abierta, el botón de la otra aparece desactivado. Para usar la otra, cierre primero la que está abierta.

---

## 4. Validación de los datos del formulario

El formulario revisa el formato de los datos **cuando usted sale de un campo**. Si hay un problema:

- El mensaje aparece **debajo del campo**, explicando qué corregir.
- El campo queda marcado en rojo.
- **No se pierde nada de lo que ya escribió.** Corrija el dato y el mensaje desaparece.

La plataforma vuelve a revisar todo al guardar y al radicar. Si encuentra algo que el formulario no detectó (por ejemplo, un teléfono con el formato correcto pero que no existe en el país indicado), muestra el error junto al campo correspondiente.

### Reglas por tipo de dato

**Identificación** (del solicitante externo y de la contraparte). Primero elija el **tipo de documento**; la regla depende de él:

| Tipo | Qué se acepta | Ejemplo válido |
|---|---|---|
| NIT | De 5 a 10 dígitos, **sin** el dígito de verificación. Puede escribirlo con puntos o espacios; se ignoran. | `900123456` o `900.123.456` |
| Cédula de ciudadanía | De 5 a 10 dígitos. Puntos y espacios se ignoran. | `1.144.000.000` |
| Cédula de extranjería | De 3 a 15 letras o dígitos. | `E1234567` |
| Pasaporte | De 5 a 20 letras o dígitos. | `AB123456` |
| Identificación fiscal extranjera u Otro | De 3 a 40 caracteres: letras, dígitos, espacios, guion, punto o barra, con al menos una letra o dígito. | `B-12345678` |

**Dígito de verificación (solo NIT).** Al elegir NIT aparece un campo aparte, **Dígito de verificación**:

- Escriba **un solo dígito**.
- La plataforma comprueba que coincida con el NIT escrito (cálculo oficial de la DIAN). Si no coincide, aparece "El dígito de verificación del NIT no es correcto".
- No escriba el dígito pegado al NIT (por ejemplo, `900123456-8`). Va en su propio campo.

**Teléfonos.** Aplica a los cuatro teléfonos del formulario: el de la contraparte, el del contacto y los de los dos supervisores.

- Números de Colombia: escríbalos sin indicativo, por ejemplo `602 555 1234` o `310 123 4567`.
- Números de otro país: incluya el indicativo con `+`, por ejemplo `+34 912 345 678`.
- Puede usar espacios, paréntesis, puntos o guiones.
- Para una extensión, escriba `ext`, `extensión` o `x` seguido de 1 a 6 dígitos, por ejemplo `602 555 1234 ext 123`.
- No se aceptan letras en el número.

**País.** Se elige de la lista. No se escribe a mano.

**Ciudad.** Se escribe a mano:

- De 2 a 120 caracteres.
- Debe empezar con una letra.
- Solo letras, espacios, guion, punto o apóstrofo.

La plataforma **no comprueba** que la ciudad pertenezca al país elegido; revise que esté bien escrita.

**Dirección.**

- De 5 a 200 caracteres, con al menos una letra.
- Debe tener **un número**, **o** al menos dos referencias separadas por coma o barra.
- Signos permitidos: `# - . , / ° º ( ) '`.

Se aceptan direcciones urbanas, rurales e internacionales, por ejemplo:

- `Calle 5 # 38-25`
- `Cra. 122 No. 6-65, Pance`
- `Vereda La Esperanza, Finca El Roble`
- `Km 3 vía Cali/Jamundí`
- `1600 Amphitheatre Pkwy`

Un texto como "Campus universitario" solo no es suficiente; agregue una referencia: "Campus universitario, Pance". Que la dirección tenga un formato válido no significa que la plataforma haya comprobado que el lugar existe.

---

## 5. Guardar borrador y radicar

| | Guardar borrador | Radicar solicitud |
|---|---|---|
| ¿Para qué? | Conservar lo avanzado y seguir después. | Presentar formalmente la solicitud a la ORI. |
| ¿Exige todos los campos? | No. Puede guardar con campos vacíos. | Sí. Todos los campos marcados con `*` y al menos un documento de representación legal de la contraparte. |
| ¿Revisa el formato? | Sí, de los campos que haya llenado. | Sí, de todos. |
| ¿Cambia el estado? | No; la solicitud sigue editable. | Sí, pasa a **Radicada**. |

Si al radicar falta algo o hay un dato inválido:

- La solicitud **no se radica**.
- Sigue editable y los campos con problema quedan marcados.

Si la ORI **devuelve** su solicitud:

1. Lea las observaciones de devolución.
2. Corrija lo indicado.
3. Pulse **Guardar cambios** y después **Volver a radicar**. Se aplican las mismas reglas de este manual.

Los documentos se adjuntan en la sección **Documentación**: archivos PDF, JPG o PNG de hasta 10 MB.

---

## 6. Acción Volver en las vistas de convenios

En las pantallas de convenios hay un botón **Volver** al principio de la pantalla:

- Detalle del convenio.
- Elaboración.
- Historial.
- Versiones anteriores.
- Documento aprobado para firma.

**Cómo funciona:**

- Lo regresa a la pantalla de la que vino, aunque haya pasado por varias. Por ejemplo, Renovaciones → Detalle → Elaboración: desde Elaboración vuelve al Detalle, y desde el Detalle vuelve a Renovaciones.
- En **Revisiones jurídicas**, los filtros quedan en la dirección de la página. Al volver, recargar o compartir el enlace se conservan.
- Si abrió la pantalla directamente (por ejemplo, desde un enlace), Volver lo lleva a una pantalla de partida según su rol, como el Tablero o la Consulta de convenios.

---

## 7. Preguntas frecuentes

**La guía de bienvenida no se abrió sola.**
Solo se abre la primera vez que entra a Inicio. Si ya la terminó o la omitió, ábrala con **Ayuda**.

**Aparece "No se pudo consultar el estado de la guía" o "No se pudo guardar el estado de la guía".**
Puede seguir usando la plataforma normalmente. Use el botón **Reintentar** que aparece junto al mensaje.

**El botón de una de las guías está desactivado.**
Hay otra guía abierta. Ciérrela con **Omitir**, la **X** o **Esc**.

**Las flechas del teclado no cambian el paso.**
Espere a que termine la animación del paso actual (menos de medio segundo) y vuelva a intentarlo.

**Me dice que el dígito de verificación no es correcto.**
Revise el NIT y el dígito. El NIT va sin el dígito, y el dígito va en su propio campo.

**Mi teléfono internacional no se acepta.**
Escríbalo con `+` y el indicativo del país. Sin `+`, la plataforma lo interpreta como un número de Colombia.

**No puedo radicar.**
Revise los campos marcados en rojo y los que tienen `*`. Confirme también que adjuntó al menos un documento de representación legal de la contraparte.
