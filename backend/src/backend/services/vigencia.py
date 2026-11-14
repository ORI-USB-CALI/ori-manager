"""HT-08/HT-17: reglas de vigencia de un convenio y fecha de referencia del dominio.

Vive en un módulo propio porque `renovaciones` importa `convenios`; si
`convenios` importara la fecha del dominio desde `renovaciones` habría un ciclo.
"""

from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.schemas.convenio import CampoFaltante

ZONA_HORARIA_DOMINIO = ZoneInfo("America/Bogota")

MOTIVO_VENCIMIENTO_PASADO = "No puede ser anterior a la fecha actual"
MOTIVO_INICIO_POSTERIOR = "Debe ser igual o posterior a la fecha de inicio"
MOTIVO_DURACION_INCOHERENTE = (
    "No coincide con la fecha de inicio y la duración en meses"
)


def instante_actual_dominio() -> datetime:
    """Instante actual con la zona del dominio.

    Lo usa quien necesita un único punto de referencia temporal para toda una
    operación: la fecha que persiste y el año que deriva de ella salen de la
    misma lectura del reloj, así que no pueden caer a cada lado de un cambio
    de año.
    """
    return datetime.now(ZONA_HORARIA_DOMINIO)


def fecha_actual_dominio() -> date:
    return instante_actual_dominio().date()


def sumar_meses(fecha: date, meses: int) -> date:
    """HT-17: suma meses calendario; si el día no existe en el mes de llegada
    se usa el último día de ese mes (31/01 + 1 mes = 28/02 o 29/02)."""
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    return date(anio, mes, min(fecha.day, monthrange(anio, mes)[1]))


def vencimiento_esperado(fecha_inicio: date, duracion_meses: int) -> date:
    """HT-17: vencimiento que corresponde a un inicio y una duración.

    Convención "mismo día del mes": 01/01/2027 con 12 meses vence el
    01/01/2028. El vencimiento sigue siendo inclusivo para la vigencia (HT-10).
    """
    return sumar_meses(fecha_inicio, duracion_meses)


def _vencimiento_coincide(
    fecha_inicio: date, fecha_vencimiento: date, duracion_meses: int
) -> bool:
    try:
        return fecha_vencimiento == vencimiento_esperado(fecha_inicio, duracion_meses)
    except (ValueError, OverflowError):
        # Una duración que sale del rango de fechas no puede coincidir con un
        # vencimiento real; se reporta como incoherente en vez de fallar con 500.
        return False


def validar_vigencia(
    fecha_inicio: date | None,
    fecha_vencimiento: date | None,
    hoy: date,
    *,
    duracion_meses: int | None = None,
) -> list[CampoFaltante]:
    """Indica qué corregir en la vigencia. Sin efectos secundarios.

    Solo valida lo informado: las fechas siguen siendo opcionales (decisión
    HT-08, no las exigen los CA).

    - CA-01: un vencimiento anterior a `hoy` no es válido; vencer hoy sí.
    - CA-02/CA-03: el inicio puede ser igual al vencimiento. Esto relaja la regla
      previa de HU-12, que exigía vencimiento estrictamente posterior al inicio
      (decisión HT-08 siguiendo el CA-03 literal; señalada en el PR).
    - HT-17: la duración es referencial y se valida, no se calcula. Si vienen
      inicio, vencimiento y una duración positiva, el vencimiento debe ser
      `vencimiento_esperado(inicio, duración)` (mismo día del mes). Si falta alguno, no se valida.
      No se restringen fechas retroactivas ni periodos cortos (HT-17 CA-03).
    """
    faltantes: list[CampoFaltante] = []
    if fecha_vencimiento is None:
        return faltantes
    if fecha_vencimiento < hoy:
        faltantes.append(
            CampoFaltante(campo="fecha_vencimiento", motivo=MOTIVO_VENCIMIENTO_PASADO)
        )
    if fecha_inicio is None:
        return faltantes
    if fecha_inicio > fecha_vencimiento:
        faltantes.append(
            CampoFaltante(campo="fecha_vencimiento", motivo=MOTIVO_INICIO_POSTERIOR)
        )
    elif duracion_meses and not _vencimiento_coincide(
        fecha_inicio, fecha_vencimiento, duracion_meses
    ):
        # Con el inicio posterior ya se reporta un error sobre el mismo campo;
        # sumarle la incoherencia solo repetiría el aviso.
        faltantes.append(
            CampoFaltante(
                campo="fecha_vencimiento", motivo=MOTIVO_DURACION_INCOHERENTE
            )
        )
    return faltantes
