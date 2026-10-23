"""HT-08: reglas de vigencia de un convenio y fecha de referencia del dominio.

Vive en un módulo propio porque `renovaciones` importa `convenios`; si
`convenios` importara la fecha del dominio desde `renovaciones` habría un ciclo.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.schemas.convenio import CampoFaltante

ZONA_HORARIA_DOMINIO = ZoneInfo("America/Bogota")

MOTIVO_VENCIMIENTO_PASADO = "No puede ser anterior a la fecha actual"
MOTIVO_INICIO_POSTERIOR = "Debe ser igual o posterior a la fecha de inicio"


def fecha_actual_dominio() -> date:
    return datetime.now(ZONA_HORARIA_DOMINIO).date()


def validar_vigencia(
    fecha_inicio: date | None, fecha_vencimiento: date | None, hoy: date
) -> list[CampoFaltante]:
    """Indica qué corregir en la vigencia. Sin efectos secundarios.

    Solo valida lo informado: las fechas siguen siendo opcionales (decisión
    HT-08, no las exigen los CA).

    - CA-01: un vencimiento anterior a `hoy` no es válido; vencer hoy sí.
    - CA-02/CA-03: el inicio puede ser igual al vencimiento. Esto relaja la regla
      previa de HU-12, que exigía vencimiento estrictamente posterior al inicio
      (decisión HT-08 siguiendo el CA-03 literal; señalada en el PR).
    """
    faltantes: list[CampoFaltante] = []
    if fecha_vencimiento is None:
        return faltantes
    if fecha_vencimiento < hoy:
        faltantes.append(
            CampoFaltante(campo="fecha_vencimiento", motivo=MOTIVO_VENCIMIENTO_PASADO)
        )
    if fecha_inicio is not None and fecha_inicio > fecha_vencimiento:
        faltantes.append(
            CampoFaltante(campo="fecha_vencimiento", motivo=MOTIVO_INICIO_POSTERIOR)
        )
    return faltantes
