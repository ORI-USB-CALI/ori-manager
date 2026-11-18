> **Fuente de la portada de la GitHub Wiki.** Este archivo prepara el contenido de `Home.md` de la wiki (repositorio `ori-manager.wiki`); no se publica solo. Los enlaces que empiezan con `./` solo funcionan dentro de la wiki.

# ORI Manager — Wiki

Bienvenido a la wiki de **ORI Manager**, el sistema de gestión y trazabilidad de convenios de la Oficina de Relaciones Internacionales (ORI) de la Universidad de San Buenaventura Cali.

> **Esta wiki es un directorio, no una copia.** La documentación vive en la carpeta [`docs/`](https://github.com/ORI-USB-CALI/ori-manager/tree/main/docs) del repositorio, junto al código, y allí se mantiene. Aquí solo se enlaza para encontrarla.
> Ningún documento de esta wiki ni de `docs/` contiene credenciales: las variables de entorno se citan por nombre, nunca por valor.

## Soy de la ORI: quiero usar el sistema

| Qué necesito | Dónde está |
|---|---|
| Aprender a usar la plataforma paso a paso | [Manual de usuario](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/manual-usuario.md) |
| Ver el flujo completo en video (15 min) | [Video tutorial](https://drive.google.com/file/d/1JG-D8WC7pb1cnFA5vYG4QW4Y8gUik1GR/view?usp=drivesdk) |
| Revisar un convenio como contraparte, sin cuenta | Se entra con un enlace individual con token. Ver [HU-14 — Revisión de la contraparte](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/hu/hu-14-contraparte.md) |
| Firmar un convenio, sin cuenta | Se entra con un enlace individual con token. Ver [HU-15 — Revisión final y firmas](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/hu/hu-15-firmas.md) |
| Saber qué historias están terminadas | [Estado de las historias de usuario](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/product/estado-hu-2026-10-13.md) |

## Soy de TI: quiero instalar, desplegar u operar el sistema

| Qué necesito | Dónde está |
|---|---|
| Instalar el sistema desde cero | [Manual técnico e instalación](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/manual-tecnico-instalacion.md) |
| Crear la base de datos (estructura sin datos) | [Script de base de datos](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/base-de-datos/README.md) |
| Entender cómo está armado | [Arquitectura](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/architecture/overview.md) |
| Configurar la base en la nube | [Supabase](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/supabase.md) |
| Publicar una versión en producción | [Runbook de producción](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/production-release.md) |
| Ver todos los manuales operativos | [Manuales operativos](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/README.md) |
| Recibir el código y los accesos | [Transferencia técnica](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/operations/transferencia-tecnica.md) |
| Código fuente | [Backend](https://github.com/ORI-USB-CALI/ori-manager/tree/main/backend) · [Frontend](https://github.com/ORI-USB-CALI/ori-manager/tree/main/frontend) |

## Soy del equipo de desarrollo

- [Lineamientos de desarrollo](./lineamientos-desarrollo)
- [Instalación del entorno de desarrollo en Windows](./Instalación-del-entorno-de-desarrollo)
- [Lineamientos Testing](./lineamientos-testing)
- [Política de documentación continua](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/development/documentation-policy.md)
- [Centro documental](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/README.md): índice de historias de usuario, historias técnicas y sprints.
- Sprints: [Sprint 1](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/sprints/sprint-01.md) · [Sprint 2](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/sprints/sprint-02.md) · [Sprint 3](https://github.com/ORI-USB-CALI/ori-manager/blob/main/docs/sprints/sprint-03.md)

## Evidencias y releases (Google Drive)

- [Gestión de releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb): planes, fichas, actas y decisiones.
- [Quality Assurance](https://drive.google.com/drive/folders/12aOj3os-8IVkqfuDmK2E85NWJABSQg8j): evidencias de pruebas.

---

**Cómo leer los estados:** una historia en `Pruebas` no es `Terminado` solo porque su código esté en `develop`. Para saber qué está publicado, consultar la rama `main` y el registro del release correspondiente.
