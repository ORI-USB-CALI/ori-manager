# Centro de notificaciones HU-30 / HU-33

La integración se limita al frontend. No cambia servicios, endpoints, permisos,
persistencia, migraciones ni el protocolo WebSocket del backend.

## Representación y composición

- `components/notificaciones/avisos.ts` define la unión discriminada `Aviso`,
  los adaptadores explícitos y la configuración de categorías. Las acciones
  tienen lectura persistida; los vencimientos calculados carecen de ella y no
  reciben una fecha de creación artificial. La fecha relevante distingue fecha
  de vencimiento de instante de recepción.
- `pages/centroNotificaciones.ts` compone las consultas existentes y agrega
  exclusivamente fuentes autorizadas. Las claves de caché permanecen iguales.
- `CentroNotificaciones` filtra las fuentes y presenta carga, errores parciales
  y vacíos por categoría. `AvisoNotificacion` representa todos los elementos.
- `AppLayout` monta una sola `BandejaNotificaciones` y mantiene la suscripción
  HU-33 existente. El contador suma asuntos sin resolver y vencimientos activos;
  no cuenta mensajes sin leer. Los IDs incluyen el origen y se deduplican antes
  de representar o contar.

Para añadir una categoría, ampliar la unión `Aviso`, añadir su configuración en
`CATEGORIAS_AVISOS`, escribir su adaptador e incorporar su consulta autorizada a
las fuentes de `useCentroNotificaciones` y al refresco. El filtro y el listado
compartido la presentan sin crear otra campana ni otro panel.

## Comportamiento preservado

HU-30 sigue consultando `/convenios/alertas-vencimiento`. El servidor conserva el
cálculo dinámico y sus exclusiones por estado, renovación activa y decisión de
no renovar. El adaptador conserva los cuatro rangos de 0 a 120 días inclusive y
descarta defensivamente resultados fuera de la ventana. El destino principal es
la gestión de renovaciones del convenio.

Los datos se consultan al abrir o actualizar el Centro, montar la consulta,
regresar a la aplicación y recuperar conectividad. Una consulta periódica cada
minuto mientras la aplicación está visible recupera cambios del servidor al
avanzar el tiempo. No se calcula ni persiste una segunda versión de las reglas
de negocio en el cliente.

Inicio usa la misma consulta y adaptador para mostrar el total y hasta tres
próximos vencimientos con sus fechas, días restantes y enlaces de renovación.
El resumen y la categoría requieren `convenios.ver_alertas_vencimiento`; sin
ese permiso tampoco se consulta el endpoint, incluyendo el refresco manual.

HU-33 conserva las consultas personales, los cuatro tipos y sus rutas existentes.
Marcar como leída llama únicamente al PATCH de lectura. Las acciones resueltas
siguen visibles como atendidas y no incrementan el contador, independientemente
de su lectura. El WebSocket sigue invalidando la consulta al recibir eventos y
al conectar, recuperando también cambios ocurridos durante una desconexión.

## Validación

`CentroNotificaciones.test.tsx` conserva las aserciones existentes de HU-33,
adaptando el montaje al contrato de fuentes y el texto vacío aprobado.
`CentroNotificacionesUnificado.test.tsx` cubre integración con AppLayout e Inicio,
permisos de los cinco roles, agregación sin duplicados, límites de los cuatro
rangos, filtros, lectura independiente de resolución, rutas, refresco al abrir,
regresar y avanzar el tiempo, eventos WebSocket, errores parciales, vacíos y
navegación por teclado con cierre y recuperación del foco.

No se modifican los módulos de HU-10, HU-18, HT-02 ni HU-20. Sus pruebas frontend
se incluyen en la suite completa. No se requiere ejecutar la suite backend al
mantener intactos sus contratos y código.
