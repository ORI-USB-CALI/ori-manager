from datetime import date, timedelta

from sqlalchemy import event, func, select

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.enums import EstadoConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.services.renovaciones import listar_seguimiento_renovaciones

FECHA_REFERENCIA = date(2026, 10, 7)


def test_consulta_agregada_no_produce_n_mas_uno(db, gestor, crear_convenio) -> None:
    for dias in (15, 45, 75):
        convenio = crear_convenio(
            gestor,
            fecha_vencimiento=FECHA_REFERENCIA + timedelta(days=dias),
        )
        convenio.estado = EstadoConvenio.VIGENTE.value
    db.commit()

    sentencias = []

    def registrar_sentencia(*args) -> None:
        sentencias.append(args[2])

    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", registrar_sentencia)
    try:
        resultados = listar_seguimiento_renovaciones(db, fecha_referencia=FECHA_REFERENCIA)
    finally:
        event.remove(conexion, "before_cursor_execute", registrar_sentencia)

    assert len(resultados) == 3
    assert len(sentencias) == 1


def test_consulta_es_read_only_y_no_fuerza_flush(
    db, gestor, crear_convenio, monkeypatch
) -> None:
    convenio = crear_convenio(
        gestor,
        fecha_vencimiento=FECHA_REFERENCIA + timedelta(days=30),
    )
    convenio.estado = EstadoConvenio.VIGENTE.value
    db.commit()
    estado_inicial = convenio.estado
    actualizado_inicial = convenio.actualizado_en
    conteos_iniciales = {
        "auditorias": db.scalar(select(func.count()).select_from(Auditoria)),
        "decisiones": db.scalar(
            select(func.count()).select_from(DecisionNoRenovacion)
        ),
        "solicitudes": db.scalar(
            select(func.count()).select_from(SolicitudConvenio)
        ),
        "convenios": db.scalar(select(func.count()).select_from(Convenio)),
    }

    def operacion_prohibida(*args, **kwargs) -> None:
        raise AssertionError("La consulta del panel intentó escribir")

    with monkeypatch.context() as contexto:
        contexto.setattr(db, "commit", operacion_prohibida)
        contexto.setattr(db, "flush", operacion_prohibida)
        resultados = listar_seguimiento_renovaciones(
            db, fecha_referencia=FECHA_REFERENCIA
        )

    db.expire(convenio)
    assert [item.convenio_id for item in resultados] == [convenio.id]
    assert convenio.estado == estado_inicial
    assert convenio.actualizado_en == actualizado_inicial
    assert db.scalar(select(func.count()).select_from(Auditoria)) == (
        conteos_iniciales["auditorias"]
    )
    assert db.scalar(select(func.count()).select_from(DecisionNoRenovacion)) == (
        conteos_iniciales["decisiones"]
    )
    assert db.scalar(select(func.count()).select_from(SolicitudConvenio)) == (
        conteos_iniciales["solicitudes"]
    )
    assert db.scalar(select(func.count()).select_from(Convenio)) == (
        conteos_iniciales["convenios"]
    )
