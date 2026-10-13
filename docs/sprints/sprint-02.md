# Sprint 2 — Operatividad

**Estado:** Completado según exportación del backlog (13/10/2026). **13 entradas terminadas: 8 HU y 5 registros FIX.** Los FIX no se cuentan como cinco capacidades de negocio adicionales.

| Clase | Registros `Terminado` |
|---|---|
| HU base | HU-07 revisión de solicitud · HU-08 gestión de credenciales · HU-11 registro/radicación · HU-12 elaboración · HU-13 revisión jurídica · HU-14 contraparte · HU-15 revisión final y firmas · HU-17 tablero |
| Correcciones FIX | FIX HU-07 · FIX HU-12 · FIX HU-13 · FIX HU-14 · FIX HU-15 |

## Recorrido funcional implementado

1. Solicitante interno/externo crea una solicitud, adjunta soporte y radica.
2. La ORI revisa, devuelve para subsanar o acepta y habilita la elaboración.
3. El convenio se elabora y se versiona antes de revisión jurídica.
4. Dos instancias jurídicas tramitan decisiones y observaciones con control de versiones.
5. Se gestiona revisión de contraparte y respuestas.
6. Se gestiona revisión final y proceso de firmas.
7. El tablero operativo presenta avances de convenios a usuarios autorizados.

El archivo `backend/tests/test_e2e_flujo_canonico_sprint2.py` valida el flujo **por APIs**; no significa que las integraciones externas o el sistema completo hayan superado la aceptación institucional. [Contrato HU-11](../hu11-solicitudes.md).

## Despliegue técnico R0

El 07/10/2026 se fusionó [PR #108](https://github.com/ORI-USB-CALI/ori-manager/pull/108) hacia `main`. [CI](https://github.com/ORI-USB-CALI/ori-manager/actions/runs/37651528077) y [CodeQL](https://github.com/ORI-USB-CALI/ori-manager/actions/runs/37651528072) fueron exitosos. El hito R0 es técnico; no certifica activación con datos reales ni aceptación de la ORI. El registro histórico formal está en [Drive — Gestión de Releases](https://drive.google.com/drive/folders/1TwlYItxGI0bYmJ6nxw6Ggk0Sbc08cRdb).

## Evidencias

- [QA Sprint 2 (Drive)](https://drive.google.com/drive/folders/1KBvjN5nSYUkOsWl-t83OXS9EL-MTIKn5)
- [Estado oficial exportado](../product/estado-hu-2026-10-13.md)

**No asumir** que firmar implica archivar: HU-16 está `Sin iniciar` en Sprint 5 y no integra R1.
