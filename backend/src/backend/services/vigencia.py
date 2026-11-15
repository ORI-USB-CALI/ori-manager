"""HT-08/HT-17: reglas de vigencia de un convenio y fecha de referencia del dominio.

Vive en un módulo propio porque `renovaciones` importa `convenios`; si
`convenios` importara la fecha del dominio desde `renovaciones` habría un ciclo.
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
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
    """Extremos inclusivos; los inicios en fin de mes conservan fin de mes."""
    destino = sumar_meses(fecha_inicio, duracion_meses)
    if fecha_inicio.day == monthrange(fecha_inicio.year, fecha_inicio.month)[1]:
        return destino.replace(day=monthrange(destino.year, destino.month)[1])
    return destino - timedelta(days=1)


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
    """HT-08: restricciones temporales persistidas.

    La coherencia HT-17 se comprueba solo si el llamador aporta duracion.
    Los historicos se validan sin ese argumento para preservar su convencion.
    El registro de nuevos valores pasa por preparar_vigencia.
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
            CampoFaltante(campo="fecha_vencimiento", motivo=MOTIVO_DURACION_INCOHERENTE)
        )
    return faltantes


def preparar_vigencia(
    inicio: date | None,
    duracion: int | None,
    vencimiento: date | None,
    hoy: date,
) -> tuple[date | None, list[CampoFaltante]]:
    """Valida una entrada nueva y devuelve vencimiento; permite borrador parcial."""
    errores = []
    if duracion is not None and duracion < 4:
        errores.append(
            CampoFaltante(
                campo="duracion_meses", motivo="La duración mínima es de 4 meses"
            )
        )
    if inicio is not None and inicio < hoy:
        errores.append(
            CampoFaltante(
                campo="fecha_inicio", motivo="No puede ser anterior a la fecha actual"
            )
        )
    calculado = vencimiento
    if inicio is not None and duracion is not None and not errores:
        try:
            calculado = vencimiento_esperado(inicio, duracion)
        except (ValueError, OverflowError):
            errores.append(
                CampoFaltante(
                    campo="duracion_meses",
                    motivo="La duración excede el rango de fechas permitido",
                )
            )
        if (
            vencimiento is not None
            and calculado is not None
            and vencimiento != calculado
        ):
            errores.append(
                CampoFaltante(
                    campo="fecha_vencimiento", motivo=MOTIVO_DURACION_INCOHERENTE
                )
            )
    errores.extend(validar_vigencia(inicio, vencimiento, hoy))
    return calculado, errores
