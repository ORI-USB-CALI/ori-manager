"""Datos validos para escenarios nuevos que avanzan fuera de Elaboracion."""
from datetime import date

from backend.services import convenios
from backend.services.vigencia import vencimiento_esperado


def vigencia_nueva(*, inicio: date | None = None, duracion_meses: int = 12) -> dict:
    inicio = inicio or convenios.fecha_actual_dominio()
    return {
        "fecha_inicio": inicio,
        "duracion_meses": duracion_meses,
        "fecha_vencimiento": vencimiento_esperado(inicio, duracion_meses),
    }


def vigencia_json(**opciones) -> dict:
    return {campo: valor.isoformat() if isinstance(valor, date) else valor
            for campo, valor in vigencia_nueva(**opciones).items()}
