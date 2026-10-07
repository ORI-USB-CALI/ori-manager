from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.usuario import Usuario
from backend.services import alertas_vencimiento
from backend.services.alertas_vencimiento import (
    ProximoVencimiento,
    RangoVencimiento,
    ServicioAlertasVencimiento,
)

FECHA_REFERENCIA = date(2026, 10, 7)


@pytest.fixture
def crear_alertable(
    db: Session, gestor: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(
        *,
        dias: int | None,
        estado: EstadoConvenio = EstadoConvenio.VIGENTE,
        codigo: str | None = None,
        objeto: str = "Convenio identificable HU-30",
    ) -> Convenio:
        convenio = crear_convenio(
            gestor,
            codigo=codigo,
            objeto=objeto,
            fecha_vencimiento=(
                FECHA_REFERENCIA + timedelta(days=dias) if dias is not None else None
            ),
        )
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


@pytest.mark.parametrize(
    ("dias", "rango"),
    [
        (0, RangoVencimiento.DIAS_0_30),
        (30, RangoVencimiento.DIAS_0_30),
        (31, RangoVencimiento.DIAS_31_60),
        (60, RangoVencimiento.DIAS_31_60),
        (61, RangoVencimiento.DIAS_61_90),
        (90, RangoVencimiento.DIAS_61_90),
        (91, RangoVencimiento.DIAS_91_120),
        (120, RangoVencimiento.DIAS_91_120),
    ],
)
def test_clasifica_limites_inclusivos(
    db, crear_alertable, dias: int, rango: RangoVencimiento
) -> None:
    convenio = crear_alertable(dias=dias)

    resultados = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        FECHA_REFERENCIA
    )

    resultado = next(item for item in resultados if item.convenio_id == convenio.id)
    assert resultado.dias_restantes == dias
    assert resultado.rango_vencimiento == rango


@pytest.mark.parametrize(
    ("dias", "estado"),
    [
        (121, EstadoConvenio.VIGENTE),
        (-1, EstadoConvenio.VIGENTE),
        (None, EstadoConvenio.VIGENTE),
        (15, EstadoConvenio.EN_TRAMITE),
        (15, EstadoConvenio.VENCIDO),
        (15, EstadoConvenio.RENOVADO),
        (15, EstadoConvenio.FINALIZADO),
        (15, EstadoConvenio.CANCELADO),
    ],
)
def test_excluye_fechas_y_estados_no_elegibles(
    db, crear_alertable, dias: int | None, estado: EstadoConvenio
) -> None:
    convenio = crear_alertable(dias=dias, estado=estado)

    resultados = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        FECHA_REFERENCIA
    )

    assert convenio.id not in {item.convenio_id for item in resultados}


@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER])
def test_incluye_estados_activos(db, crear_alertable, estado: EstadoConvenio) -> None:
    convenio = crear_alertable(dias=15, estado=estado)

    resultados = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        FECHA_REFERENCIA
    )

    assert convenio.id in {item.convenio_id for item in resultados}


def test_cada_convenio_pertenece_a_un_solo_rango(db, crear_alertable) -> None:
    convenios = [crear_alertable(dias=dias) for dias in (15, 45, 75, 105)]

    resultados = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        FECHA_REFERENCIA
    )
    seleccionados = [
        item for item in resultados if item.convenio_id in {c.id for c in convenios}
    ]

    assert len(seleccionados) == len(convenios)
    assert {item.rango_vencimiento for item in seleccionados} == set(RangoVencimiento)


def test_ordena_por_vencimiento_y_por_id(db, crear_alertable) -> None:
    mas_tarde = crear_alertable(dias=60)
    mismo_dia_primero = crear_alertable(dias=30)
    mismo_dia_segundo = crear_alertable(dias=30)

    resultados = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        FECHA_REFERENCIA
    )
    ids_creados = {mas_tarde.id, mismo_dia_primero.id, mismo_dia_segundo.id}

    assert [
        item.convenio_id for item in resultados if item.convenio_id in ids_creados
    ] == [mismo_dia_primero.id, mismo_dia_segundo.id, mas_tarde.id]


def test_segunda_consulta_refleja_cambio_de_fecha(db, crear_alertable) -> None:
    convenio = crear_alertable(dias=20)
    servicio = ServicioAlertasVencimiento(db)

    primera = servicio.listar_proximos_vencimientos(FECHA_REFERENCIA)
    assert (
        next(
            item for item in primera if item.convenio_id == convenio.id
        ).rango_vencimiento
        == RangoVencimiento.DIAS_0_30
    )

    convenio.fecha_vencimiento = FECHA_REFERENCIA + timedelta(days=75)
    db.commit()

    segunda = servicio.listar_proximos_vencimientos(FECHA_REFERENCIA)
    actualizado = next(item for item in segunda if item.convenio_id == convenio.id)
    assert actualizado.fecha_vencimiento == FECHA_REFERENCIA + timedelta(days=75)
    assert actualizado.dias_restantes == 75
    assert actualizado.rango_vencimiento == RangoVencimiento.DIAS_61_90


def test_consulta_es_read_only_y_no_fuerza_flush(
    db, crear_alertable, monkeypatch
) -> None:
    convenio = crear_alertable(dias=20)
    estado_inicial = convenio.estado
    actualizado_inicial = convenio.actualizado_en
    auditorias_iniciales = db.scalar(select(func.count()).select_from(Auditoria))

    def operacion_prohibida(*args, **kwargs) -> None:
        raise AssertionError("El servicio de alertas intentó escribir")

    with monkeypatch.context() as contexto:
        contexto.setattr(db, "commit", operacion_prohibida)
        contexto.setattr(db, "flush", operacion_prohibida)

        ServicioAlertasVencimiento(db).listar_proximos_vencimientos(FECHA_REFERENCIA)

    db.expire(convenio)
    assert convenio.estado == estado_inicial
    assert convenio.actualizado_en == actualizado_inicial
    assert (
        db.scalar(select(func.count()).select_from(Auditoria)) == auditorias_iniciales
    )


def test_resultado_identifica_convenio_sin_codigo(db, crear_alertable) -> None:
    convenio = crear_alertable(
        dias=12,
        codigo=None,
        objeto="Cooperación académica sin código",
    )

    resultado = next(
        item
        for item in ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
            FECHA_REFERENCIA
        )
        if item.convenio_id == convenio.id
    )

    assert resultado == ProximoVencimiento(
        convenio_id=convenio.id,
        codigo=None,
        objeto="Cooperación académica sin código",
        fecha_vencimiento=FECHA_REFERENCIA + timedelta(days=12),
        dias_restantes=12,
        rango_vencimiento=RangoVencimiento.DIAS_0_30,
    )


def test_fecha_por_defecto_usa_zona_horaria_de_bogota(db, monkeypatch) -> None:
    zonas_recibidas = []

    class FechaHoraFija:
        @classmethod
        def now(cls, zona):
            zonas_recibidas.append(zona)
            return datetime(2026, 10, 7, 23, 59, tzinfo=zona)

    monkeypatch.setattr(alertas_vencimiento, "datetime", FechaHoraFija)

    assert ServicioAlertasVencimiento(db).listar_proximos_vencimientos() == []
    assert zonas_recibidas == [alertas_vencimiento.ZONA_HORARIA_DOMINIO]
    assert alertas_vencimiento.ZONA_HORARIA_DOMINIO.key == "America/Bogota"
