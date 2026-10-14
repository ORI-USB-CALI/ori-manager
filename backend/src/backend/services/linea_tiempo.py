from datetime import date

from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.schemas.convenio import HitoLineaTiempoLeer


def construir_linea_tiempo(convenio: Convenio, hoy: date) -> list[HitoLineaTiempoLeer]:
    """HU-20: hitos del convenio en orden cronológico.

    El orden sale de la construcción: la elaboración precede a la activación,
    que solo ocurre al completar firmas, y esta precede al vencimiento.
    """
    hitos: list[HitoLineaTiempoLeer] = []
    if convenio.elaboracion_iniciada_en is not None:
        hitos.append(
            HitoLineaTiempoLeer(
                codigo="INICIO_ELABORACION",
                nombre="Inicio de elaboración",
                fecha=convenio.elaboracion_iniciada_en,
                estado="COMPLETADO",
            )
        )
    if convenio.activado_en is not None:
        hitos.append(
            HitoLineaTiempoLeer(
                codigo="ACTIVACION",
                nombre="Activación",
                fecha=convenio.activado_en,
                estado="COMPLETADO",
            )
        )
    elif convenio.estado == EstadoConvenio.EN_TRAMITE.value:
        hitos.append(
            HitoLineaTiempoLeer(
                codigo="ACTIVACION", nombre="Activación", fecha=None, estado="PENDIENTE"
            )
        )
    nunca_vigente = (
        convenio.activado_en is None
        and convenio.estado == EstadoConvenio.CANCELADO.value
    )
    if convenio.fecha_vencimiento is not None and not nunca_vigente:
        hitos.append(
            HitoLineaTiempoLeer(
                codigo="VENCIMIENTO",
                nombre="Vencimiento",
                fecha=convenio.fecha_vencimiento,
                estado="PROGRAMADO" if convenio.fecha_vencimiento > hoy else "COMPLETADO",
            )
        )
    return hitos
