# Centro de documentación — ORI Manager

**Referencia:** revisión de `develop` y exportación de historias de usuario recibida el 13/10/2026. Es un inventario documental, no una certificación operativa.

| Tema | Fuente técnica principal |
|---|---|
| Estado de HU y HT | [Inventario 13/10/2026](product/estado-hu-2026-10-13.md) |
| Sprints | [Sprint 1](sprints/sprint-01.md) · [Sprint 2](sprints/sprint-02.md) · [Sprint 3 en curso](sprints/sprint-03.md) |
| Arquitectura, entornos y acceso | [Arquitectura](architecture/overview.md) |
| Solicitudes y radicación | [HU-11](hu11-solicitudes.md) |
| Consistencia de solicitudes | [HT-01](ht01-validacion.md) |
| Borradores, versiones formales y concurrencia | [HT-13 — Borrador y versionamiento](hu/ht-13-borrador-versionamiento.md), contrato y dependencia con HT-09 |
| Consulta del contenido histórico de convenios | [HT-05 — Versiones históricas](hu/HT-05-consulta-versiones-historicas.md), ocho CA, permisos, compatibilidad y reversión |
| Autoría y ejecución de la auditoría | [HT-09 — Auditoría ampliada](hu/ht-09-auditoria-ampliada.md), responsables, contratos y rollback conservador |
| Código institucional y modo de emisión del documento | [HT-06 — Código del convenio](hu/ht-06-codigo-convenio.md), generación al formalizar, contador anual y exportación en trámite u oficial |
| Base de datos e infraestructura | [Operaciones](operations/README.md) |
| Contribuciones | [Política documental](development/documentation-policy.md) |
| Wiki de GitHub | [Portada preparada](wiki/Home.md), pendiente de publicar |

## Historias técnicas en desarrollo (Sprint 4)

- [HT-05 — Consulta de versiones históricas](hu/HT-05-consulta-versiones-historicas.md) · [PR #159](https://github.com/ORI-USB-CALI/ori-manager/pull/159); depende de HT-13 y no implica aceptación QA ni release.
- [HT-08 — Validación de vigencia de convenios](hu/ht-08-validacion-vigencia.md) · [PR #147](https://github.com/ORI-USB-CALI/ori-manager/pull/147); no implica aceptación QA ni release.
- [HT-06 — Código institucional del convenio](hu/ht-06-codigo-convenio.md) · incidencias [QA #145](https://github.com/ORI-USB-CALI/ori-manager/issues/145) y [QA #136](https://github.com/ORI-USB-CALI/ori-manager/issues/136); no implica aceptación QA ni release.
- [HT-07 — PDF del reporte de convenios activos](hu/ht-07-pdf-reporte-convenios-activos.md) · incidencia [QA #137](https://github.com/ORI-USB-CALI/ori-manager/issues/137); no implica aceptación QA ni release.

- [HT-11 — Legibilidad del reporte web de convenios activos](hu/ht-11-legibilidad-reporte-convenios-activos.md) · [QA #142](https://github.com/ORI-USB-CALI/ori-manager/issues/142); complementa HT-07. Validación visual pendiente de QA.

## Historias terminadas con ficha de referencia

- [HU-01 — Inicio sesion](hu/hu-01-inicio-sesion.md)
- [HU-02 — Gestion roles](hu/hu-02-gestion-roles.md)
- [HU-03 — Usuarios](hu/hu-03-usuarios.md)
- [HU-04 — Aliados](hu/hu-04-aliados.md)
- [HU-05 — Perfil aliado](hu/hu-05-perfil-aliado.md)
- [HU-06 — Convenio base](hu/hu-06-convenio-base.md)
- [HU-07 — Revision solicitudes](hu/hu-07-revision-solicitudes.md)
- [HU-08 — Credenciales](hu/hu-08-credenciales.md)
- [HU-12 — Elaboracion](hu/hu-12-elaboracion.md)
- [HU-13 — Revision juridica](hu/hu-13-revision-juridica.md)
- [HU-14 — Contraparte](hu/hu-14-contraparte.md)
- [HU-15 — Firmas](hu/hu-15-firmas.md)
- [HU-17 — Tablero](hu/hu-17-tablero.md)
- [HU-21 — Observaciones juridicas](hu/hu-21-observaciones-juridicas.md)

## Fuentes de referencia y trazabilidad

**GitHub (`docs/`)** conserva los procedimientos técnicos versionados junto al código. **GitHub Wiki** se utiliza como guía de navegación y enlaces hacia documentos técnicos, no como segunda copia divergente. **Google Drive** alberga planes de release, fichas, actas, aprobaciones y evidencias de negocio.

- [Drive — Gestión de Releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb)
- [Drive — Quality Assurance](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j)

Las pruebas integrales de todo el sistema están previstas al finalizar **Sprint 5**; no deben confundirse con las pruebas de cada HU durante los sprints. Tampoco debe considerarse desplegado algo solo porque esté integrado en `develop`.
