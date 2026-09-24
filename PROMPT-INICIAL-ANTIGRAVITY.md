# Prompt inicial — Google Antigravity — ORI Manager

Estoy trabajando en **ORI Manager**.

Debes seguir las instrucciones del `AGENTS.md` disponible en la raíz del proyecto y utilizar las Skills de `.agents/skills/` cuando sean pertinentes.

Para esta tarea, la fuente de verdad funcional es la Historia de Usuario, tarea y criterios de aceptación que proporcionaré a continuación.

Antes de modificar archivos:

1. revisa completamente la tarea y sus criterios;
2. revisa el estado relevante del repositorio;
3. identifica decisiones funcionales faltantes o contradicciones;
4. no amplíes el alcance;
5. no agregues dependencias sin justificarlo y solicitar aprobación;
6. no ejecutes operaciones destructivas;
7. no hagas commit, push, PR, merge o despliegues sin autorización explícita;
8. si el cambio no es trivial, presenta primero un plan breve.

Al finalizar, informa:

- cambios realizados;
- archivos modificados;
- pruebas ejecutadas;
- resultados;
- criterios cubiertos;
- riesgos;
- pendientes;
- acciones humanas necesarias.

## TAREA 1: Vista de Revisión Final (Gestor ORI)

- Crear la pantalla donde el Gestor ORI compara la versión aprobada por la contraparte y revisa que los documentos estén completos.
- Incluir un botón/modal para "Devolver con observaciones" si hay algo por corregir.
- Deshabilitar el botón "Iniciar Firmas" si hay observaciones sin resolver.

## TAREA 2: Pantalla de Seguimiento de Firmas

- Diseñar la lista con los 7 firmantes mostrando su estado (Pendiente / Firmado).
- Botón para ejecutar la firma electrónica.
- Botón/Formulario para subir el documento PDF escaneado con las firmas físicas.

## DATO IMPORTANTE: AlGUNOS CRITERIOS NO ESTA AUN RELACIONADOS CON LA TAREAS ACTUALES, IGUAL TE LOS DEJO PARA QUE LOS TENGAS EN CUENTA
## CRITERIOS DE ACEPTACIÓN
 

El **Gestor ORI gestiona el proceso**; el **Administrador ORI es uno de los firmantes**, junto con el Revisor ORI, Vicerrectoría Financiera, Vicerrectoría Académica, Secretaría, Rector y el representante correspondiente de la parte solicitante. 

---

CA-01 — Iniciar revisión final

Scenario: Iniciar la revisión final de un convenio

Given que la contraparte ha aprobado el convenio
And el Gestor ORI tiene permisos para gestionar el trámite
When accede a la revisión final
Then el sistema debe mostrar la versión aprobada por la contraparte
And debe permitir verificar la información y documentos correspondientes
And no debe iniciar todavía el proceso de firmas

CA-02 — Impedir firmas con revisiones pendientes

Scenario: Intentar iniciar firmas con observaciones pendientes

Given que existen observaciones o revisiones pendientes sobre el convenio
When el Gestor ORI intenta iniciar el proceso de firmas
Then el sistema debe impedir la operación
And debe mantener el convenio fuera del proceso de firmas
And debe indicar que existen asuntos pendientes de resolución

**CA-03 — Devolver el convenio desde la revisión final**

Scenario: Detectar una inconsistencia durante la revisión final

Given que el convenio se encuentra en revisión final
When se identifica una información o modificación que debe corregirse
Then el sistema debe permitir registrar la observación
And debe devolver el convenio al responsable correspondiente
And no debe permitir iniciar las firmas hasta resolver la situación

CA-04 — Aprobar el convenio para iniciar firmas

Scenario: Completar satisfactoriamente la revisión final

Given que la versión final corresponde con la versión aprobada
And no existen observaciones o revisiones pendientes
When el Gestor ORI confirma la finalización de la revisión
Then el sistema debe registrar que el convenio está preparado para firmas
And debe conservar la versión aprobada para el proceso de firma
And debe registrar la actuación en la trazabilidad

CA-05 — Registrar los siete firmantes

Scenario: Configurar los firmantes requeridos

Given que el convenio fue aprobado para iniciar firmas
When el sistema prepara el proceso de firma
Then debe registrar los seis firmantes institucionales obligatorios
And debe registrar el séptimo firmante de acuerdo con el tipo de solicitante
And el convenio debe tener exactamente siete firmantes requeridos

CA-06 — Registrar firma electrónica

Scenario: Registrar una firma electrónica

Given que un firmante tiene una firma pendiente
When se registra su firma electrónica
Then el sistema debe identificar al firmante
And debe registrar la fecha y hora
And debe actualizar el estado de su firma
And debe asociar la firma al convenio correspondiente

CA-07 — Registrar proceso de firma física

Scenario: Gestionar firmas realizadas físicamente

Given que el convenio se encuentra aprobado para firmas
When las firmas se realizan mediante modalidad física
Then el sistema debe permitir disponer del documento aprobado para su firma
And debe permitir cargar posteriormente el documento firmado
And el documento cargado debe quedar asociado al convenio

CA-08 — Consultar estado de las firmas

Scenario: Consultar el avance del proceso de firmas

Given que el convenio se encuentra en proceso de firmas
When el Gestor ORI consulta el convenio
Then el sistema debe mostrar los siete firmantes requeridos
And debe mostrar el estado de firma de cada uno
And no debe considerar completamente firmado el convenio mientras exista al menos una firma pendiente

CA-09 — Proteger la versión aprobada para firma

Scenario: Intentar modificar un convenio aprobado para firma

Given que existe una versión del convenio aprobada para el proceso de firmas
When se intenta realizar una modificación sustancial sobre dicha versión
Then el sistema no debe modificarla silenciosamente
And debe registrar el cambio requerido
And debe exigir que el convenio vuelva a las revisiones correspondientes antes de continuar con las firmas