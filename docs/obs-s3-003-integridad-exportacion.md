# OBS-S3-003: auditoria y criterio de emision

La auditoria previa identifica en ServicioPdfConvenio el DTO compartido con Excel:
- Convenio actual: tipo, objeto, alcance, unidad, finanzas, fechas, duracion, codigo, estado y avance.
- Solicitud actual: justificacion, solicitante, contactos y contraparte propuesta si falta aliado.
- VersionConvenio: exclusivamente contenido; snapshot_metadata era ignorado.

_snapshot_de congela IDs de tipo/unidad, objeto, alcance, finanzas, vigencia,
duracion y (en snapshots recientes) identidad juridica del aliado. No congela
nombres de catalogos, estado, avance ni fecha de firma. Codigo y aliado pueden
ser nulos antes de formalizar. Se respetan claves presentes, incluso nulas;
claves ausentes conservan la lectura historica desde Convenio, nunca desde
la solicitud para completar condiciones. Los nombres de catalogos se resuelven
por el ID congelado. La identidad congelada prevalece sobre el catalogo actual.

expandir_plantilla sustituye placeholders por texto, y validar_contenido no
admite marcas de procedencia. La plantilla tampoco tiene revisiones inmutables.
Por ello no se autoriza borrar ni corregir clausulas aprobadas. Se reconoce
unicamente la estructura completa de la precarga original HU-12: los 23 bloques,
tipos, niveles y todos los literales fijos, con valores variables donde habia
placeholders. No basta un titulo, una palabra ni el numero de bloques. Si esa
estructura se conserva (incluso con clausulas anadidas), se rechaza la emision
oficial completa mediante el 422 de HU-24. Tambien se rechaza si no hay mas texto:
no es posible certificar contenido juridico suficiente eliminando antecedentes.
No se elimina ningun bloque. El borrador conserva la precarga editable y su marca.

Limite: un texto libre o una plantilla historica profundamente reestructurada no
admite deteccion semantica automatica de contradicciones. Las coincidencias
parciales o palabras genericas no se consideran prueba de procedencia. No se
pretende certificar juridicamente cualquier texto libre. Para las versiones
rechazadas hace falta una decision juridica sobre una nueva version mediante
las revisiones existentes, o sobre otro procedimiento explicitamente autorizado;
no basta sustituir cifras en la version firmada. No se implementa prevencion en
el editor porque exigiria anadir procedencia persistida/cambiar el flujo.

Sin aliado consolidado ni identidad congelada, una contraparte solo propuesta no
satisface entidad_participante en un oficial. Esa propuesta sigue disponible en borradores.

En el DTO oficial se deja de trasladar la justificacion y los contactos propuestos
de solicitud como condiciones o contactos contractuales. El texto libre aprobado
permanece integro. Los datos del solicitante y consecutivo conservan trazabilidad.

Validacion local: 122 pruebas dirigidas aprobadas (regresiones OBS-S3-003, HU-24,
PDF/Excel, seguridad y borradores; dos casos HU-12 y uno HT-15). Las pruebas
observan solo SELECT durante la exportacion y comparan contenido, snapshot y
auditoria tras el rechazo. No se ejecutaron migraciones ni operaciones externas.
