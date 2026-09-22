# HU-11 — contrato de solicitudes radicadas

## Decisiones de dominio

`SolicitudConvenio` sigue siendo la única entidad de solicitud. Crear o radicar una
solicitud no crea `Convenio` ni `Aliado`. La contraparte permanece en los campos
`*_aliado_propuesto`; su resolución posterior conserva el contrato de HU-04.

El tipo y la identidad del solicitante se toman siempre de la sesión. La FK
`solicitante_id` es inmutable y mantiene la identidad canónica. Nombre, correo,
identificación, cargo, entidad, facultad/dependencia y programa/unidad se
precargan desde el perfil como campos `solicitante_*`; pueden corregirse en el
borrador sin cambiar ownership y quedan congelados al radicar.

Para internos, la estructura organizacional canónica determina la precarga y la
obligatoriedad: un `PROGRAMA` guarda el programa y su unidad padre cuando existe;
una `FACULTAD` o `UNIDAD_ADMINISTRATIVA` solo requiere `solicitante_unidad`. No se
inventa un programa cuando no aplica. Sin unidad canónica se exige que el borrador
aporte al menos una unidad o programa aplicable.

La única transición implementada es `BORRADOR -> RADICADA`. Una solicitud
radicada no admite edición ni cambios documentales desde estos endpoints.
`fecha_radicacion` y `fecha_recibido_ori` reciben el mismo instante UTC porque la
plataforma recibe la solicitud al radicar. `aprobada_por_director` y
`fecha_aprobacion_director` se preservan como legacy, sin crear aprobación ni una
transición adicional.

## Correspondencia con la plantilla oficial

La institución propuesta conserva identidad digital para HU-04 y añade país,
ciudad, teléfono y dirección. El correo `correo_aliado_propuesto` es el correo
institucional; `contacto_contraparte_correo` pertenece a la persona de contacto.
El contacto incluye nombre, cargo, teléfono y correo. Los responsables ya no se
guardan en texto libre: existen cuatro campos para supervisor USB y cuatro para
supervisor de la contraparte (nombre, cargo, teléfono y correo).

El catálogo oficial se siembra idempotentemente con MARCO, ESPECIFICO,
PRACTICA_INTERNACIONAL, INVESTIGACION, PLAN_BENEFICIOS y OTRO. `naturaleza`
queda nullable: solo MARCO y ESPECIFICO conservan naturaleza homónima; no se
clasifican artificialmente las otras cuatro opciones.
El seed usa `ON CONFLICT DO NOTHING`: nunca modifica nombre, estado, descripción
ni naturaleza de tipos preexistentes. El marcador técnico solo se asigna a filas
realmente insertadas por HU-11 y permite retirarlas selectivamente al degradar.

## Documentos

`documento_solicitud` guarda metadata y una `clave_objeto` opaca; no guarda el
archivo. `AlmacenDocumentos` es el puerto sustituible. El adaptador de desarrollo
`AlmacenDocumentosLocal` genera rutas exclusivamente desde claves internas,
nunca desde nombres aportados por usuarios. Admite PDF, JPG y PNG hasta 10 MB.

El catálogo incluye Cámara de Comercio, RUT, cédula del representante legal,
otro documento de representación y otros soportes. La regla central exige al
menos un documento clasificado en `TIPOS_DOCUMENTO_REPRESENTACION`; no exige
simultáneamente Cámara + RUT + cédula ni aplica una matriz legal inventada.

En desarrollo se usa `DOCUMENT_STORAGE_PROVIDER=local` (valor por defecto) y
`DOCUMENT_STORAGE_PATH` define la ubicación. El adaptador local solo se habilita
con `APP_ENV=development`.

Staging y producción usan `DOCUMENT_STORAGE_PROVIDER=microsoft_graph` con
Microsoft Graph AppFolder y el permiso delegado `Files.ReadWrite.AppFolder`. La
configuración requiere estas variables, sin valores por defecto secretos:

- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_REFRESH_TOKEN`
- `MICROSOFT_STORAGE_ROOT` (`staging` o `production`)

Los objetos quedan bajo `Apps/ORI Manager Storage/{MICROSOFT_STORAGE_ROOT}/`.
Una configuración incompleta o inválida falla explícitamente y nunca cae al
filesystem local. La integración usa temporalmente una cuenta Microsoft personal
dedicada y un refresh token delegado. Una futura integración institucional podrá
migrarse sin cambiar `ServicioSolicitudes` gracias al puerto
`AlmacenDocumentos`.

Crear, editar, listar y consultar solicitudes operan únicamente con metadata y no
resuelven el adaptador físico. Subir, eliminar y radicar sí lo requieren.

## Contrato para HU-07

HU-07 debe consumir solicitudes con `estado = RADICADA`, `fecha_radicacion` y
`fecha_recibido_ori` no nulas. No debe inferir aprobación de la radicación. Los
endpoints HU-11 son:

- `GET /api/solicitudes/catalogos`
- `POST /api/solicitudes`
- `PATCH /api/solicitudes/{id}`
- `GET /api/solicitudes/mias`
- `GET /api/solicitudes/{id}`
- `POST /api/solicitudes/{id}/documentos`
- `DELETE /api/solicitudes/{id}/documentos/{documento_id}`
- `POST /api/solicitudes/{id}/radicar`

En HU-11 la visibilidad se limita estrictamente a solicitudes cuyo
`solicitante_id` corresponde al usuario autenticado. La tabla
`solicitud_usuario` se conserva para un posible uso futuro, pero no concede
acceso de lectura en esta HU. Los permisos son `solicitudes.crear`,
`solicitudes.ver_propias`,
`solicitudes.editar_propias` y `solicitudes.radicar`. No se definieron permisos ni
transiciones de revisión ORI.
